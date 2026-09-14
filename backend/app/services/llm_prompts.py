"""Системный промпт и few-shot примеры для LLM Engine. См. docs/LLM_SCHEMA.md."""

import json

from app.schemas.llm import MusicProfile

SYSTEM_PROMPT = """\
Ты — музыкальный куратор. Пользователь описывает желаемый плейлист свободным текстом.
Разложи запрос в структурированный профиль для поиска в каталоге Яндекс Музыки.

Правила:
- search_queries: 3–5 фраз для поиска треков в каталоге (русский или английский)
- search_queries: называй жанры, стили, имена артистов и характерные сочетания
  («Tycho ambient», «lo-fi hip hop instrumental», «post-punk dark»)
- search_queries: НЕ используй generic SEO-фразы — coding music, programming,
  study beats, workout playlist, music for, best tracks
- Включи минимум 2 фразы с именами артистов из reference_artists
- reference_artists: 4–8 реальных артистов, узнаваемых в каталоге
- playlist_title: 2–4 слова на языке запроса
- playlist_description: 1–2 предложения об атмосфере
- primary_genres / mood_tags: на английском
- vocal_type: instrumental_only — если явно просят без вокала; vocal_only — только вокал
- target_track_count: из запроса пользователя или 25 по умолчанию
"""

FEW_SHOT_EXAMPLES: list[tuple[str, MusicProfile]] = [
    (
        "спокойная музыка для кодинга поздней ночью, эмбиент и лоу-фай без слов",
        MusicProfile(
            playlist_title="Ночной фокус",
            playlist_description="Спокойный эмбиент и лоу-фай для глубокой концентрации",
            primary_genres=["ambient", "lo-fi", "downtempo"],
            mood_tags=["calm", "focused", "nocturnal", "minimal"],
            vocal_type="instrumental_only",
            reference_artists=["Tycho", "Nujabes", "Bonobo", "Helios"],
            search_queries=[
                "Tycho ambient instrumental",
                "Nujabes chillhop",
                "lo-fi hip hop instrumental",
            ],
            target_track_count=25,
        ),
    ),
    (
        "музыка для тренировки с разгоном темпа",
        MusicProfile(
            playlist_title="Разгон пульса",
            playlist_description="Энергичная электроника с нарастающим темпом для тренировки",
            primary_genres=["electronic", "house", "drum and bass"],
            mood_tags=["energetic", "driving", "motivating"],
            vocal_type="any",
            reference_artists=[
                "The Chemical Brothers",
                "Disclosure",
                "Pendulum",
                "Fatboy Slim",
            ],
            search_queries=[
                "The Chemical Brothers electronic",
                "Disclosure house",
                "Pendulum drum and bass",
            ],
            target_track_count=30,
        ),
    ),
]


def build_messages(user_prompt: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for example_prompt, profile in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": example_prompt})
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(profile.model_dump(), ensure_ascii=False),
            }
        )
    messages.append({"role": "user", "content": user_prompt})
    return messages
