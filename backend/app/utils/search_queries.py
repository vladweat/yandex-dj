"""Генерация и фильтрация поисковых фраз для каталога Яндекс Музыки."""

import re

from app.core.config import settings
from app.schemas.llm import MusicProfile

_GENERIC_PATTERNS = re.compile(
    r"\b("
    r"coding|programming|developer|code|"
    r"study\s+(music|beats)|focus\s+music|"
    r"workout(\s+playlist|\s+music)?|gym\s+music|running\s+playlist|cardio|"
    r"best\s+tracks|music\s+for|playlist"
    r")\b",
    re.IGNORECASE,
)


def is_generic_search_query(query: str) -> bool:
    """SEO-фразы вроде «coding music» плохо работают в каталоге."""
    return bool(_GENERIC_PATTERNS.search(query.strip()))


def refine_search_queries(profile: MusicProfile) -> MusicProfile:
    """Убрать generic-фразы, дополнить жанрами и артистами."""
    queries: list[str] = []
    seen: set[str] = set()

    def add(phrase: str) -> None:
        text = phrase.strip()
        if not text or is_generic_search_query(text):
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

    for genre in profile.primary_genres:
        add(genre)
        if profile.mood_tags:
            add(f"{genre} {profile.mood_tags[0]}")
        if profile.vocal_type == "instrumental_only":
            add(f"{genre} instrumental")

    for artist in profile.reference_artists[:4]:
        for genre in profile.primary_genres[:2]:
            add(f"{artist} {genre}")

    if len(queries) < 3:
        for tag in profile.mood_tags:
            add(tag)
            if len(queries) >= 3:
                break

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
        if not text or is_generic_search_query(text):
            return
        key = text.lower()
        if key in used:
            return
        used.add(key)
        result.append(text)

    if pass_num == 0:
        for artist in profile.reference_artists:
            add(artist)
        for genre in profile.primary_genres:
            add(genre)
            for mood in profile.mood_tags[:2]:
                add(f"{genre} {mood}")
            if profile.vocal_type == "instrumental_only":
                add(f"{genre} instrumental")
        for artist in profile.reference_artists[:4]:
            for genre in profile.primary_genres[:2]:
                add(f"{artist} {genre}")
    else:
        for mood in profile.mood_tags:
            for genre in profile.primary_genres:
                add(f"{mood} {genre}")
        for artist in profile.reference_artists:
            for mood in profile.mood_tags[:2]:
                add(f"{artist} {mood}")
        for artist in profile.reference_artists:
            add(f"{artist} popular")

    return result
