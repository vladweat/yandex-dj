# Архитектура Prompt DJ

Архитектура описывает границы компонентов и поток данных генерации.

## Модули системы

| Модуль | Код | Ответственность | Вход | Выход |
|--------|-----|-----------------|------|-------|
| Prompt Understanding | `services/llm_service.py` | Декомпозиция NL-запроса | Промпт | `MusicProfile` |
| Candidate Retrieval | `services/retrieval/` | Сбор пула через API | `MusicProfile` | до 300 `TrackCandidate` |
| Scoring & Ranking | `services/scoring_service.py` + `utils/scoring/` | Векторный скоринг | Промпт + кандидаты | `list[ScoredTrack]` |
| Playlist Builder | `services/yandex/` | Создание плейлиста | Топ-N треков | URL плейлиста |
| Auth & Sessions | `services/` + `api/.../auth` | Device Flow, шифрование токенов | — | `session_id` |
| API | `api/v1/endpoints/` | FastAPI endpoints | HTTP | JSON |
| Pipeline | `services/playlist_service.py` | Оркестрация generate | Промпт + опции | `PlaylistGenerateResponse` |

Это слоистый монолит, а не набор микросервисов: API, pipeline и data access
работают в одном Python-процессе. Bot и frontend — отдельные процессы.

## Жизненный цикл HTTP-запроса

```mermaid
sequenceDiagram
    participant C as Browser
    participant E as FastAPI endpoint
    participant D as dependencies
    participant S as PlaylistService
    participant X as LLM/Yandex/Redis
    participant R as Repository
    participant P as PostgreSQL

    C->>E: POST /api/v1/playlists/generate + Bearer
    E->>D: get_current_session / get_playlist_service
    D->>P: SessionRepository.get_valid
    E->>S: generate(...)
    S->>X: LLM, retrieval/cache, scoring, export
    S->>R: create generation
    R->>P: flush + commit
    S-->>E: PlaylistGenerateResponse
    E-->>C: JSON
```

`api/deps.py` создаёт request-scoped `AsyncSession`. Endpoints преобразуют
domain exceptions в HTTP statuses; централизованного global exception handler
нет. Весь generate обёрнут `asyncio.wait_for(PIPELINE_TIMEOUT_SEC)`.

## Пайплайн

```
[Пользователь] ──> (Промпт + session_id)
                         │
                         ▼
              ┌──────────────────────┐
              │ 1. LLM Engine       │
              │    → MusicProfile    │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 2. Retrieval        │
              │    → 150–300 tracks  │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 3. Scoring          │
              │    → топ-N           │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 4. Export           │
              │    → playlist_url    │
              └──────────────────────┘
```

Время этапов зависит от внешних API и доступности embedding-модели.

## Слой данных

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ PostgreSQL  │     │    Redis    │     │  yandex-    │
│    15       │     │  кэш track  │     │  music API  │
│             │     │  metadata   │     │             │
│  users      │     │ metadata +  │     │             │
│  sessions   │     │ lyrics      │     │             │
│ generations │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘

(*) токены зашифрованы Fernet; ORM — SQLAlchemy
```

## Интерпретация запроса

- Pydantic `MusicProfile` + `instructor`
- Провайдер: OpenAI API (`openai` SDK, `gpt-4o-mini`) + `instructor`
- Схема: [LLM_SCHEMA.md](LLM_SCHEMA.md)

## Поиск кандидатов

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

## Ранжирование и отбор

**Паспорт трека:**
```
Название: {title}. Исполнитель: {artists}. Альбом: {album}. Жанр: {genre}. Версия: {version}
```

Для embedding используется компактная форма `embedding_passport()` — `{title}. {artists}. {genre}` (меньше токенов, быстрее encode).

**Алгоритм:**
1. Pre-filter SEO/мусор (`utils/quality/`) → clean-пул
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

## Экспорт плейлиста

1. `users_playlists_create(title=profile.playlist_title)`
2. `users_playlists_change()` с одним `Difference.add_insert` для списка треков
3. Описание: `profile.playlist_description` + исходный промпт
4. URL: `https://music.yandex.ru/users/{login}/playlists/{kind}`

## Интерфейсы

| Интерфейс | Стек | Назначение |
|-----------|------|-----------|
| Web | Next.js 15 + Tailwind 4 + shadcn | **Основной UI** |
| REST API | FastAPI + uvicorn | Контракт для UI и интеграций |
| CLI | click | Отладка Device Flow |
| Telegram | aiogram 3.x + Mini App `/tg` | [Компоненты и настройка](TELEGRAM.md) |

API-контракты: [API.md](API.md). UX и маршруты: [FRONTEND.md](FRONTEND.md).

## Обработка ошибок

| Ситуация | Поведение |
|----------|-----------|
| LLM: невалидный JSON | Retry через instructor (до 2 раз) |
| Пул < 100 кандидатов | Расширить search_queries, повторить |
| HTTP 429 от Яндекса | Exponential backoff, retry |
| Prompt DJ session истекла | 401 → повторный Device Flow |
| Embeddings недоступны | Fallback-скоринг |
| Трек `available=False` | Пропустить, следующий по score |

## Асинхронность и фоновые операции

- Yandex/OpenAI/Redis I/O выполняется async.
- CPU-bound embeddings/scoring запускаются через executor.
- Cover создаётся `asyncio.create_task` параллельно основному pipeline, но
  результат ожидается с отдельным timeout до ответа.
- Bot использует aiogram long polling в отдельном Compose service.
- Генерация обрабатывается в рамках исходного HTTP-запроса.

## Транзакции и внешние границы

`get_db()` не делает implicit commit. Auth commit выполняет service, а
generation create/update — repository. Экспорт в Яндекс происходит раньше
persist в PostgreSQL; общей транзакции между Яндексом, БД, Redis и filesystem
нет. Подробности: [DATABASE.md](DATABASE.md).

Внешние boundaries: OpenAI-compatible API, Yandex Music API, Telegram Bot API.
Retries Яндекса находятся в service wrapper; универсальной idempotency key и
distributed retry policy нет.

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

Полный каталог: [CONFIGURATION.md](CONFIGURATION.md). Runtime и startup:
[OPERATIONS.md](OPERATIONS.md).
