"""Keyword spam: имя якоря в title без реального исполнителя."""

import re
from difflib import SequenceMatcher

from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.quality.artists import artist_matches_reference, references_in_artists
from app.utils.quality.text import compact, title_tokens, tokenize_name


def _title_resembles_reference(title: str, reference: str) -> bool:
    title_lower = title.lower().strip()
    ref_lower = reference.lower().strip()
    if title_lower == ref_lower:
        return True
    title_compact = compact(title_lower)
    ref_compact = compact(ref_lower)
    if not title_compact or not ref_compact:
        return False
    if title_compact == ref_compact:
        return True
    if ref_lower in title_lower or ref_compact in title_compact:
        return True
    if len(title_compact) >= 4 and title_compact in ref_compact:
        return len(title_compact) / len(ref_compact) >= 0.75
    if min(len(title_compact), len(ref_compact)) >= 6:
        ratio = SequenceMatcher(None, title_compact, ref_compact).ratio()
        if ratio >= 0.88:
            return True
    return False


def _reference_split_across_title_artist(
    track: TrackCandidate,
    reference: str,
) -> bool:
    """
    Мультисловный якорь размазан: часть в title, часть в artist
    («Night» + «Vitu Lovell» ≈ Night Lovell), без точного match исполнителя.
    """
    ref_parts = [part for part in re.findall(r"[a-z0-9]+", reference.lower()) if len(part) >= 4]
    if len(ref_parts) < 2:
        return False
    if any(artist_matches_reference(artist, reference) for artist in track.artists):
        return False

    title_token_set = set(title_tokens(track.title))
    artist_token_set: set[str] = set()
    for name in track.artists:
        artist_token_set.update(tokenize_name(name))

    in_title = [part for part in ref_parts if part in title_token_set]
    in_artist = [part for part in ref_parts if part in artist_token_set]
    if not in_title or not in_artist:
        return False
    return bool(set(in_title) - set(in_artist)) or bool(set(in_artist) - set(in_title))


def reference_in_title_only(track: TrackCandidate, profile: MusicProfile) -> bool:
    """Имя reference artist в title (или размазано title+artist), но не точный исполнитель."""
    if references_in_artists(track, profile):
        return False

    for ref in profile.reference_artists:
        if _title_resembles_reference(track.title, ref):
            return True
        if _reference_split_across_title_artist(track, ref):
            return True

    return False
