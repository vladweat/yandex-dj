"""Универсальная гигиена каталога — без привязки к жанру или промпту."""

import re

from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate

_ARRANGEMENT_MARKERS = re.compile(
    r"("
    r"\b(cover|covers|tribute|karaoke|remix|rework|bootleg|reprise|unplugged)\b|"
    r"\barr\.?\b|\barrangement\b|"
    r"\b(piano|guitar|orchestral|acoustic|violin)\s+version\b|"
    r"\blive\s+at\b|"
    r"\bfrom\s+[\u201c\"']|\bmusic\s+from\b|"
    r"\(arr\.|"
    r"[-–—]\s*(piano|guitar|orchestral|acoustic)\s+version"
    r")",
    re.IGNORECASE,
)

_COMPILATION_ARTIST = re.compile(
    r"\b(soundtrack|саундтрек|theme\s+orchestra|tribute\s+(to|band)|cover\s+band|karaoke)\b",
    re.IGNORECASE,
)

# Структурные шаблоны SEO-каталога (любой контекст: cooking, sleep, study, …).
_SEO_TITLE_FOR = re.compile(
    r"\b("
    r"vibe|vibes|sound|sounds|audio|ambience|ambient|beats?|mix|playlist|bgm|background"
    r")\s*for\b",
    re.IGNORECASE,
)
_SEO_TITLE_SUFFIX = re.compile(
    r"[-–—]\s*.+\s+for\s+\w",
    re.IGNORECASE,
)
_SEO_MUSIC_FOR = re.compile(r"\bmusic\s+for\b", re.IGNORECASE)

_SEO_ARTIST_STRUCTURAL = re.compile(
    r"("
    r"music\s*for\b|"
    r"\bmusic\s+playlist\b|"
    r"\b\w+\s+music\s+(playlist|moods?|universe|deluxe|lounge|beats?|ambience|bgm|"
    r"all-?stars?|classics?|vintage|orchestra)\b|"
    r"\b\w+\s+(jazz|beats?|piano|lo-?fi|chill|ambient)\s+(moods?|playlist|music)\b|"
    r"\b(jazz|beats?|piano|lo-?fi|chill|ambient)\s+(moods?|playlist|music)\b"
    r")",
    re.IGNORECASE,
)

_SEO_LABEL_ARTIST = re.compile(
    r"("
    r"\b\w+\s+sounds\b|"
    r"^\s*mood\w+\s*$|"
    r"^\s*\w*music\s*$|"
    r"^\s*\w+(mode|audio|beats)\s*$"
    r")",
    re.IGNORECASE,
)

_TITLE_STOPWORDS = frozenset({"a", "an", "the", "of", "and", "la", "le", "de", "el", "y", "i", "to"})

_GENRE_TOKENS = frozenset(
    {
        "indie",
        "pop",
        "rock",
        "jazz",
        "hop",
        "hip",
        "hiphop",
        "lofi",
        "lo",
        "fi",
        "chill",
        "bossa",
        "nova",
        "electronic",
        "electro",
        "ambient",
        "classical",
        "piano",
        "soul",
        "folk",
        "funk",
        "disco",
        "house",
        "techno",
        "metal",
        "punk",
        "rap",
        "rnb",
        "country",
        "blues",
        "reggae",
        "synth",
        "wave",
        "trap",
        "downtempo",
        "instrumental",
        "acoustic",
        "alternative",
        "alt",
        "edm",
        "trance",
        "dubstep",
        "garage",
        "grunge",
        "cinematic",
    }
)

