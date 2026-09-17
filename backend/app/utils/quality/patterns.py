"""Regex и словари для pre-filter каталога."""

import re

ARRANGEMENT_MARKERS = re.compile(
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

COMPILATION_ARTIST = re.compile(
    r"\b(soundtrack|саундтрек|theme\s+orchestra|tribute\s+(to|band)|cover\s+band|karaoke)\b",
    re.IGNORECASE,
)

SEO_TITLE_FOR = re.compile(
    r"\b("
    r"vibe|vibes|sound|sounds|audio|ambience|ambient|beats?|mix|playlist|bgm|background"
    r")\s*for\b",
    re.IGNORECASE,
)
SEO_TITLE_SUFFIX = re.compile(
    r"[-–—]\s*.+\s+for\s+\w",
    re.IGNORECASE,
)
SEO_MUSIC_FOR = re.compile(r"\bmusic\s+for\b", re.IGNORECASE)

SEO_ARTIST_STRUCTURAL = re.compile(
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

SEO_LABEL_ARTIST = re.compile(
    r"("
    r"\b\w+\s+sounds\b|"
    r"^\s*mood\w+\s*$|"
    r"^\s*\w*music\s*$|"
    r"^\s*\w+(mode|audio|beats)\s*$"
    r")",
    re.IGNORECASE,
)

TITLE_STOPWORDS = frozenset(
    {"a", "an", "the", "of", "and", "la", "le", "de", "el", "y", "i", "to", "for"}
)

GENRE_TOKENS = frozenset(
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
        "emo",
        "phonk",
        "drill",
        "beat",
        "beats",
    }
)

DESCRIPTOR_TOKENS = GENRE_TOKENS | frozenset(
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
        "sad",
        "emotional",
        "melancholic",
        "melancholy",
        "introspective",
        "depressing",
        "depressed",
        "lonely",
        "heartbreak",
        "heartbreaking",
        "moody",
        "nostalgic",
        "atmospheric",
        "dark",
        "emo",
        "est",
        "get",
        "top",
        "hot",
        "new",
    }
)

MOOD_KEYWORD_TOKENS = frozenset(
    {
        "cozy",
        "chill",
        "vibe",
        "vibes",
        "mood",
        "sleep",
        "relax",
        "calm",
        "lofi",
        "sad",
        "emotional",
        "melancholic",
        "melancholy",
        "introspective",
        "depressing",
        "depressed",
        "lonely",
        "heartbreak",
        "moody",
        "nostalgic",
        "atmospheric",
    }
)

GENRE_PREFIX_NOISE = frozenset(
    {
        "get",
        "est",
        "best",
        "top",
        "hot",
        "new",
        "real",
        "true",
        "pure",
        "ultimate",
        "fresh",
        "free",
    }
)

TYPE_BEAT = re.compile(
    r"\b("
    r"type\s*beats?|"
    r"free\s*beats?|"
    r"beat\s*tape|"
    r"instrumental\s+type"
    r")\b",
    re.IGNORECASE,
)

SEO_ARTIST_TOKENS = frozenset(
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
