"""Скоринг: cosine similarity → adaptive cutoff → diversity."""

from __future__ import annotations

import numpy as np
from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.quality import (
    artist_matches_reference,
    artist_tokens,
    diversity_artist_keys,
    references_in_artists,
)

REFERENCE_ANCHOR_BOOST = 0.03
LIBRARY_ARTIST_BOOST = 0.025
ANCHOR_MAX_TRACKS_PER_ARTIST = 3
ANCHOR_FILL_MAX_TRACKS_PER_ARTIST = 5
HIGH_DIVERSITY_MAX_PER_ARTIST = 1
HIGH_DIVERSITY_ANCHOR_MAX = 2
HIGH_DIVERSITY_ANCHOR_FILL = 3
TAIL_SCORE_DROP = 0.04
# Доля плейлиста на reference artists (суммарно, не per-artist).
ANCHOR_PLAYLIST_CAP_RATIO = 0.6
# Хвост далеко от медианы топ-K — типичный embedding false positive (Hauvy и т.п.).
TOP_MEDIAN_WINDOW = 10
TOP_MEDIAN_MAX_GAP = 0.15


def build_prompt_text(profile: MusicProfile, user_prompt: str | None = None) -> str:
    parts: list[str] = []
    if user_prompt and user_prompt.strip():
        parts.append(user_prompt.strip())
    parts.append(profile.playlist_description)
    if profile.primary_genres:
        parts.append("Жанры: " + ", ".join(profile.primary_genres))
    if profile.mood_tags:
        parts.append("Настроение: " + ", ".join(profile.mood_tags))
    # reference_artists — только для retrieval, не для embedding-запроса:
    # пользователь может не назвать ни одного артиста («карю макароны»).
    if profile.vocal_type != "any":
        parts.append(f"Вокал: {profile.vocal_type}")
    return ". ".join(parts)


def max_tracks_per_artist(playlist_size: int, *, configured: int | None = None) -> int:
    """Лимит non-anchor артиста; `configured` = settings.max_tracks_per_artist."""
    base = configured if configured is not None else 2
    if base < 1:
        base = 1
    return base if playlist_size <= 25 else max(base, 3)


def max_anchor_tracks(playlist_size: int) -> int:
    """Суммарный cap якорей (~60% плейлиста)."""
    return max(1, int(playlist_size * ANCHOR_PLAYLIST_CAP_RATIO))


