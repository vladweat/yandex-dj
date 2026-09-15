# План разработки (Roadmap)

Стек: [STACK.md](STACK.md). ТЗ: [SPEC.md](SPEC.md).

## Текущий статус

| Область | Состояние |
|---------|-----------|
| Документация | ✅ SPEC, STACK, ARCHITECTURE, API, LLM_SCHEMA |
| Окружение | ✅ `make venv` — venv + модель e5-base + libgomp |
| Docker | ✅ `prompt-dj-api` + `prompt-dj-db` (PostgreSQL 15) + Redis 7 |
| FastAPI | ✅ `/api/v1/health` → `200 ok` |
| Auth / Playlists | ✅ Auth + `POST /playlists/generate` (end-to-end) |
| Frontend | ⏳ каркас из docwise — [FRONTEND.md](FRONTEND.md); временно `GET /test/auth` |
| Пайплайн (LLM → export) | ✅ LLM → retrieval → scoring → export |
| Качество плейлистов | ⚠️ топ хороший, **18–19/25** на mood-only промптах — см. [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md) |

**Следующий шаг:** [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md) § «Открытые задачи» (P0: clean-пул ≥50), затем этап 6 backlog.

---

## Этап 0. Инфраструктура и скелет

**Цель:** каркас приложения, окружение, offline-сборка.

- [x] Структура `backend/app/` (api, core, services, schemas, repositories, db, cli)
- [x] `backend/pyproject.toml`: зависимости из [STACK.md](STACK.md)
- [x] `docker-compose.yml`: PostgreSQL 15 + Redis 7 + API
- [x] `Dockerfile`: offline-сборка (venv → site-packages, модель, libgomp)
- [x] `Makefile`: `venv`, `build`, `up`, `down`, `pack`
- [x] Скрипты: `build-venv.sh`, `verify-venv.sh`, `pack-offline-bundle.sh`, `prepare_embeddings.py`
- [x] `Settings` + `.env.example`
- [x] Async SQLAlchemy (`create_async_engine`, `get_db`)
- [x] Alembic каркас (`env.py`) — **миграций пока нет**
- [x] Fernet: `encrypt_token` / `decrypt_token` (`core/security.py`)
- [x] Pydantic-схемы: `MusicProfile`, auth, playlist, health
- [x] Роутеры: health, auth, llm, retrieval, scoring, playlists (`api/v1/router.py`)
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

Через UI: `GET /test/auth` (временно) или `/login` в Next.js после этапа 1.5.

---

## Этап 1.5. Frontend (каркас из docwise)

**Цель:** Next.js UI с Device Flow и экраном генерации (заглушка до готового пайплайна).

- [x] `frontend/` — скелет по [REUSE_FROM_DOCWISE.md](REUSE_FROM_DOCWISE.md)
- [x] `components/ui`, `layout`, `query-provider`, `toast-host`
- [x] `lib/api.ts` — Bearer `session_id`, `fetchMe`, Device Flow
- [x] `features/auth` — `/login`, gates, `auth-provider`
- [x] `features/playlist` — форма промпта, заглушка результата
- [x] `docker-compose` сервис `frontend`, `make deps-frontend` / `up-frontend`
- [x] Удалить `backend/app/static/auth-test.html` и `GET /test/auth`

**Проверка:** `http://localhost:3001/login` → Device Flow → профиль в header; `/` — форма промпта.

---

## Этап 2. LLM Engine

**Цель:** промпт → `MusicProfile` через OpenAI + instructor.

- [x] Pydantic-модель `MusicProfile` ([LLM_SCHEMA.md](LLM_SCHEMA.md))
- [x] Системный промпт + few-shot примеры
- [x] `LLMService`: `instructor` + `openai` SDK (KodikRouter / `gpt-4o-mini`)
- [x] Внутренний сервис / endpoint для парсинга (`POST /api/v1/llm/parse`, CLI `llm parse`)
- [x] 10–15 тестов с разноплановыми промптами (`pytest`)

**Проверка:** тестовые промпты → валидный `MusicProfile`.

---

## Этап 3. Retrieval Engine

**Цель:** `MusicProfile` → пул 150–300 кандидатов.

- [x] `RetrievalService`: `search` + `artists_tracks` (топ-10) + `tracks_similar`
- [x] Async через `asyncio`
- [x] Дедупликация: `track.id` + «Артист + Название»
- [x] Фильтр `available == False`
- [x] Redis: кэш метаданных треков (`docker compose` + `redis:7`)

