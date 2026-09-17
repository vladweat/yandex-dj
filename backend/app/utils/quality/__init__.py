"""Универсальная гигиена каталога — без привязки к жанру или промпту."""

from app.utils.quality.arrangements import is_arrangement, is_compilation_artist
from app.utils.quality.artists import (
    artist_matches_reference,
    artist_tokens,
    diversity_artist_keys,
    hard_anchor_names,
    hard_references_in_artists,
    references_in_artists,
)
from app.utils.quality.seo import (
    is_functional_seo_track,
    is_genre_descriptor_title,
    is_genre_suffix_artist,
    is_mood_keyword_artist,
    is_mood_keyword_title,
    is_production_spam_title,
    looks_like_seo_artist,
    looks_like_seo_title,
)
from app.utils.quality.spurious import is_spurious_track
from app.utils.quality.text import normalize_song_title

__all__ = [
    "artist_matches_reference",
    "artist_tokens",
    "diversity_artist_keys",
    "hard_anchor_names",
    "hard_references_in_artists",
    "is_arrangement",
    "is_compilation_artist",
    "is_functional_seo_track",
    "is_genre_descriptor_title",
    "is_genre_suffix_artist",
    "is_mood_keyword_artist",
    "is_mood_keyword_title",
    "is_production_spam_title",
    "is_spurious_track",
    "looks_like_seo_artist",
    "looks_like_seo_title",
    "normalize_song_title",
    "references_in_artists",
]
