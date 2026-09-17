"""Коррекции ранга: mood-title, plateau, anchor/library boost."""

from __future__ import annotations

import re

from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.mood_tokens import MOOD_TITLE_DEMOTE_TOKENS
from app.utils.quality import artist_matches_reference, hard_references_in_artists
from app.utils.scoring.constants import (
    LIBRARY_ARTIST_BOOST,
    MOOD_TITLE_DEMOTE,
    PLATEAU_SCORE_BUCKET,
    PLATEAU_SCORE_SPAN,
    REFERENCE_ANCHOR_BOOST,
)


def apply_mood_title_demote(
    ranked: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
    *,
    penalty: float = MOOD_TITLE_DEMOTE,
) -> list[tuple[TrackCandidate, float]]:
    """Слегка понизить score, если title пересекается с mood_tags (Sad/Emotional…)."""
    if penalty <= 0 or not ranked:
        return ranked
    profile_mood = {
        token
        for tag in profile.mood_tags
        for token in re.findall(r"[a-z0-9]+", tag.lower())
    }
    demote_tokens = profile_mood & MOOD_TITLE_DEMOTE_TOKENS
    if not demote_tokens:
        return ranked

    adjusted: list[tuple[TrackCandidate, float]] = []
    for track, score in ranked:
        title_tokens = set(re.findall(r"[a-z0-9]+", track.title.lower()))
        if title_tokens & demote_tokens:
            score = max(0.0, score - penalty)
        adjusted.append((track, score))
    adjusted.sort(key=lambda item: item[1], reverse=True)
    return adjusted


def is_score_plateau(
    ranked: list[tuple[TrackCandidate, float]],
    limit: int,
    *,
    span: float = PLATEAU_SCORE_SPAN,
) -> bool:
    if len(ranked) < max(limit, 2):
        return False
    top = ranked[0][1]
    edge = ranked[min(limit, len(ranked)) - 1][1]
    return (top - edge) < span


def prefer_non_anchors_on_plateau(
    ranked: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
    *,
    limit: int | None = None,
) -> list[tuple[TrackCandidate, float]]:
    """При малом размахе топ-N в score-корзинах ставить не-hard-якоря выше hard-якорей."""
    target = limit if limit is not None else profile.target_track_count
    if not is_score_plateau(ranked, target):
        return ranked

    def sort_key(item: tuple[TrackCandidate, float]) -> tuple[int, int, float]:
        track, score = item
        bucket = int(round(score / PLATEAU_SCORE_BUCKET))
        is_hard = 1 if hard_references_in_artists(track, profile) else 0
        return (-bucket, is_hard, -score)

    return sorted(ranked, key=sort_key)


def apply_reference_anchor_boost(
    ranked: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
) -> list[tuple[TrackCandidate, float]]:
    """Мягкий буст hard-якорным артистам (soft refs — без boost)."""
    boosted: list[tuple[TrackCandidate, float]] = []
    for track, score in ranked:
        if hard_references_in_artists(track, profile):
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