_DESCRIPTOR_TOKENS = _GENRE_TOKENS | frozenset(
    {
        "upbeat",
        "happy",
        "modern",
        "cozy",
        "relaxing",
        "calm",
        "soft",
        "deep",
        "light",
        "smooth",
        "stylish",
        "cool",
        "warm",
        "dreamy",
        "gentle",
        "lifestyle",
        "mood",
        "vibe",
        "vibes",
        "beautiful",
        "perfect",
        "best",
        "fresh",
        "easy",
        "slow",
        "fast",
        "energetic",
        "peaceful",
        "romantic",
        "summer",
        "winter",
        "night",
        "day",
        "retro",
        "vintage",
        "classic",
        "contemporary",
        "premium",
        "ultimate",
        "pure",
        "true",
        "real",
        "inspiring",
        "inspired",
        "groovy",
        "groove",
        "lovely",
        "sweet",
        "chillout",
        "laid",
        "back",
    }
)

_SEO_ARTIST_TOKENS = frozenset(
    {
        "music",
        "for",
        "vibe",
        "vibes",
        "playlist",
        "ambience",
        "ambient",
        "bgm",
        "lounge",
        "background",
        "moods",
        "mood",
        "universe",
        "deluxe",
        "beats",
        "beat",
        "all",
        "stars",
        "classics",
        "vintage",
        "orchestra",
        "soundtrack",
    }
)


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9а-яё]", "", text.lower())


