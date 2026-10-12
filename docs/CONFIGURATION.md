# Конфигурация

Источник истины backend — `Settings` в `backend/app/core/config.py`.
`pydantic-settings` читает переменные окружения и файл `.env` текущего рабочего
каталога; неизвестные ключи игнорируются. Безопасный шаблон —
`backend/.env.example`.

Compose загружает `backend/.env`, затем явно заменяет `DATABASE_URL`,
`REDIS_URL` и `EMBEDDING_MODEL_PATH` для контейнера `api`. Секретные значения
ниже намеренно не приведены.

## Обязательность

У `Settings` есть defaults почти для всех полей, но это не означает готовность
функции:

- `TOKEN_ENCRYPTION_KEY` обязателен для создания и чтения пользовательских
  сессий;
- `OPENAI_API_KEY` обязателен для нового LLM-профиля и включённой генерации
  обложек;
- `TG_BOT_TOKEN` обязателен для bot и проверки Telegram `initData`;
- `METRICS_TOKEN` обязателен только для `/api/v1/metrics/product`; пустое
  значение отключает endpoint ответом `503`.

## Backend

### Данные и безопасность

| Переменная | Default | Назначение |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://prompt_dj:prompt_dj@localhost/prompt_dj` | Async SQLAlchemy URL; Compose использует host `db` |
| `DATABASE_CONNECT_TIMEOUT_SEC` | `5` | Таймаут подключения; для localhost также отключается SSL |
| `REDIS_URL` | `redis://localhost:6379/0` | Кэш метаданных и наличия lyrics |
| `TOKEN_ENCRYPTION_KEY` | пусто | Fernet-ключ для OAuth-токенов; секрет |
| `SESSION_TTL_HOURS` | `720` | TTL серверной сессии |
| `CORS_ORIGINS` | localhost ports 3000/3001 | CSV exact origins без wildcard |
| `METRICS_TOKEN` | пусто | Shared secret заголовка `X-Metrics-Token`; секрет |

### LLM, embeddings и обложки