**Проверка:** пул 150+ треков за < 4 сек.

```bash
# API (нужна сессия)
curl -X POST localhost:8000/api/v1/retrieval/candidates \
  -H "Authorization: Bearer $SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"profile": {...}}'

# CLI
prompt-dj retrieval fetch --prompt "dark synthwave" --token "$YANDEX_OAUTH_TOKEN"
```

---

## Этап 4. Scoring Module

**Цель:** кандидаты → отранжированный топ-N (embeddings с первого релиза).

- [x] Модель `intfloat/multilingual-e5-base` подготовлена для offline (`make venv`)
- [x] `ScoringService`: `sentence-transformers` + batch-эмбеддинг
- [x] Паспорта треков (формат из [SPEC.md](SPEC.md) §4.4)
- [x] Cosine similarity (`numpy`)
- [x] Diversity: 2 трека/артист (N≤25), 3 (N 26–50)
- [x] Fallback: жанры + популярность

**Проверка:** 25 релевантных треков; скоринг **< 2 сек** после warmup модели (API прогревает при старте). Первый CLI-запуск: ~15 с load + ~12 с encode на CPU — норма для cold start.

```bash
prompt-dj scoring rank --prompt "dark synthwave for night coding" --token "$YANDEX_OAUTH_TOKEN"
# Ожидаем: ranked: 25, method: embedding, reference artists в топе
```

---

## Этап 5. Export + end-to-end API

**Цель:** полный пайплайн через FastAPI.

- [x] `PlaylistService.generate()` — LLM → retrieval → scoring → export
- [x] `POST /api/v1/playlists/generate` ([API.md](API.md))
- [x] Экспорт: `users_playlists_create` + `insert_track` + description + URL
- [x] Метрики latency по этапам в логах

**Проверка:** промпт через API → ссылка на плейлист за 7–12 сек.

```bash
# session_id — из Device Flow (make auth-poll) или GET /api/v1/auth/me
curl -sS -X POST http://localhost:8000/api/v1/playlists/generate \
  -H "Authorization: Bearer $SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "dark synthwave for night coding", "track_count": 25}'
# Ожидаем: 200, playlist_url, tracks[].similarity_score; в логах api — Playlist pipeline: llm=…ms …
```

Контракт, коды ошибок и семантика полей: [API.md](API.md) § Playlists.  
Методы SDK Яндекса (auth, retrieval, export): [API.md](API.md) § Yandex Music API, детали — [YANDEX_MUSIC.md](YANDEX_MUSIC.md).

---

## Этап 5.5. Качество плейлистов

**Цель:** стабильно **25 релевантных** треков на промптах без артистов (kitchen, coding, …).

- [x] Универсальный SEO pre-filter (`quality.py`)
- [x] Embedding без `reference_artists` в query + anchor boost
- [x] Adaptive elbow + fill + sort (tail без raise до `score[N-1]`)
- [x] Retrieval: similar seeds, frequency-rank discovered + similar, `min_clean_candidates`
- [x] Scoring feedback при `selected < N`; `pool_stats` в ответе
- [x] **P0:** kitchen curl/UI → `tracks.length == 25`, `clean ≥ 40`
- [x] Frontend: генерация без заглушки «Скоро», таблица + `pool_stats`
- [ ] **P1:** хвост без embedding-мусора (Hauvy и т.п.)
- [ ] **P2:** latency budget 7–12 сек (`SCORING_EMBED_LIMIT` / меньше double-embed)

**Handoff для агента:** [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md) — не добавлять regex под промпт.  
**UI-тест:** [FRONTEND.md](FRONTEND.md) § «Ручной тест UI».

---

## Этап 6. Backlog

- [ ] Telegram-бот (`aiogram`)
- [ ] BPM-анализ (`librosa`)
- [ ] AI-обложка, анализ lyrics
- [ ] Celery/Arq при необходимости async-генерации

---

## Dev-инструменты

| Инструмент | Статус |
|------------|--------|
| `ruff` | ✅ в `pyproject.toml` |
| `pytest` | ✅ auth, health, llm, retrieval, scoring |
| `vitest` / `tsc` | ⏳ после `frontend/` |
| CI (`.github/`) | ❌ не настроен |

```bash
cd backend
ruff check app tests
ruff format .
pytest
```
