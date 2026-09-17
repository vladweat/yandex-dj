"""Двухфазный отбор плейлиста: голова → expansion, shortfall."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
from app.schemas.llm import MusicProfile
from app.schemas.track import (
    RETRIEVAL_TIER_SEARCH,
    RETRIEVAL_TIER_SIMILAR,
    TrackCandidate,
)
from app.utils.quality import (
    diversity_artist_keys,
    hard_references_in_artists,
    normalize_song_title,
)
from app.utils.scoring.adjustments import (
    apply_mood_title_demote,
    is_score_plateau,
    prefer_non_anchors_on_plateau,
)
from app.utils.scoring.constants import (
    ANCHOR_FILL_MAX_TRACKS_PER_ARTIST,
    ANCHOR_MAX_TRACKS_PER_ARTIST,
    ELBOW_MIN_GAP,
    EXPANSION_MEDIAN_GAP,
    HEAD_LOCK_MAX,
    HEAD_LOCK_MIN,
    HIGH_DIVERSITY_ANCHOR_FILL,
    HIGH_DIVERSITY_ANCHOR_MAX,
    HIGH_DIVERSITY_MAX_PER_ARTIST,
    ISOLATE_DEMOTE,
    SEARCH_ONLY_DEMOTE,
    SHORTFALL_QUALITY_GAP,
    SOURCE_PRIOR_BOOST,
    TAIL_SCORE_DROP,
    TOP_MEDIAN_WINDOW,
)
from app.utils.scoring.diversity import (
    append_diverse_tracks,
    apply_diversity_filter,
    max_anchor_tracks,
    max_tracks_per_artist,
)
from app.utils.scoring.floors import (
    filter_by_top_median_gap,
    largest_score_gap_cut,
    playlist_score_floor,
    score_window,
)


class PlaylistSelection(NamedTuple):
    tracks: list[tuple[TrackCandidate, float]]
    shortfall: bool


@dataclass(frozen=True)
class SelectLimits:
    per_artist: int
    anchor_max: int
    anchor_fill: int
    anchor_cap: int


def limits_for_profile(
    profile: MusicProfile,
    *,
    diversity: str,
    max_per_artist: int | None,
) -> SelectLimits:
    limit = profile.target_track_count
    anchor_cap = max_anchor_tracks(limit)
    if diversity == "high":
        return SelectLimits(
            per_artist=HIGH_DIVERSITY_MAX_PER_ARTIST,
            anchor_max=HIGH_DIVERSITY_ANCHOR_MAX,
            anchor_fill=HIGH_DIVERSITY_ANCHOR_FILL,
            anchor_cap=anchor_cap,
        )
    per_artist = (
        max_per_artist if max_per_artist is not None else max_tracks_per_artist(limit)
    )
    return SelectLimits(
        per_artist=per_artist,
        anchor_max=ANCHOR_MAX_TRACKS_PER_ARTIST,
        anchor_fill=ANCHOR_FILL_MAX_TRACKS_PER_ARTIST,
        anchor_cap=anchor_cap,
    )


def compute_head_lock_size(scores: list[float], limit: int) -> int:
    """Число треков фазы A: до HEAD_LOCK_MAX или по elbow на ранжированном списке."""
    if limit <= 0 or not scores:
        return 0
    if limit <= HEAD_LOCK_MAX:
        reserve = max(3, limit // 4)
        return max(1, min(limit - reserve, len(scores), limit))
    cap = min(limit, HEAD_LOCK_MAX)
    if len(scores) < HEAD_LOCK_MIN:
        return min(limit, len(scores))

    window = score_window(scores, limit)
    best_gap, cut_index = largest_score_gap_cut(window)
    min_tracks = max(1, limit // 2)
    if best_gap >= ELBOW_MIN_GAP and cut_index >= min_tracks and cut_index >= HEAD_LOCK_MIN:
        return min(cut_index, cap, limit)
    return min(cap, limit)


def is_rich_candidate_pool(ranked: list[tuple[TrackCandidate, float]], limit: int) -> bool:
    """Пул достаточно большой, чтобы ослабить tail floor при доборе хвоста до N."""
    return len(ranked) >= max(limit + 3, 28)


def use_strict_expansion_quality(
    ranked: list[tuple[TrackCandidate, float]],
    limit: int,
) -> bool:
    """На больших плоских пулах — жёсткий quality floor для expansion (иначе shortfall)."""
    return len(ranked) >= 100 and is_score_plateau(ranked, limit)


def expansion_quality_floor(head: list[tuple[TrackCandidate, float]]) -> float:
    """Минимальный score для expansion: медиана головы минус EXPANSION_MEDIAN_GAP."""
    if not head:
        return 0.0
    top_scores = [score for _, score in head[:TOP_MEDIAN_WINDOW]]
    median = float(np.median(np.asarray(top_scores, dtype=np.float64)))
    return median - EXPANSION_MEDIAN_GAP


def pool_artist_counts(ranked: list[tuple[TrackCandidate, float]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for track, _ in ranked:
        keys = diversity_artist_keys(track)
        if not keys:
            keys = [track.title.lower()]
        for key in keys:
            counts[key] = counts.get(key, 0) + 1
    return counts


def apply_expansion_prior(
    ranked: list[tuple[TrackCandidate, float]],
    head: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
    *,
    pool_artist_counts: dict[str, int],
) -> list[tuple[TrackCandidate, float]]:
    """Смещение score при доборе: boost similar, demote search-only и одиночных артистов."""
    head_keys: set[str] = set()
    head_floor = min((score for _, score in head), default=0.0)
    isolate_below = head_floor - 0.06
    for track, _ in head:
        for key in diversity_artist_keys(track):
            head_keys.add(key)

    adjusted: list[tuple[TrackCandidate, float]] = []
    for track, score in ranked:
        adj = score
        keys = diversity_artist_keys(track)
        if not keys:
            keys = [track.title.lower()]

        if track.retrieval_tier >= RETRIEVAL_TIER_SIMILAR:
            adj += SOURCE_PRIOR_BOOST
        elif track.retrieval_tier == RETRIEVAL_TIER_SEARCH:
            adj -= SEARCH_ONLY_DEMOTE

        connected = any(key in head_keys for key in keys)
        singleton = any(pool_artist_counts.get(key, 0) <= 1 for key in keys)
        if (
            singleton
            and not connected
            and not hard_references_in_artists(track, profile)
            and track.retrieval_tier == RETRIEVAL_TIER_SEARCH
            and score < isolate_below
        ):
            adj -= ISOLATE_DEMOTE

        adjusted.append((track, adj))
    adjusted.sort(key=lambda item: item[1], reverse=True)
    return adjusted


def exclude_selected(
    ranked: list[tuple[TrackCandidate, float]],
    selected: list[tuple[TrackCandidate, float]],
) -> list[tuple[TrackCandidate, float]]:
    taken_ids = {track.id for track, _ in selected}
    taken_titles = {normalize_song_title(track.title) for track, _ in selected}
    return [
        (track, score)
        for track, score in ranked
        if track.id not in taken_ids
        and normalize_song_title(track.title) not in taken_titles
    ]


def select_phase_head(
    ranked: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
    head_k: int,
    *,
    limits: SelectLimits,
    limit: int,
) -> list[tuple[TrackCandidate, float]]:
    scores = [score for _, score in ranked]
    strict_floor = playlist_score_floor(scores, limit, strict=True)

    selected = apply_diversity_filter(
        ranked,
        limit=head_k,
        max_per_artist=limits.per_artist,
        min_score=strict_floor,
        profile=profile,
        anchor_max_per_artist=limits.anchor_max,
        max_anchor_total=limits.anchor_cap,
    )
    soft_floor = playlist_score_floor(scores, limit, strict=False)
    if len(selected) < head_k and soft_floor < strict_floor:
        selected = append_diverse_tracks(
            ranked,
            selected,
            limit=head_k,
            max_per_artist=limits.per_artist,
            min_score=soft_floor,
            profile=profile,
            anchor_max_per_artist=limits.anchor_max,
            max_anchor_total=limits.anchor_cap,
        )
    return selected


def build_expansion_fill_pool(
    ranked: list[tuple[TrackCandidate, float]],
    head: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
    *,
    remaining_slots: int,
    pool_artist_counts: dict[str, int],
) -> tuple[list[tuple[TrackCandidate, float]], list[tuple[TrackCandidate, float]]]:
    raw_pool = exclude_selected(ranked, head)
    raw_pool = prefer_non_anchors_on_plateau(raw_pool, profile, limit=remaining_slots)
    ordered = apply_expansion_prior(
        raw_pool,
        head,
        profile,
        pool_artist_counts=pool_artist_counts,
    )
    raw_by_id = {track.id: score for track, score in raw_pool}
    fill_pool: list[tuple[TrackCandidate, float]] = []
    for track, _ in ordered:
        raw_score = raw_by_id.get(track.id)
        if raw_score is not None:
            fill_pool.append((track, raw_score))
    return fill_pool, raw_pool


def expansion_only(
    combined: list[tuple[TrackCandidate, float]],
    head_len: int,
) -> list[tuple[TrackCandidate, float]]:
    return combined[head_len:]


def append_expansion_at_floor(
    fill_pool: list[tuple[TrackCandidate, float]],
    combined: list[tuple[TrackCandidate, float]],
    *,
    playlist_limit: int,
    limits: SelectLimits,
    profile: MusicProfile,
    min_score: float,
) -> list[tuple[TrackCandidate, float]]:
    return append_diverse_tracks(
        fill_pool,
        combined,
        limit=playlist_limit,
        max_per_artist=limits.per_artist,
        min_score=min_score,
        profile=profile,
        anchor_max_per_artist=limits.anchor_max,
        max_anchor_total=limits.anchor_cap,
    )


def select_phase_expansion(
    ranked: list[tuple[TrackCandidate, float]],
    head: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
    *,
    limit: int,
    limits: SelectLimits,
    pool_artist_counts: dict[str, int],
) -> tuple[list[tuple[TrackCandidate, float]], bool]:
    remaining_slots = limit - len(head)
    if remaining_slots <= 0:
        return [], False

    fill_pool, raw_pool = build_expansion_fill_pool(
        ranked,
        head,
        profile,
        remaining_slots=remaining_slots,
        pool_artist_counts=pool_artist_counts,
    )

    quality_floor = expansion_quality_floor(head)
    rich_pool = is_rich_candidate_pool(ranked, limit)
    strict_quality = use_strict_expansion_quality(ranked, limit)
    expansion_scores = [score for _, score in raw_pool]
    elbow_strict = (
        playlist_score_floor(expansion_scores, remaining_slots, strict=True)
        if expansion_scores
        else quality_floor
    )
    strict_floor = max(quality_floor, elbow_strict) if strict_quality else elbow_strict

    playlist_limit = len(head) + remaining_slots
    head_len = len(head)

    combined = append_expansion_at_floor(
        fill_pool,
        list(head),
        playlist_limit=playlist_limit,
        limits=limits,
        profile=profile,
        min_score=strict_floor,
    )
    expansion = expansion_only(combined, head_len)

    if len(expansion) < remaining_slots:
        soft_elbow = (
            playlist_score_floor(expansion_scores, remaining_slots, strict=False)
            if expansion_scores
            else quality_floor
        )
        soft_floor = max(quality_floor, soft_elbow) if strict_quality else soft_elbow
        if soft_floor < strict_floor:
            combined = append_expansion_at_floor(
                fill_pool,
                combined,
                playlist_limit=playlist_limit,
                limits=limits,
                profile=profile,
                min_score=soft_floor,
            )
            expansion = expansion_only(combined, head_len)

    if len(expansion) < remaining_slots and head:
        head_floor = min(score for _, score in head)
        tail_drop = TAIL_SCORE_DROP + (0.02 if rich_pool else 0.0)
        tail_floor = head_floor - tail_drop
        if not rich_pool:
            tail_floor = max(quality_floor, tail_floor)
        combined = append_diverse_tracks(
            fill_pool,
            combined,
            limit=playlist_limit,
            max_per_artist=limits.per_artist,
            min_score=tail_floor,
            profile=profile,
            anchor_max_per_artist=limits.anchor_fill,
            max_anchor_total=limits.anchor_cap,
        )
        expansion = expansion_only(combined, head_len)

    shortfall = len(expansion) < remaining_slots
    if shortfall and head:
        head_floor = min(score for _, score in head)
        reject_floor = head_floor - TAIL_SCORE_DROP - SHORTFALL_QUALITY_GAP
        best_score = max((score for _, score in raw_pool), default=0.0)
        if best_score < reject_floor:
            shortfall = True
    return expansion, shortfall


def finalize_playlist_order(
    head: list[tuple[TrackCandidate, float]],
    expansion: list[tuple[TrackCandidate, float]],
    *,
    limit: int,
) -> list[tuple[TrackCandidate, float]]:
    """Сначала голова по score, затем expansion — фазы не перемешиваются."""
    head_sorted = sorted(head, key=lambda item: item[1], reverse=True)
    expansion_sorted = sorted(expansion, key=lambda item: item[1], reverse=True)
    return (head_sorted + expansion_sorted)[:limit]


def select_playlist_tracks(
    ranked: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
    *,
    diversity: str = "normal",
    max_per_artist: int | None = None,
) -> list[tuple[TrackCandidate, float]]:
    """Отбор топ-N: фиксированная голова, expansion, возможный shortfall."""
    return select_playlist_with_meta(
        ranked,
        profile,
        diversity=diversity,
        max_per_artist=max_per_artist,
    ).tracks


def select_playlist_with_meta(
    ranked: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
    *,
    diversity: str = "normal",
    max_per_artist: int | None = None,
) -> PlaylistSelection:
    """Двухфазный отбор: голова → expansion; shortfall вместо низкокачественного добора."""
    limit = profile.target_track_count
    if not ranked:
        return PlaylistSelection([], shortfall=False)

    ranked = filter_by_top_median_gap(ranked)
    if not ranked:
        return PlaylistSelection([], shortfall=False)

    ranked = apply_mood_title_demote(ranked, profile)
    scores = [score for _, score in ranked]
    limits = limits_for_profile(
        profile, diversity=diversity, max_per_artist=max_per_artist
    )
    artist_counts = pool_artist_counts(ranked)

    head_k = compute_head_lock_size(scores, limit)
    head = select_phase_head(
        ranked,
        profile,
        head_k,
        limits=limits,
        limit=limit,
    )

    expansion, shortfall = select_phase_expansion(
        ranked,
        head,
        profile,
        limit=limit,
        limits=limits,
        pool_artist_counts=artist_counts,
    )

    selected = finalize_playlist_order(head, expansion, limit=limit)
    if len(selected) < limit:
        shortfall = True
    return PlaylistSelection(selected, shortfall=shortfall)