| Переменная | Default | Назначение |
|---|---|---|
| `OPENAI_API_KEY` | пусто | Bearer key OpenAI-compatible API; секрет |
| `OPENAI_BASE_URL` | пусто | Альтернативный OpenAI-compatible endpoint |
| `OPENAI_MODEL` | пусто | Предпочтительная LLM-модель в `llm_config` |
| `LLM_MODEL` | `gpt-4o-mini` | Fallback имени LLM-модели |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-base` | Hugging Face model id |
| `EMBEDDING_MODEL_PATH` | пусто | Локальная offline-модель; Compose: `/opt/models` |
| `EMBEDDING_BATCH_SIZE` | `64` | Размер encode batch |
| `EMBEDDING_TORCH_THREADS` | `0` | `0` — все доступные CPU threads |
| `PLAYLIST_COVER_ENABLED` | `true` | Включает параллельную генерацию cover |
| `OPENAI_IMAGE_MODEL` | пусто | Image model; в `.env.example` указан рекомендуемый provider model |
| `PLAYLIST_COVER_ASPECT_RATIO` | `1:1` | Aspect ratio запроса image API |
| `PLAYLIST_COVER_RESOLUTION` | `1K` | Resolution запроса |
| `PLAYLIST_COVER_TIMEOUT_SEC` | `28` | Ожидание cover task |
| `COVER_STORAGE_DIR` | `data/covers` | Локальное файловое хранилище PNG |

### Pipeline и retrieval

| Переменная | Default |
|---|---:|
| `PIPELINE_TIMEOUT_SEC` | `90` |
| `DAILY_GENERATION_LIMIT` | `10` (`0` отключает лимит) |
| `MAX_CANDIDATES` | `300` |
| `MIN_CANDIDATES_POOL` | `100` |
| `TARGET_CANDIDATES_POOL` | `150` |
| `MIN_CLEAN_CANDIDATES` | `50` |
| `TRACK_CACHE_TTL_SEC` | `86400` |
| `ARTIST_TRACKS_LIMIT` | `20` |
| `SEARCH_TRACKS_PER_QUERY` | `50` |
| `SEARCH_PAGES` | `2` |
| `SEARCH_EXPAND_MAX_QUERIES` | `12` |
| `RETRIEVAL_EXPAND_PASSES` | `4` |
| `SIMILAR_SEEDS_PER_ARTIST` | `3` |
| `MAX_SIMILAR_REQUESTS` | `12` |
| `REFERENCE_ARTISTS_TOPS_LIMIT` | `5` |
| `DISCOVERED_ARTISTS_LIMIT` | `12` |
| `DISCOVERED_SIMILAR_SEEDS` | `8` |
| `FEEDBACK_ARTISTS_LIMIT` | `8` |
| `FEEDBACK_SIMILAR_SEEDS` | `8` |
| `SCORING_EMBED_LIMIT` | `0` (весь пул) |
| `MAX_TRACKS_PER_ARTIST` | `2` |

Эти параметры связаны между собой. Менять их без golden-регресса из
`backend/tests/test_golden_prompts.py` нельзя.

### Библиотека, lyrics и Яндекс

| Переменная | Default | Назначение |
|---|---:|---|
| `LIBRARY_ARTIST_LIMIT` | `24` | Ширина artist bias |
| `LIBRARY_SEED_ARTISTS` | `8` | Seed artists |
| `LIBRARY_SIMILAR_SEEDS` | `6` | Similar requests |
| `LIBRARY_LIKES_TRACK_LIMIT` | `80` | Лимит likes |
| `LIBRARY_RECENT_FULL_MODELS` | `40` | Лимит recent |
| `LIBRARY_ARTIST_BOOST` | `0.025` | Soft score boost |
| `LYRICS_CHECK_LIMIT` | `80` | Максимум lyrics checks |
| `LYRICS_VOCAL_SCORE_PENALTY` | `0.045` | Soft penalty |
| `YANDEX_RATE_LIMIT_DELAY_SEC` | `0.15` | Пауза между вызовами SDK |
| `YANDEX_API_MAX_RETRIES` | `3` | Число попыток сетевых вызовов |
| `DEVICE_FLOW_TIMEOUT_SEC` | `120` | Используется CLI/full-flow helper; HTTP poll выполняет один poll |

### API, Telegram и proxy

| Переменная | Default | Назначение |
|---|---|---|
| `API_HOST` | `0.0.0.0` | Используется CLI/config; Compose command фиксирует host |
| `API_PORT` | `8000` | Используется CLI/config; Compose command фиксирует port |
| `TG_BOT_TOKEN` | пусто | Telegram Bot API token; секрет |
| `TELEGRAM_WEB_APP_URL` | `http://localhost:3001/tg` | Menu Button URL; production требует HTTPS |
| `TELEGRAM_BOT_USE_PROXY` | `true` | Использовать proxy для bot |
| `HTTP_PROXY`, `HTTPS_PROXY` | не заданы | Исходящий proxy |
| `NO_PROXY`, `no_proxy` | дополняются кодом | Internal hosts `db`, `postgres`, `redis`, localhost |

`HTTP_PROXY`/`HTTPS_PROXY` не являются полями `Settings`: их читают HTTP-клиенты
и окружение. `backend/app/core/proxy.py` только дополняет bypass list.

## Frontend

| Переменная | Default | Где используется |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | `frontend/src/lib/api.ts` |

Переменная публичная и встраивается в JavaScript во время `next build`.
Значение из секции `environment` уже собранного контейнера не переписывает
bundle. Для другого API URL пересоберите образ с build arg и добавьте origin UI
в backend `CORS_ORIGINS`.

## Окружения

В репозитории нет отдельных staging/production env-файлов и secret manager
integration. Для production необходим внешний механизм выдачи secrets, TLS,
непубличные PostgreSQL/Redis ports и явная политика CORS. Эти элементы нельзя
считать реализованными текущим Compose.
