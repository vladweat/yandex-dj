from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.quality import (
    is_genre_suffix_artist,
    is_mood_keyword_artist,
    is_spurious_track,
    looks_like_seo_artist,
    references_in_artists,
)


def non_anchor_artists_from_ranked(
    ranked: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
    *,
    limit: int,
    scan_top: int = 40,
) -> list[str]:
    """Лучшие не-якорные артисты по embedding-рангу — для feedback expand."""
    found: list[str] = []
    seen: set[str] = set()
    for track, _score in ranked[:scan_top]:
        if references_in_artists(track, profile):
            continue
        if is_spurious_track(track, profile):
            continue
        for name in track.artists:
            key = name.lower().strip()
            if not key or key in seen:
                continue
            if looks_like_seo_artist(name):
                continue
            if is_mood_keyword_artist(name) or is_genre_suffix_artist(name):
                continue
            seen.add(key)
            found.append(name.strip())
            if len(found) >= limit:
                return found
    return found
