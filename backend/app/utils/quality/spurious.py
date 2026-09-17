"""Сборка универсального pre-filter."""

from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.quality.arrangements import is_arrangement, is_compilation_artist
from app.utils.quality.reference_collision import reference_in_title_only
from app.utils.quality.seo import (
    is_functional_seo_track,
    is_genre_suffix_artist,
    is_mood_keyword_artist,
    is_mood_keyword_title,
)


def is_spurious_track(track: TrackCandidate, profile: MusicProfile) -> bool:
    """
    Универсальные признаки мусора в каталоге.
    Релевантность промпту — только через embedding, не через эвристики жанра.
    """
    if is_arrangement(track):
        return True
    if is_compilation_artist(track):
        return True
    if is_functional_seo_track(track):
        return True
    if is_mood_keyword_title(track.title):
        return True
    if any(is_mood_keyword_artist(name) for name in track.artists):
        return True
    if any(is_genre_suffix_artist(name) for name in track.artists):
        return True
    if reference_in_title_only(track, profile):
        return True
    return False
