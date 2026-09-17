"""Каверы, tribute и compilation-исполнители."""

from app.schemas.track import TrackCandidate
from app.utils.quality.patterns import ARRANGEMENT_MARKERS, COMPILATION_ARTIST


def is_arrangement(track: TrackCandidate) -> bool:
    haystack = f"{track.title} {track.version}".strip()
    return bool(ARRANGEMENT_MARKERS.search(haystack))


def is_compilation_artist(track: TrackCandidate) -> bool:
    """Исполнитель-заглушка (soundtrack orchestra и т.п.) — для любого жанра."""
    for name in track.artists:
        if COMPILATION_ARTIST.search(name):
            return True
    return False
