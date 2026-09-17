"""Diversity caps и жадный отбор с лимитами per-artist / anchor."""

from __future__ import annotations

from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.quality import (
    diversity_artist_keys,
    hard_references_in_artists,
    normalize_song_title,
)
from app.utils.scoring.constants import ANCHOR_PLAYLIST_CAP_RATIO


def max_tracks_per_artist(playlist_size: int, *, configured: int | None = None) -> int:
    """Лимит non-anchor артиста; `configured` = settings.max_tracks_per_artist."""
    base = configured if configured is not None else 2
    if base < 1:
        base = 1
    return base if playlist_size <= 25 else max(base, 3)


def max_anchor_tracks(playlist_size: int) -> int:
    """Суммарный cap hard-якорей (~60% плейлиста)."""
    return max(1, int(playlist_size * ANCHOR_PLAYLIST_CAP_RATIO))


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
        is_anchor = profile is not None and hard_references_in_artists(track, profile)
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


def append_diverse_tracks(
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
    if len(selected) >= limit:
        return selected

    seen_titles = {normalize_song_title(track.title) for track, _ in selected}
    artist_counts: dict[str, int] = {}
    for track, _ in selected:
        for key in diversity_artist_keys(track):
            artist_counts[key] = artist_counts.get(key, 0) + 1
    anchors_used = sum(1 for track, _ in selected if hard_references_in_artists(track, profile))

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
