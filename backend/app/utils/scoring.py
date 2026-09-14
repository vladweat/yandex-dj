"""Чистые функции скоринга: cosine, diversity, fallback."""

from __future__ import annotations

import numpy as np
from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate


def build_prompt_text(profile: MusicProfile, user_prompt: str | None = None) -> str:
    parts: list[str] = []
    if user_prompt and user_prompt.strip():
        parts.append(user_prompt.strip())
    parts.append(profile.playlist_description)
    if profile.primary_genres:
        parts.append("Жанры: " + ", ".join(profile.primary_genres))
    if profile.mood_tags:
        parts.append("Настроение: " + ", ".join(profile.mood_tags))
    if profile.reference_artists:
        parts.append("Артисты: " + ", ".join(profile.reference_artists))
    if profile.vocal_type != "any":
        parts.append(f"Вокал: {profile.vocal_type}")
    return ". ".join(parts)


def max_tracks_per_artist(playlist_size: int) -> int:
    return 2 if playlist_size <= 25 else 3


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


def apply_diversity_filter(
    ranked: list[tuple[TrackCandidate, float]],
    *,
    limit: int,
    max_per_artist: int,
) -> list[tuple[TrackCandidate, float]]:
    artist_counts: dict[str, int] = {}
    selected: list[tuple[TrackCandidate, float]] = []

    for track, score in ranked:
        if len(selected) >= limit:
            break
        artist = track.artists[0].lower() if track.artists else track.title.lower()
        if artist_counts.get(artist, 0) >= max_per_artist:
            continue
        artist_counts[artist] = artist_counts.get(artist, 0) + 1
        selected.append((track, score))

    return selected


def merge_embedding_rank(
    profile: MusicProfile,
    candidates: list[TrackCandidate],
    embedded: list[tuple[TrackCandidate, float]],
) -> list[tuple[TrackCandidate, float]]:
    """Embed-пул + fallback-хвост, чтобы diversity мог набрать target_track_count."""
    if not embedded:
        return fallback_scores(profile, candidates)

    embedded_ids = {track.id for track, _ in embedded}
    min_score = min(score for _, score in embedded)
    tail = [track for track in candidates if track.id not in embedded_ids]
    if not tail:
        return sorted(embedded, key=lambda item: item[1], reverse=True)

    fallback_tail = fallback_scores(profile, tail)
    max_tail = max(score for _, score in fallback_tail)
    if max_tail > 0:
        scale = (min_score * 0.95) / max_tail
        fallback_tail = [(track, score * scale) for track, score in fallback_tail]

    combined = embedded + fallback_tail
    combined.sort(key=lambda item: item[1], reverse=True)
    return combined


def select_embedding_pool(
    profile: MusicProfile,
    candidates: list[TrackCandidate],
    *,
    limit: int,
) -> list[TrackCandidate]:
    if len(candidates) <= limit:
        return candidates
    return [track for track, _ in fallback_scores(profile, candidates)[:limit]]


def apply_reference_artist_boost(
    profile: MusicProfile,
    ranked: list[tuple[TrackCandidate, float]],
    *,
    boost: float = 1.08,
) -> list[tuple[TrackCandidate, float]]:
    ref_artists = {artist.lower() for artist in profile.reference_artists}
    boosted: list[tuple[TrackCandidate, float]] = []
    for track, score in ranked:
        if any(artist.lower() in ref_artists for artist in track.artists):
            score *= boost
        boosted.append((track, score))
    boosted.sort(key=lambda item: item[1], reverse=True)
    return boosted


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
        if any(artist.lower() in ref_artists for artist in track.artists):
            score += 0.5
        score += 0.01 * (pool_size - index) / pool_size
        scored.append((track, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored
