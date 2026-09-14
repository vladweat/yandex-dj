# План разработки (Roadmap)

Стек: [STACK.md](STACK.md). ТЗ: [SPEC.md](SPEC.md).

## Текущий статус

| Область | Состояние |
|---------|-----------|
| Документация | ✅ SPEC, STACK, ARCHITECTURE, API, LLM_SCHEMA |
| Окружение | ✅ `make venv` — venv + модель e5-base + libgomp |
| Docker | ✅ `prompt-dj-api` + `prompt-dj-db` (PostgreSQL 15) |
| FastAPI | ✅ `/api/v1/health` → `200 ok` |
| Auth / Playlists | ✅ Auth реализован; Playlists — `501` |
| Пайплайн (LLM → export) | ❌ сервисы — заглушки |

**Следующий шаг:** применить миграции и проверить Device Flow; затем Этап 2 (LLM Engine).

---

## Этап 0. Инфраструктура и скелет

**Цель:** каркас приложения, окружение, offline-сборка.

- [x] Структура `backend/app/` (api, core, services, schemas, repositories, db, cli)
- [x] `backend/pyproject.toml`: зависимости из [STACK.md](STACK.md)
- [x] `docker-compose.yml`: PostgreSQL 15 + API
- [x] `Dockerfile`: offline-сборка (venv → site-packages, модель, libgomp)
- [x] `Makefile`: `venv`, `build`, `up`, `down`, `pack`
- [x] Скрипты: `build-venv.sh`, `verify-venv.sh`, `pack-offline-bundle.sh`, `prepare_embeddings.py`
- [x] `Settings` + `.env.example`
- [x] Async SQLAlchemy (`create_async_engine`, `get_db`)
- [x] Alembic каркас (`env.py`) — **миграций пока нет**
- [x] Fernet: `encrypt_token` / `decrypt_token` (`core/security.py`)
- [x] Pydantic-схемы: `MusicProfile`, auth, playlist, health
- [x] Роутеры: health, auth, playlists (`api/v1/router.py`)
- [x] `/api/v1/health` — работает
- [x] Embedding-модель `intfloat/multilingual-e5-base` скачана в `backend/.models/`
- [x] Docker-стек: `make build && make up`

**Проверка:** `curl localhost:8000/api/v1/health` → `{"status":"ok",...}`.

---

## Этап 1. Авторизация (OAuth Device Flow)

**Цель:** Device Flow → зашифрованный токен в PostgreSQL → сессия пользователя.

- [x] SQLAlchemy: модели `User`, `Session` (`db/models/`)
- [x] Alembic-миграция `580d8db37f7b_add_users_and_sessions`
- [x] `UserRepository` + `SessionRepository` — CRUD
- [x] `AuthService` — `start_device_flow` / `poll_device_flow`
- [x] `YandexMusicService` — обёртка `ClientAsync`, retry, rate limiting
- [x] Эндпоинты `POST /api/v1/auth/device-flow/start` и `poll`
- [x] CLI: `prompt-dj db`, `prompt-dj auth start` / `poll` / `import-token`
- [ ] **Проверка на стенде:** миграции + Device Flow → токен в PostgreSQL

**Проверка (две ВМ / переключение интернета):**

Браузер на проектной ВМ не нужен — код подтверждают на **телефоне** (мобильный интернет).

```bash
make up && make migrate          # БД — только через контейнер (как docwise)

# 1. На хосте (прокси → Яндекс): запросить код
cd backend && prompt-dj auth start

# 2. На телефоне подтвердить user_code на ya.ru/device

# 3. На хосте (прокси): poll → токен + профиль в pending.json
prompt-dj auth poll

# 4. Запись в БД — в контейнере (только PostgreSQL, без Яндекса):
#    pending.json должен содержать access_token + yandex_uid + login
make migrate && make auth-poll

# Альтернатива: на ВМ с интернетом prompt-dj auth test, скопировать токен:
# prompt-dj auth import-token <oauth_token>
```

**CLI vs API:** HTTP `poll` всегда ходит в Яндекс и сразу пишет в БД. CLI умеет разорванный сценарий: токен и профиль кэшируются в `backend/.auth/pending.json` (в Docker — volume `./backend/.auth`), запись в PostgreSQL — отдельным шагом `make auth-poll`. Для шага 4 нужен `TOKEN_ENCRYPTION_KEY` в `.env`.

Через API — те же шаги: `POST .../start` → подтверждение на телефоне → `POST .../poll`.

---

## Этап 2. LLM Engine

**Цель:** промпт → `MusicProfile` через OpenAI + instructor.

- [x] Pydantic-модель `MusicProfile` ([LLM_SCHEMA.md](LLM_SCHEMA.md))
- [ ] Системный промпт + few-shot примеры
- [ ] `LLMService`: `instructor` + `openai` SDK (`gpt-4o-mini`)
- [ ] Внутренний сервис / endpoint для парсинга
- [ ] 10–15 тестов с разноплановыми промптами (`pytest`)

**Проверка:** тестовые промпты → валидный `MusicProfile`.

---

## Этап 3. Retrieval Engine

**Цель:** `MusicProfile` → пул 150–300 кандидатов.

- [ ] `RetrievalService`: `search` + `artists_tracks` (топ-10) + `tracks_similar`
- [ ] Async через `asyncio`
- [ ] Дедупликация: `track.id` + «Артист + Название»
- [ ] Фильтр `available == False`
- [ ] Redis: кэш метаданных треков (`docker compose` + `redis:7`)

**Проверка:** пул 150+ треков за < 4 сек.

---

## Этап 4. Scoring Module

**Цель:** кандидаты → отранжированный топ-N (embeddings с первого релиза).

- [x] Модель `intfloat/multilingual-e5-base` подготовлена для offline (`make venv`)
- [ ] `ScoringService`: `sentence-transformers` + batch-эмбеддинг
- [ ] Паспорта треков (формат из [SPEC.md](SPEC.md) §4.4)
- [ ] Cosine similarity (`numpy`)
- [ ] Diversity: 2 трека/артист (N≤25), 3 (N 26–50)
- [ ] Fallback: жанры + популярность

**Проверка:** 25 релевантных треков; скоринг < 2 сек.

---

## Этап 5. Export + end-to-end API

**Цель:** полный пайплайн через FastAPI.

- [ ] `PlaylistService.generate()` — LLM → retrieval → scoring → export
- [ ] `POST /api/v1/playlists/generate` ([API.md](API.md)) — сейчас `501`
- [ ] Экспорт: `users_playlists_create` + `insert_track` + description + URL
- [ ] Метрики latency по этапам в логах

**Проверка:** промпт через API → ссылка на плейлист за 7–12 сек.

---

## Этап 6. Backlog

- [ ] Next.js фронтенд
- [ ] Telegram-бот (`aiogram`)
- [ ] BPM-анализ (`librosa`)
- [ ] AI-обложка, анализ lyrics
- [ ] Celery/Arq при необходимости async-генерации

---

## Dev-инструменты

| Инструмент | Статус |
|------------|--------|
| `ruff` | ✅ в `pyproject.toml` |
| `pytest` | ⏳ тест `test_health.py`; dev-зависимости — `pip install ".[dev]"` |
| CI (`.github/`) | ❌ не настроен |

```bash
cd backend
ruff check app tests
ruff format .
pytest
```
