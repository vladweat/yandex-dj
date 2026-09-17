"""Сопоставление артистов с reference-якорями профиля."""

import re

from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.quality.text import compact


def artist_tokens(track: TrackCandidate) -> set[str]:
    tokens: set[str] = set()
    for name in track.artists:
        for part in name.split(","):
            token = part.strip().lower()
            if token:
                tokens.add(token)
    return tokens


def diversity_artist_keys(track: TrackCandidate) -> list[str]:
    return sorted(artist_tokens(track))


def _artist_name_parts(name: str) -> list[str]:
    parts: list[str] = []
    for chunk in re.split(r"[,/&+]+", name.lower()):
        part = chunk.strip()
        if part:
            parts.append(part)
    return parts


def artist_matches_reference(artist: str, reference: str) -> bool:
    """Точное совпадение имени (без «Parcel» ≈ «Parcels»)."""
    ref_lower = reference.lower().strip()
    ref_compact = compact(ref_lower)
    for part in _artist_name_parts(artist):
        if part == ref_lower:
            return True
        if compact(part) == ref_compact:
            return True
    return False


def references_in_artists(track: TrackCandidate, profile: MusicProfile) -> bool:
    artists = artist_tokens(track)
    for ref in profile.reference_artists:
        if any(artist_matches_reference(artist, ref.lower()) for artist in artists):
            return True
    return False


def hard_anchor_names(profile: MusicProfile) -> list[str]:
    """Hard-якоря для boost/diversity; если список пуст — все reference_artists профиля."""
    hard = [name.strip() for name in profile.hard_reference_artists if name.strip()]
    if hard:
        return hard
    return list(profile.reference_artists)


def hard_references_in_artists(track: TrackCandidate, profile: MusicProfile) -> bool:
    artists = artist_tokens(track)
    for ref in hard_anchor_names(profile):
        if any(artist_matches_reference(artist, ref.lower()) for artist in artists):
            return True
    return False
