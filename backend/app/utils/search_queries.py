"""Генерация и фильтрация поисковых фраз для каталога Яндекс Музыки."""

import re

from app.core.config import settings
from app.schemas.llm import MusicProfile
from app.utils.mood_tokens import MOOD_SEARCH_BAIT_TOKENS

# Структурные SEO-фразы (не список контекстов вроде cooking/sleep).
_GENERIC_PATTERNS = re.compile(
    r"("
    r"\b(coding|programming|developer|code)\b|"
    r"\b(study|focus|workout|gym|running|cardio|meditation|yoga|relaxation)\s+"
    r"(music|beats?|playlist)\b|"
    r"\b(music|vibe|vibes|sound|sounds|audio|ambience|ambient|beats?|bgm)\s+for\b|"
    r"\bfor\s+(cooking|kitchen|sleep|study|work|focus|relax|meditation|yoga|"
    r"workout|gym|restaurants?|coffee|driving|reading)\b|"
    r"\bbest\s+tracks\b|"
    r"\b\w+\s+music\s+(playlist|moods?)\b|"
    r"\bplaylist\b|"
    r"\b(bossa\s+nova|lo-?fi|jazz|chill|ambient|electronic|classical|piano|synth)\s+"
    r"(cooking|cleaning|sleeping|studying|working|driving|reading|meditation|workout)\b"
    r")",
    re.IGNORECASE,
)

# Mood в search тянет SEO-title («Sad Rap», «Bones sad»). Scene-adj (dark/atmospheric/…)
# не режем — lexicon: app.utils.mood_tokens.MOOD_SEARCH_BAIT_TOKENS.

_GENRE_BAIT_TOKENS = frozenset(
    {
        "rap",
        "hip",
        "hop",
        "hiphop",
        "trap",
        "emo",
        "punk",
        "metal",
        "jazz",
        "pop",
        "rock",
        "rnb",
        "soul",
        "house",
        "techno",
        "ambient",
        "lofi",
        "indie",
        "folk",
        "blues",
        "reggae",
        "drill",
        "phonk",
        "electronic",
        "electro",
        "synth",
        "wave",
        "synthwave",
        "retrowave",
        "downtempo",
        "instrumental",
        "acoustic",
        "alternative",
        "edm",
        "trance",
        "dubstep",
        "garage",
        "grunge",
        "cinematic",
        "disco",
        "funk",
        "country",
        "classical",
        "piano",
        "bossa",
        "nova",
        "chillhop",
        "cloud",
    }
)


def _query_tokens(query: str) -> list[str]:
    normalized = query.lower().replace("lo-fi", "lofi").replace("hip-hop", "hiphop")
    return re.findall(r"[a-z0-9$]+", normalized)


def is_generic_search_query(query: str) -> bool:
    """SEO-фразы вроде «coding music» / «vibe for sleep» плохо работают в каталоге."""
    return bool(_GENERIC_PATTERNS.search(query.strip()))


def is_mood_bait_search_query(query: str) -> bool:
    """Artist+mood или mood+genre bait («Bones sad rap», «sad rap», «emotional trap»)."""
    tokens = _query_tokens(query)
    if len(tokens) < 2:
        return False

    mood_hits = [token for token in tokens if token in MOOD_SEARCH_BAIT_TOKENS]
    genre_hits = [token for token in tokens if token in _GENRE_BAIT_TOKENS]
    if mood_hits and genre_hits:
        return True
    # «Bones sad», «$uicideboy$ emotional», «Men I Trust cozy»
    if tokens[-1] in MOOD_SEARCH_BAIT_TOKENS:
        return True
    return False


def is_genre_only_search_query(query: str) -> bool:
    """
    Чистый жанровый ярлык без артиста («emo rap», «indie pop», «ambient»).
    В каталоге Яндекса тянет SEO/плейлист-мусор; артист+жанр — ок.
    """
    tokens = _query_tokens(query)
    if not tokens:
        return False
    return all(token in _GENRE_BAIT_TOKENS for token in tokens)


def is_rejected_search_query(query: str) -> bool:
    """Любая поисковая фраза, которую не стоит слать в каталог."""
    return (
        is_generic_search_query(query)
        or is_mood_bait_search_query(query)
        or is_genre_only_search_query(query)
    )


def refine_search_queries(profile: MusicProfile) -> MusicProfile:
    """Убрать generic/mood/genre-only фразы; опираться на артистов и artist+genre."""
    queries: list[str] = []
    seen: set[str] = set()

    def add(phrase: str) -> None:
        text = phrase.strip()
        if not text or is_rejected_search_query(text):
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        queries.append(text)

    for query in profile.search_queries:
        add(query)

    for artist in profile.reference_artists:
        add(artist)

    # Не добавляем голый primary_genres — is_genre_only. Только artist + genre.
    for artist in profile.reference_artists[:4]:
        for genre in profile.primary_genres[:2]:
            add(f"{artist} {genre}")
            if profile.vocal_type == "instrumental_only":
                add(f"{artist} {genre} instrumental")

    if len(queries) < 3:
        for artist in profile.reference_artists:
            add(f"artists like {artist}")
            if len(queries) >= 3:
                break

    if not queries:
        # Последний шанс: сырые artist names без фильтра mood (имена сами по себе ок).
        for artist in profile.reference_artists[:5]:
            text = artist.strip()
            if text and text.lower() not in seen:
                seen.add(text.lower())
                queries.append(text)

    if not queries:
        queries = [q for q in profile.search_queries[:5] if not is_rejected_search_query(q)]
        if not queries:
            queries = list(profile.search_queries[:5])

    return profile.model_copy(update={"search_queries": queries[:5]})


def expand_search_queries(
    profile: MusicProfile,
    *,
    used: set[str],
    pass_num: int = 0,
    limit: int | None = None,
) -> list[str]:
    """Дополнительные фразы при маленьком пуле (ARCHITECTURE.md)."""
    max_queries = limit or settings.search_expand_max_queries
    result: list[str] = []

    def add(phrase: str) -> None:
        if len(result) >= max_queries:
            return
        text = phrase.strip()
        if not text or is_rejected_search_query(text):
            return
        key = text.lower()
        if key in used:
            return
        used.add(key)
        result.append(text)

    if pass_num == 0:
        for artist in profile.reference_artists:
            add(artist)
        for artist in profile.reference_artists[:4]:
            for genre in profile.primary_genres[:2]:
                add(f"{artist} {genre}")
                if profile.vocal_type == "instrumental_only":
                    add(f"{artist} {genre} instrumental")
    else:
        for artist in profile.reference_artists:
            add(f"artists like {artist}")
            add(f"{artist} popular")
        for artist in profile.reference_artists[:3]:
            for genre in profile.primary_genres[:2]:
                add(f"{artist} {genre}")

    return result
