# Архитектура Prompt DJ

Соответствует [SPEC.md](SPEC.md) §3.

## Модули системы

| Модуль | Код | Ответственность | Вход | Выход |
|--------|-----|-----------------|------|-------|
| Prompt Understanding | `services/llm_service.py` | Декомпозиция NL-запроса | Промпт | `MusicProfile` |
| Candidate Retrieval | `services/retrieval_service.py` | Сбор пула через API | `MusicProfile` | 150–300 `TrackCandidate` |
| Scoring & Ranking | `services/scoring_service.py` + `utils/scoring.py` | Векторный скоринг | Промпт + кандидаты | `list[ScoredTrack]` |
| Playlist Builder | `services/yandex_music_service.py` | Создание плейлиста | Топ-N треков | URL плейлиста |
| Auth & Sessions | `services/` + `api/.../auth` | Device Flow, шифрование токенов | — | `session_id` |
| API | `api/v1/endpoints/` | FastAPI endpoints | HTTP | JSON |
| Pipeline | `services/playlist_service.py` | Оркестрация generate | Промпт + опции | `PlaylistGenerateResponse` |

## Пайплайн

```
[Пользователь] ──> (Промпт + session_id)
                         │
                         ▼
              ┌──────────────────────┐
              │ 1. LLM Engine       │  2–3 сек
              │    → MusicProfile    │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 2. Retrieval        │  2–4 сек (async)
              │    → 150–300 tracks  │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 3. Scoring          │  1–2 сек
              │    → топ-N           │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 4. Export           │  1–2 сек
              │    → playlist_url    │
              └──────────────────────┘
```

**Целевой latency:** 7–12 сек.

## Слой данных

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ PostgreSQL  │     │    Redis    │     │  yandex-    │
│    15       │     │  кэш track  │     │  music API  │
│             │     │  metadata   │     │             │
│  users      │     │  (этап 3)   │     │             │
│  tokens (*) │     │             │     │             │
│  sessions   │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘

(*) токены зашифрованы Fernet; ORM — SQLAlchemy
```

## Этап 1: LLM Engine

- Pydantic `MusicProfile` + `instructor`
- Провайдер: OpenAI API (`openai` SDK, `gpt-4o-mini`) + `instructor`
- Схема: [LLM_SCHEMA.md](LLM_SCHEMA.md)

## Этап 2: Candidate Retrieval

Параллельно (`asyncio`):

| Источник | API | Лимит |
|----------|-----|-------|
| Поисковые фразы | `client.search(type_='track')` | все `search_queries` |
| Референсные артисты | `client.artists_tracks` | топ-N (`artist_tracks_limit`, default 20) |
| Эталонный трек | `client.tracks_similar` | если указан в промпте |

**Нормализация:**
- Дедуп по `track.id`
- Дедуп по «Артист + Название»
- Исключить `available == False`
- Кэш метаданных в Redis (TTL 24h)

## Этап 3: Scoring & Ranking

**Паспорт трека (SPEC §4.4):**
```
Название: {title}. Исполнитель: {artists}. Альбом: {album}. Жанр: {genre}. Версия: {version}
```

Для embedding используется компактная форма `embedding_passport()` — `{title}. {artists}. {genre}` (меньше токенов, быстрее encode).

**Алгоритм:**
1. Pre-filter SEO/мусор (`quality.py`) → clean-пул
2. Batch-эмбеддинг query + паспортов (`sentence-transformers`, E5 `query:` / `passage:`); `SCORING_EMBED_LIMIT=0` = весь пул
3. Cosine similarity (`numpy`) + soft reference anchor boost (+0.03)
4. Select: top-median gap → elbow → soft/tail fill → diversity + cap якорей ~60%
5. Warmup модели при старте API (`lifespan`)

**Diversity:**
| Режим | Max треков на артиста |
|-------|----------------------|
| normal | `MAX_TRACKS_PER_ARTIST` (env, default 2); якоря 3 / fill 5; суммарный cap ~60% |
| high | 1; якоря 2 / fill 3 |

**Fallback** (embeddings недоступны): совпадение `primary_genres` + reference artists + порядок retrieval как прокси популярности.

**Модель:** `intfloat/multilingual-e5-base` (см. [STACK.md](STACK.md)).

## Этап 4: Export

1. `users_playlists_create(title=profile.playlist_title)`
2. `users_playlists_insert_track()` — в порядке score
3. Описание: `profile.playlist_description` + исходный промпт
4. URL: `https://music.yandex.ru/users/{login}/playlists/{kind}`

## Интерфейсы

| Интерфейс | Стек | Приоритет |
|-----------|------|-----------|
| Web | Next.js 15 + Tailwind 4 + shadcn | **Основной UI** (каркас из docwise) |
| REST API | FastAPI + uvicorn | Контракт для UI и интеграций |
| CLI | click | Отладка, разорванный Device Flow |
| Telegram | aiogram 3.x | PRODUCT P1.1 ([PRODUCT.md](PRODUCT.md)) |

API-контракты: [API.md](API.md). UX и маршруты: [FRONTEND.md](FRONTEND.md).

## Обработка ошибок

| Ситуация | Поведение |
|----------|-----------|
| LLM: невалидный JSON | Retry через instructor (до 2 раз) |
| Пул < 100 кандидатов | Расширить search_queries, повторить |
| HTTP 429 от Яндекса | Exponential backoff, retry |
| Токен истёк | 401 → переавторизация Device Flow |
| Embeddings недоступны | Fallback-скоринг |
| Трек `available=False` | Пропустить, следующий по score |

## Структура кода

```
backend/app/
├── main.py
├── api/v1/endpoints/   # HTTP-слой
├── api/deps.py         # Async Depends (AsyncSession)
├── core/               # config, security, exceptions
├── schemas/            # Pydantic (API + MusicProfile)
├── services/           # бизнес-логика
├── repositories/       # доступ к БД
└── db/models/          # SQLAlchemy

frontend/src/           # Next.js (см. CONVENTIONS.md)
├── app/                # RSC-маршруты
├── features/           # auth, playlist
├── components/         # shell + ui/
├── lib/api.ts
└── types/
```

## Конфигурация

См. `.env.example`. Ключевые переменные:

```env
DATABASE_URL=postgresql+asyncpg://prompt_dj:prompt_dj@localhost/prompt_dj
OPENAI_API_KEY=
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=intfloat/multilingual-e5-base
SCORING_EMBED_LIMIT=0
TOKEN_ENCRYPTION_KEY=
```

Окружение dev-машины: [INFRASTRUCTURE.md](INFRASTRUCTURE.md).
