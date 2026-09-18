"""Исключение артистов и языков из пула/плейлиста (опции generate)."""

from __future__ import annotations

import logging

from app.schemas.llm import MusicProfile
from app.schemas.scoring import ScoredTrack
from app.schemas.track import TrackCandidate
from app.utils.prompt_constraints import filter_excluded_languages
from app.utils.quality import artist_matches_reference, artist_tokens

logger = logging.getLogger(__name__)


def normalize_excludes(names: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        cleaned = name.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def is_explicit_track(track: TrackCandidate | ScoredTrack) -> bool:
    return track.explicit is True


def filter_explicit_candidates(candidates: list[TrackCandidate]) -> list[TrackCandidate]:
    return [track for track in candidates if not is_explicit_track(track)]


def filter_explicit_scored(selected: list[ScoredTrack]) -> list[ScoredTrack]:
    return [track for track in selected if not is_explicit_track(track)]


def apply_exclude_artists(
    profile: MusicProfile,
    exclude_artists: list[str],
) -> tuple[MusicProfile, list[str]]:
    """
    Убирает excludes из reference_artists, если останется ≥4 якоря.

    Возвращает (profile, warnings). Кандидаты фильтруются отдельно —
    даже если якоря не трогали.
    """
    excludes = normalize_excludes(exclude_artists)
    if not excludes:
        return profile, []
    remaining = [
        artist
        for artist in profile.reference_artists
        if not any(artist_matches_reference(artist, excluded) for excluded in excludes)
    ]
    if len(remaining) < 4:
        kept = [
            artist
            for artist in profile.reference_artists
            if any(artist_matches_reference(artist, excluded) for excluded in excludes)
        ]
        names = ", ".join(kept) if kept else ", ".join(excludes)
        warning = (
            f"exclude_artists не сняты с якорей (нужно ≥4 reference_artists): {names}. "
            "Из пула кандидатов они всё равно исключены."
        )
        logger.warning(warning)
        return profile, [warning]
    hard_remaining = [
        artist
        for artist in profile.hard_reference_artists
        if any(artist_matches_reference(artist, ref) for ref in remaining)
        and not any(artist_matches_reference(artist, excluded) for excluded in excludes)
    ]
    return (
        profile.model_copy(
            update={
                "reference_artists": remaining,
                "hard_reference_artists": hard_remaining,
            }
        ),
        [],
    )


def filter_excluded_candidates(
    candidates: list[TrackCandidate],
    exclude_artists: list[str],
) -> list[TrackCandidate]:
    excludes = normalize_excludes(exclude_artists)
    if not excludes:
        return candidates
    kept: list[TrackCandidate] = []
    for track in candidates:
        tokens = artist_tokens(track)
        if any(
            artist_matches_reference(token, excluded) for token in tokens for excluded in excludes
        ):
            continue
        kept.append(track)
    return kept


def filter_excluded_scored(
    selected: list[ScoredTrack],
    exclude_artists: list[str],
) -> list[ScoredTrack]:
    excludes = normalize_excludes(exclude_artists)
    if not excludes:
        return selected
    kept: list[ScoredTrack] = []
    for track in selected:
        if any(
            artist_matches_reference(artist, excluded)
            for artist in track.artists
            for excluded in excludes
        ):
            continue
        kept.append(track)
    return kept


def apply_candidate_pool_filters(
    candidates: list[TrackCandidate],
    *,
    exclude_artists: list[str],
    exclude_languages: list[str],
    exclude_explicit: bool = False,
) -> list[TrackCandidate]:
    filtered = filter_excluded_candidates(candidates, exclude_artists)
    filtered = filter_excluded_languages(filtered, exclude_languages)
    if exclude_explicit:
        filtered = filter_explicit_candidates(filtered)
    return filtered


def apply_selected_track_filters(
    selected: list[ScoredTrack],
    *,
    exclude_artists: list[str],
    exclude_languages: list[str],
    exclude_explicit: bool = False,
) -> list[ScoredTrack]:
    filtered = filter_excluded_scored(selected, exclude_artists)
    filtered = filter_excluded_languages(filtered, exclude_languages)
    if exclude_explicit:
        filtered = filter_explicit_scored(filtered)
    return filtered
