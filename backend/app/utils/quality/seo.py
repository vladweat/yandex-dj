"""SEO-шаблоны каталога: genre-as-title, mood-keyword, type beat."""

from app.schemas.track import TrackCandidate
from app.utils.quality.patterns import (
    DESCRIPTOR_TOKENS,
    GENRE_PREFIX_NOISE,
    GENRE_TOKENS,
    MOOD_KEYWORD_TOKENS,
    SEO_ARTIST_STRUCTURAL,
    SEO_ARTIST_TOKENS,
    SEO_LABEL_ARTIST,
    SEO_MUSIC_FOR,
    SEO_TITLE_FOR,
    SEO_TITLE_SUFFIX,
    TYPE_BEAT,
)
from app.utils.quality.text import title_tokens, tokenize_name


def is_genre_descriptor_title(title: str) -> bool:
    """Название = стек жанров/прилагательных без собственного имени («Upbeat Indie Pop»)."""
    tokens = title_tokens(title)
    if not tokens:
        return False
    if len(tokens) == 1:
        return tokens[0] in GENRE_TOKENS

    if len(tokens) == 2 and tokens[0] in GENRE_TOKENS:
        return True

    if len(tokens) == 2 and tokens[0] in DESCRIPTOR_TOKENS and tokens[1] in GENRE_TOKENS:
        return True

    genre_count = sum(1 for token in tokens if token in GENRE_TOKENS)
    descriptor_count = sum(1 for token in tokens if token in DESCRIPTOR_TOKENS)

    if descriptor_count == len(tokens):
        return True

    if genre_count >= 2 and len(tokens) <= 5:
        return True

    non_descriptor = [token for token in tokens if token not in DESCRIPTOR_TOKENS]
    if genre_count >= 1 and descriptor_count >= 2 and len(non_descriptor) <= 1 and len(tokens) <= 4:
        return True

    if (
        2 <= len(tokens) <= 3
        and tokens[-1] in GENRE_TOKENS
        and all(token in GENRE_PREFIX_NOISE or token in GENRE_TOKENS for token in tokens)
    ):
        return True

    if genre_count >= 2 and len(tokens) >= 3:
        distinctive = [
            token
            for token in tokens
            if token not in DESCRIPTOR_TOKENS and token not in GENRE_TOKENS
        ]
        if len(distinctive) <= 2:
            return True

    return False


def is_production_spam_title(title: str) -> bool:
    """Beat-store / type beat SEO в названии (любой жанр)."""
    return bool(TYPE_BEAT.search(title))


def looks_like_seo_artist(name: str) -> bool:
    """Исполнитель похож на SEO-лейбл, а не на реальную группу."""
    if SEO_LABEL_ARTIST.search(name):
        return True
    if SEO_ARTIST_STRUCTURAL.search(name):
        return True

    tokens = tokenize_name(name)
    if len(tokens) == 2 and tokens[1] == "music":
        return True

    if len(tokens) >= 3:
        hits = sum(1 for token in tokens if token in SEO_ARTIST_TOKENS)
        if hits >= 2 and hits / len(tokens) >= 0.4:
            return True

    return "music" in tokens and "for" in tokens


def looks_like_seo_title(title: str, artists: list[str]) -> bool:
    """SEO-шаблон в названии: «… - Vibe for …», «Sounds for …» и т.п."""
    if SEO_TITLE_FOR.search(title):
        return True
    if SEO_TITLE_SUFFIX.search(title):
        return True
    if SEO_MUSIC_FOR.search(title):
        return any(looks_like_seo_artist(name) for name in artists)
    return False


def is_functional_seo_track(track: TrackCandidate) -> bool:
    """SEO-мусор каталога: functional «vibe for», genre-as-title, type beat, лейблы."""
    haystack = f"{track.title} {track.version}".strip()
    if looks_like_seo_title(haystack, track.artists):
        return True
    if is_production_spam_title(haystack):
        return True
    if is_genre_descriptor_title(track.title):
        return True
    return any(looks_like_seo_artist(name) for name in track.artists)


def is_mood_keyword_title(title: str) -> bool:
    """SEO-title с mood-словом: «Cozy Forever», «Chill Vibes», «Sad Vibes»."""
    tokens = title_tokens(title)
    if len(tokens) < 2:
        return False
    return tokens[0] in MOOD_KEYWORD_TOKENS


def is_genre_suffix_artist(name: str) -> bool:
    """Лейбл-заглушка «Waco Texas Metal» — жанр в конце имени."""
    tokens = tokenize_name(name)
    return len(tokens) >= 3 and tokens[-1] in GENRE_TOKENS


def is_mood_keyword_artist(name: str) -> bool:
    """Артист-заглушка под mood-слово: Cozy', COZY YiELDS, Melancholy Mø."""
    tokens = tokenize_name(name)
    if not tokens or len(tokens) > 3:
        return False
    return tokens[0] in MOOD_KEYWORD_TOKENS
