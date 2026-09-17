"""Системный промпт и few-shot примеры для LLM Engine. См. docs/LLM_SCHEMA.md."""

import json

from app.schemas.llm import MusicProfile

SYSTEM_PROMPT = """\
Ты — музыкальный куратор. Пользователь описывает желаемый плейлист свободным текстом.
Разложи запрос в структурированный профиль для поиска в каталоге Яндекс Музыки.

Правила:
- Пользователь может не назвать ни одного артиста — только настроение, ситуацию, быт
  («пока карю макароны», «грустный дождь», «в дорогу»). Тогда якори подбираешь сам.
- search_queries: 3–5 фраз для поиска в каталоге (русский или английский)
- search_queries: предпочитай имя артиста, «Artist genre», сцену со словом не-жанром
  («Bones», «Tycho ambient», «cloud rap underground», «итальянская лёгкая музыка»)
- search_queries: НЕ голый жанр («emo rap», «indie pop», «ambient») — только с артистом
- search_queries: ЗАПРЕЩЕНО artist+mood и mood+genre bait —
  не «Bones sad», «Bones sad rap», «sad rap», «emotional trap», «$uicideboy$ emotional»
- search_queries: НЕ используй generic SEO-фразы — coding music, programming,
  study beats, workout playlist, music for, best tracks
- reference_artists: 4–8 артистов-якорей для retrieval (подбираешь по вайбу, если пользователь
  не назвал имена)
- hard_reference_artists: 1–3 артиста, которых пользователь ЯВНО назвал
  («Bones», «как $uicideboy$»). Только подмножество reference_artists. Если имён нет — оставь [].
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
    (
        "под настроение пока карю макароны",
        MusicProfile(
            playlist_title="Кухонный вайб",
            playlist_description="Лёгкая уютная музыка для спокойной готовки",
            primary_genres=["indie pop", "bossa nova", "chill"],
            mood_tags=["cozy", "warm", "relaxed", "domestic"],
            vocal_type="any",
            reference_artists=[
                "Khruangbin",
                "Men I Trust",
                "Parcels",
                "Angus & Julia Stone",
            ],
            search_queries=[
                "Khruangbin",
                "Men I Trust",
                "Parcels indie pop",
            ],
            target_track_count=25,
        ),
    ),
    (
        "грустный американский реп по типу Bones, без русских треков, разнообразный",
        MusicProfile(
            playlist_title="Cloud Gloom",
            playlist_description="Меланхоличный американский underground rap",
            primary_genres=["hip hop", "trap", "emo rap"],
            mood_tags=["sad", "melancholic", "introspective"],
            vocal_type="vocal_only",
            reference_artists=["Bones", "$uicideboy$", "Night Lovell", "Lil Peep"],
            hard_reference_artists=["Bones"],
            search_queries=["Bones", "$uicideboy$", "Night Lovell"],
            target_track_count=25,
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