def _tokenize_name(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _title_tokens(title: str) -> list[str]:
    normalized = re.sub(r"[\(\[].*?[\)\]]", "", title.lower())
    normalized = re.sub(r"[-–—/]", " ", normalized)
    tokens: list[str] = []
    for part in re.findall(r"[\w]+", normalized, flags=re.UNICODE):
        token = part.lower()
        if token and token not in _TITLE_STOPWORDS:
            tokens.append(token)
    return tokens


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
    ref_compact = _compact(ref_lower)
    for part in _artist_name_parts(artist):
        if part == ref_lower:
            return True
        if _compact(part) == ref_compact:
            return True
    return False


def references_in_artists(track: TrackCandidate, profile: MusicProfile) -> bool:
    artists = artist_tokens(track)
    for ref in profile.reference_artists:
        if any(artist_matches_reference(artist, ref.lower()) for artist in artists):
            return True
    return False


def is_arrangement(track: TrackCandidate) -> bool:
    haystack = f"{track.title} {track.version}".strip()
    return bool(_ARRANGEMENT_MARKERS.search(haystack))


def is_compilation_artist(track: TrackCandidate) -> bool:
    """Исполнитель-заглушка (soundtrack orchestra и т.п.) — для любого жанра."""
    for name in track.artists:
        if _COMPILATION_ARTIST.search(name):
            return True
    return False


def is_genre_descriptor_title(title: str) -> bool:
    """Название = стек жанров/прилагательных без собственного имени («Upbeat Indie Pop»)."""
    tokens = _title_tokens(title)
    if not tokens:
        return False
    if len(tokens) == 1:
        return tokens[0] in _GENRE_TOKENS

    # «Indie Mindy», «Indie Lovers» — жанр + случайное слово.
    if len(tokens) == 2 and tokens[0] in _GENRE_TOKENS:
        return True

    genre_count = sum(1 for token in tokens if token in _GENRE_TOKENS)
    descriptor_count = sum(1 for token in tokens if token in _DESCRIPTOR_TOKENS)

    if descriptor_count == len(tokens):
        return True

    # «Indie Pop Groove», «Pop Rock» — короткий стек жанров.
    if genre_count >= 2 and len(tokens) <= 5:
        return True

    # «Inspiring Indie Pop» — маркетинг + жанр, одно «чужое» слово максимум.
    non_descriptor = [token for token in tokens if token not in _DESCRIPTOR_TOKENS]
    if genre_count >= 1 and descriptor_count >= 2 and len(non_descriptor) <= 1 and len(tokens) <= 4:
        return True

    return False


def looks_like_seo_artist(name: str) -> bool:
    """Исполнитель похож на SEO-лейбл, а не на реальную группу."""
    if _SEO_LABEL_ARTIST.search(name):
        return True
    if _SEO_ARTIST_STRUCTURAL.search(name):
        return True

    tokens = _tokenize_name(name)
    if len(tokens) == 2 and tokens[1] == "music":
        return True

    if len(tokens) >= 3:
        hits = sum(1 for token in tokens if token in _SEO_ARTIST_TOKENS)
        if hits >= 2 and hits / len(tokens) >= 0.4:
            return True

    return "music" in tokens and "for" in tokens


def looks_like_seo_title(title: str, artists: list[str]) -> bool:
    """SEO-шаблон в названии: «… - Vibe for …», «Sounds for …» и т.п."""
    if _SEO_TITLE_FOR.search(title):
        return True
    if _SEO_TITLE_SUFFIX.search(title):
        return True
    # «Music for Airports» у Brian Eno — ок; «Music for …» + SEO-артист — мусор.
    if _SEO_MUSIC_FOR.search(title):
        return any(looks_like_seo_artist(name) for name in artists)
    return False


def is_functional_seo_track(track: TrackCandidate) -> bool:
    """SEO-мусор каталога: functional «vibe for», genre-as-title, лейблы-заглушки."""
    haystack = f"{track.title} {track.version}".strip()
    if looks_like_seo_title(haystack, track.artists):
        return True
    if is_genre_descriptor_title(track.title):
        return True
    return any(looks_like_seo_artist(name) for name in track.artists)


def _title_resembles_reference(title: str, reference: str) -> bool:
    title_lower = title.lower().strip()
    ref_lower = reference.lower().strip()
    if title_lower == ref_lower:
        return True
    title_compact = _compact(title_lower)
    ref_compact = _compact(ref_lower)
    if title_compact == ref_compact:
        return True
    if ref_lower in title_lower or ref_compact in title_compact:
        return True
    # «Parcel» при якоре «Parcels» — keyword spam в title.
    if len(title_compact) >= 4 and title_compact in ref_compact:
        return len(title_compact) / len(ref_compact) >= 0.75
    return False


def is_mood_keyword_title(title: str) -> bool:
    """SEO-title с mood-словом: «Cozy Forever», «Chill Vibes»."""
    tokens = _title_tokens(title)
    if len(tokens) < 2:
        return False
    mood_starters = {
        "cozy",
        "chill",
        "vibe",
        "vibes",
        "mood",
        "sleep",
        "relax",
        "calm",
        "lofi",
    }
    return tokens[0] in mood_starters


def is_genre_suffix_artist(name: str) -> bool:
    """Лейбл-заглушка «Waco Texas Metal» — жанр в конце имени."""
    tokens = _tokenize_name(name)
    return len(tokens) >= 3 and tokens[-1] in _GENRE_TOKENS


def is_mood_keyword_artist(name: str) -> bool:
    """Артист-заглушка под mood-слово: Cozy', COZY YiELDS."""
    tokens = _tokenize_name(name)
    if not tokens or len(tokens) > 3:
        return False
    mood_names = {
        "cozy",
        "chill",
        "vibe",
        "vibes",
        "mood",
        "sleep",
        "relax",
        "calm",
        "lofi",
    }
    return tokens[0] in mood_names


def _reference_in_title_only(track: TrackCandidate, profile: MusicProfile) -> bool:
    """Имя reference artist в title, но не среди исполнителей."""
    if references_in_artists(track, profile):
        return False

    for ref in profile.reference_artists:
        if _title_resembles_reference(track.title, ref):
            return True

    return False


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
    if _reference_in_title_only(track, profile):
        return True
    return False


def normalize_song_title(title: str) -> str:
    """Базовое название без суффиксов «- Artist», скобок и т.п."""
    normalized = title.lower().strip()
    normalized = re.sub(r"\s*[\(\[].*?[\)\]]", "", normalized)
    normalized = re.sub(r"\s+[-–—]\s+.+$", "", normalized)
    return normalized.strip()