def cosine_scores(query_vec: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
    if doc_vecs.size == 0:
        return np.array([], dtype=np.float64)
    query = query_vec.astype(np.float64)
    docs = doc_vecs.astype(np.float64)
    query_norm = np.linalg.norm(query)
    doc_norms = np.linalg.norm(docs, axis=1)
    if query_norm == 0:
        return np.zeros(len(docs), dtype=np.float64)
    safe_norms = np.where(doc_norms == 0, 1.0, doc_norms)
    return (docs @ query) / (query_norm * safe_norms)


def adaptive_score_floor(scores: list[float], limit: int) -> float:
    """
    Порог по наибольшему разрыву в ранжированном списке (elbow).
    Не зависит от жанра; fallback — мягкий ratio от топа.
    """
    if not scores:
        return 0.0
    if len(scores) == 1:
        return scores[0] - 1e-6

    window_size = min(len(scores), max(limit * 2, 10))
    window = scores[:window_size]

    best_gap = 0.0
    cut_index = len(window) - 1
    for index in range(len(window) - 1):
        gap = window[index] - window[index + 1]
        if gap > best_gap:
            best_gap = gap
            cut_index = index + 1

    if len(scores) < limit:
        return scores[-1] - 1e-6

    min_tracks = max(1, limit // 2)
    if best_gap >= 0.025 and cut_index >= min_tracks:
        return window[cut_index] - 1e-6

    return max(window[-1] - 1e-6, window[0] * 0.82)


def filter_by_top_median_gap(
    ranked: list[tuple[TrackCandidate, float]],
    *,
    window: int = TOP_MEDIAN_WINDOW,
    max_gap: float = TOP_MEDIAN_MAX_GAP,
) -> list[tuple[TrackCandidate, float]]:
    """
    Убирает embedding false positives в хвосте: score << медианы топ-K.

    Не привязан к жанру/промпту. На маленьких пулах (< window) не режет.
    """
    if len(ranked) < window:
        return ranked
    top_scores = [score for _, score in ranked[:window]]
    median = float(np.median(np.asarray(top_scores, dtype=np.float64)))
    floor = median - max_gap
    return [(track, score) for track, score in ranked if score >= floor]


def apply_diversity_filter(
    ranked: list[tuple[TrackCandidate, float]],
    *,
    limit: int,
    max_per_artist: int,
    min_score: float | None = None,
    seen_titles: set[str] | None = None,
    artist_counts: dict[str, int] | None = None,
    profile: MusicProfile | None = None,
    anchor_max_per_artist: int | None = None,
    max_anchor_total: int | None = None,
    anchor_total: int = 0,
) -> list[tuple[TrackCandidate, float]]:
    from app.utils.quality import normalize_song_title

    counts: dict[str, int] = dict(artist_counts or {})
    title_keys = set(seen_titles or ())
    selected: list[tuple[TrackCandidate, float]] = []
    anchors_used = anchor_total

    for track, score in ranked:
        if len(selected) >= limit:
            break
        if min_score is not None and score < min_score:
            continue
        title_key = normalize_song_title(track.title)
        if title_key in title_keys:
            continue
        keys = diversity_artist_keys(track)
        if not keys:
            keys = [track.title.lower()]
        is_anchor = profile is not None and references_in_artists(track, profile)
        if is_anchor and max_anchor_total is not None and anchors_used >= max_anchor_total:
            continue
        per_artist_limit = max_per_artist
        if is_anchor and anchor_max_per_artist is not None:
            per_artist_limit = anchor_max_per_artist
        if any(counts.get(key, 0) >= per_artist_limit for key in keys):
            continue
        for key in keys:
            counts[key] = counts.get(key, 0) + 1
        title_keys.add(title_key)
        if is_anchor:
            anchors_used += 1
        selected.append((track, score))

    return selected


def _playlist_score_floor(scores: list[float], limit: int, *, strict: bool) -> float:
    if not scores:
        return 0.0
    elbow = adaptive_score_floor(scores, limit)
    if strict or len(scores) < limit:
        return elbow
    fill_floor = scores[limit - 1] - 1e-6
    return min(elbow, fill_floor)


def _append_diverse_tracks(
    ranked: list[tuple[TrackCandidate, float]],
    selected: list[tuple[TrackCandidate, float]],
    *,
    limit: int,
    max_per_artist: int,
    min_score: float | None,
    profile: MusicProfile,
    anchor_max_per_artist: int,
    max_anchor_total: int,
) -> list[tuple[TrackCandidate, float]]:
    from app.utils.quality import normalize_song_title

    if len(selected) >= limit:
        return selected

    seen_titles = {normalize_song_title(track.title) for track, _ in selected}
    artist_counts: dict[str, int] = {}
    for track, _ in selected:
        for key in diversity_artist_keys(track):
            artist_counts[key] = artist_counts.get(key, 0) + 1
    anchors_used = sum(1 for track, _ in selected if references_in_artists(track, profile))

    extra = apply_diversity_filter(
        ranked,
        limit=limit - len(selected),
        max_per_artist=max_per_artist,
        min_score=min_score,
        seen_titles=seen_titles,
        artist_counts=artist_counts,
        profile=profile,
        anchor_max_per_artist=anchor_max_per_artist,
        max_anchor_total=max_anchor_total,
        anchor_total=anchors_used,
    )
    return selected + extra


def _sort_by_score(
    selected: list[tuple[TrackCandidate, float]],
) -> list[tuple[TrackCandidate, float]]:
    selected.sort(key=lambda item: item[1], reverse=True)
    return selected


def _tail_score_floor(
    selected: list[tuple[TrackCandidate, float]],
) -> float:
    """
    Пол относительно последнего уже отобранного трека.

    Нельзя поднимать до scores[N-1]: топ-N часто занят 3–4 якорями на diversity-cap,
    и этот порог блокирует остальных артистов чуть ниже по score (типичный shortfall 19/25).
    """
    return selected[-1][1] - TAIL_SCORE_DROP


def select_playlist_tracks(
    ranked: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
    *,
    diversity: str = "normal",
    max_per_artist: int | None = None,
) -> list[tuple[TrackCandidate, float]]:
    """Топ-N: gap → elbow + diversity; fill до limit с cap якорей ~60%."""
    limit = profile.target_track_count
    if not ranked:
        return []

    ranked = filter_by_top_median_gap(ranked)
    if not ranked:
        return []

    scores = [score for _, score in ranked]
    anchor_cap = max_anchor_tracks(limit)
    if diversity == "high":
        per_artist = HIGH_DIVERSITY_MAX_PER_ARTIST
        anchor_max = HIGH_DIVERSITY_ANCHOR_MAX
        anchor_fill = HIGH_DIVERSITY_ANCHOR_FILL
    else:
        per_artist = (
            max_per_artist
            if max_per_artist is not None
            else max_tracks_per_artist(limit)
        )
        anchor_max = ANCHOR_MAX_TRACKS_PER_ARTIST
        anchor_fill = ANCHOR_FILL_MAX_TRACKS_PER_ARTIST
    strict_floor = _playlist_score_floor(scores, limit, strict=True)

    selected = apply_diversity_filter(
        ranked,
        limit=limit,
        max_per_artist=per_artist,
        min_score=strict_floor,
        profile=profile,
        anchor_max_per_artist=anchor_max,
        max_anchor_total=anchor_cap,
    )
    soft_floor = _playlist_score_floor(scores, limit, strict=False)
    if len(selected) < limit and soft_floor < strict_floor:
        selected = _append_diverse_tracks(
            ranked,
            selected,
            limit=limit,
            max_per_artist=per_artist,
            min_score=soft_floor,
            profile=profile,
            anchor_max_per_artist=anchor_max,
            max_anchor_total=anchor_cap,
        )

    if len(selected) < limit:
        tail_floor = _tail_score_floor(selected)
        selected = _append_diverse_tracks(
            ranked,
            selected,
            limit=limit,
            max_per_artist=per_artist,
            min_score=tail_floor,
            profile=profile,
            anchor_max_per_artist=anchor_fill,
            max_anchor_total=anchor_cap,
        )

    return _sort_by_score(selected)[:limit]


def apply_reference_anchor_boost(
    ranked: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
) -> list[tuple[TrackCandidate, float]]:
    """Мягкий буст якорным артистам из retrieval (не в embedding-запросе)."""
    boosted: list[tuple[TrackCandidate, float]] = []
    for track, score in ranked:
        if references_in_artists(track, profile):
            score = min(1.0, score + REFERENCE_ANCHOR_BOOST)
        boosted.append((track, score))
    boosted.sort(key=lambda item: item[1], reverse=True)
    return boosted


def apply_library_artist_boost(
    ranked: list[tuple[TrackCandidate, float]],
    library_artists: list[str],
    *,
    boost: float | None = None,
) -> list[tuple[TrackCandidate, float]]:
    """Soft bias: артисты из likes/recent получают небольшой плюс к score."""
    if not library_artists or not ranked:
        return ranked
    delta = LIBRARY_ARTIST_BOOST if boost is None else boost
    if delta <= 0:
        return ranked
    refs = [name.strip() for name in library_artists if name and name.strip()]
    if not refs:
        return ranked

    boosted: list[tuple[TrackCandidate, float]] = []
    for track, score in ranked:
        if any(
            artist_matches_reference(artist, ref)
            for artist in track.artists
            for ref in refs
        ):
            score = min(1.0, score + delta)
        boosted.append((track, score))
    boosted.sort(key=lambda item: item[1], reverse=True)
    return boosted


def merge_embedding_rank(
    profile: MusicProfile,
    candidates: list[TrackCandidate],
    embedded: list[tuple[TrackCandidate, float]],
) -> list[tuple[TrackCandidate, float]]:
    if not embedded:
        return fallback_scores(profile, candidates)
    return apply_reference_anchor_boost(embedded, profile)


def candidates_for_embedding(
    candidates: list[TrackCandidate],
    *,
    limit: int,
) -> list[TrackCandidate]:
    """Весь пул кандидатов в embedding; limit<=0 — без обрезки."""
    if limit <= 0 or len(candidates) <= limit:
        return candidates
    return candidates[:limit]


def fallback_scores(
    profile: MusicProfile,
    candidates: list[TrackCandidate],
) -> list[tuple[TrackCandidate, float]]:
    genres = {genre.lower() for genre in profile.primary_genres}
    ref_artists = {artist.lower() for artist in profile.reference_artists}
    pool_size = max(len(candidates), 1)

    scored: list[tuple[TrackCandidate, float]] = []
    for index, track in enumerate(candidates):
        score = 0.0
        track_genre = track.genre.lower()
        if track_genre and any(genre in track_genre or track_genre in genre for genre in genres):
            score += 1.0
        artists = artist_tokens(track)
        if any(
            artist_matches_reference(artist, ref)
            for artist in artists
            for ref in ref_artists
        ):
            score += 0.5
        score += 0.01 * (pool_size - index) / pool_size
        scored.append((track, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored
