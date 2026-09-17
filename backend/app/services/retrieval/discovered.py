from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.quality import (
    artist_matches_reference,
    is_genre_suffix_artist,
    is_mood_keyword_artist,
    is_spurious_track,
    looks_like_seo_artist,
)


def rank_discovered_artists(
    candidates: list[TrackCandidate],
    profile: MusicProfile,
    *,
    seen_artists: set[str],
    max_artists: int,
) -> list[str]:
    """Частые clean не-якорные артисты — лучшие seeds для ширины пула."""
    counts: dict[str, int] = {}
    display: dict[str, str] = {}
    for track in candidates:
        if is_spurious_track(track, profile):
            continue
        for name in track.artists:
            key = name.lower().strip()
            if not key or key in seen_artists:
                continue
            if any(artist_matches_reference(name, ref) for ref in profile.reference_artists):
                continue
            if is_mood_keyword_artist(name) or is_genre_suffix_artist(name):
                continue
            if looks_like_seo_artist(name):
                continue
            counts[key] = counts.get(key, 0) + 1
            display.setdefault(key, name.strip())

    ranked_keys = sorted(counts, key=lambda key: (-counts[key], key))
    return [display[key] for key in ranked_keys[:max_artists]]
