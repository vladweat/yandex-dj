# Схема LLM-вывода (MusicProfile)

Модель `MusicProfile` — контракт между LLM Engine и остальным пайплайном (см. ТЗ §6.1).

## JSON-пример

```json
{
  "playlist_title": "Неоновый дождь",
  "playlist_description": "Мрачный синтвейв и пост-панк для ночной поездки под дождём",
  "primary_genres": ["synthwave", "post-punk", "darkwave"],
  "mood_tags": ["melancholic", "atmospheric", "nocturnal"],
  "vocal_type": "instrumental_only",
  "reference_artists": ["Molchat Doma", "Kavinsky", "Boy Harsher", "The Cure"],
  "search_queries": [
    "synthwave instrumental",
    "post-punk melancholic",
    "retrowave night drive"
  ],
  "target_track_count": 25
}
```

## Pydantic-модель

```python
from typing import List
from pydantic import BaseModel, Field


class MusicProfile(BaseModel):
    playlist_title: str = Field(
        description="Креативное, цепляющее название плейлиста (2-4 слова)"
    )
    playlist_description: str = Field(
        description="Короткое описание атмосферы плейлиста"
    )
    primary_genres: List[str] = Field(
        description="Основные жанры (например: 'indie-rock', 'synthwave', 'ambient')"
    )
    mood_tags: List[str] = Field(
        description="Эмоциональные теги (например: 'melancholic', 'energetic', 'dark')"
    )
    vocal_type: str = Field(
        description="Тип вокала: 'any' | 'instrumental_only' | 'vocal_only'"
    )
    reference_artists: List[str] = Field(
        min_length=4,
        max_length=8,
        description="4-8 артистов, задающих эталонное звучание"
    )
    search_queries: List[str] = Field(
        min_length=3,
        max_length=5,
        description="3-5 фраз для поискового движка"
    )
    target_track_count: int = Field(
        default=25,
        description="Желаемое количество треков"
    )
```

## Поля и использование в пайплайне

| Поле | Используется в |
|------|----------------|
| `playlist_title` | `users_playlists_create(title=...)` |
| `playlist_description` | Описание плейлиста + ответ API |
| `primary_genres` | Fallback-скоринг, обогащение паспорта трека |
| `mood_tags` | Fallback-скоринг, системный контекст для embeddings |
| `vocal_type` | Пост-фильтрация (backlog: audio VAD) |
| `reference_artists` | `artists_tracks()` — топ-10 на артиста |
| `search_queries` | `client.search()` — параллельно |
| `target_track_count` | Топ-N в Scoring, лимиты diversity |

## Системный промпт (шаблон)

```
Ты — музыкальный куратор. Пользователь описывает желаемый плейлист
свободным текстом. Разложи запрос в структурированный профиль
для поиска в каталоге Яндекс Музыки.

Правила:
- search_queries: 3–5 конкретных фраз (русский или английский)
- reference_artists: 4–8 реальных артистов, узнаваемых в каталоге
- playlist_title: 2–4 слова на языке запроса
- playlist_description: 1–2 предложения об атмосфере
- primary_genres / mood_tags: на английском
- vocal_type: instrumental_only — если явно просят без вокала
- target_track_count: из запроса пользователя или 25 по умолчанию
```

## Интеграция с instructor

```python
import instructor
from openai import OpenAI

client = instructor.from_openai(OpenAI())

profile = client.chat.completions.create(
    model="gpt-4o-mini",
    response_model=MusicProfile,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ],
)
```

## Примеры

### «спокойная музыка для кодинга поздней ночью, эмбиент и лоу-фай без слов»

```json
{
  "playlist_title": "Ночной фокус",
  "playlist_description": "Спокойный эмбиент и лоу-фай для глубокой концентрации",
  "primary_genres": ["ambient", "lo-fi", "downtempo"],
  "mood_tags": ["calm", "focused", "nocturnal", "minimal"],
  "vocal_type": "instrumental_only",
  "reference_artists": ["Tycho", "Nujabes", "Bonobo", "Helios"],
  "search_queries": [
    "lo-fi beats study",
    "ambient coding night",
    "instrumental chill focus"
  ],
  "target_track_count": 25
}
```

### «музыка для тренировки с разгоном темпа»

```json
{
  "playlist_title": "Разгон пульса",
  "playlist_description": "Энергичная электроника с нарастающим темпом для тренировки",
  "primary_genres": ["electronic", "house", "drum and bass"],
  "mood_tags": ["energetic", "driving", "motivating"],
  "vocal_type": "any",
  "reference_artists": ["The Chemical Brothers", "Disclosure", "Pendulum", "Fatboy Slim"],
  "search_queries": [
    "workout electronic energetic",
    "running playlist upbeat",
    "cardio drum and bass"
  ],
  "target_track_count": 30
}
```

## Валидация и retry

1. Pydantic v2 валидирует ответ LLM
2. При ошибке — retry через `instructor` (до 2 раз) с текстом ошибки
3. Если `search_queries` < 3 — дополнить из `primary_genres` + `mood_tags`
