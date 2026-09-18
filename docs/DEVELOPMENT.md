# План разработки (Roadmap)

Стек: [STACK.md](STACK.md). ТЗ: [SPEC.md](SPEC.md).

## Текущий статус

| Область | Состояние |
|---------|-----------|
| Документация | ✅ SPEC, STACK, ARCHITECTURE, API, LLM_SCHEMA, FRONTEND, PLAYLIST_QUALITY, **PRODUCT** |
| Окружение | ✅ `make venv` — venv + модель e5-base + libgomp |
| Docker | ✅ `prompt-dj-api` + `prompt-dj-db` (PostgreSQL 15) + Redis 7 + frontend |
| FastAPI | ✅ `/api/v1/health` → `200 ok` |
| Auth / Playlists | ✅ Device Flow + `POST /playlists/generate` (end-to-end) |
| Frontend | ✅ Next.js: `/login`, `/` (генерация + таблица + `pool_stats`) — [FRONTEND.md](FRONTEND.md) |
| Пайплайн (LLM → export) | ✅ LLM → retrieval → scoring → export |
| Качество плейлистов | ✅ этап 5.5: P0/P1/P2 — [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md) |
| Продукт (этап 6) | ✅ история / реген / profile / опции / UX / CI |
| CI | ✅ `.github/workflows/ci.yml` — ruff + pytest + tsc/vitest |
| Техдолг A/B/C1–C5 | ✅ (C6 — опциональный Яндекс E2E в CI) |
| **Следующий фокус** | [PRODUCT.md](PRODUCT.md): **P1.1 Telegram E2E**; P3 по триггеру |

**MVP, этап 5.5, этап 6 и продуктовый P0–P2 закрыты.** Ядро не трогать без регресса golden. Фокус: **канал (бот) → P3 по метрикам**.

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
- [x] Alembic (`env.py` + миграции со этапа 1)
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
- [x] **Проверка на стенде:** миграции + Device Flow → токен в PostgreSQL

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

Через UI: `http://localhost:3001/login` (Next.js Device Flow).

---

## Этап 1.5. Frontend (каркас из docwise)

**Цель:** Next.js UI с Device Flow и экраном генерации.

- [x] `frontend/` — скелет по [REUSE_FROM_DOCWISE.md](REUSE_FROM_DOCWISE.md)
- [x] `components/ui`, `layout`, `query-provider`, `toast-host`
- [x] `lib/api.ts` — Bearer `session_id`, `fetchMe`, Device Flow
- [x] `features/auth` — `/login`, gates, `auth-provider`
- [x] `features/playlist` — форма промпта, результат (таблица + `pool_stats`)
- [x] `docker-compose` сервис `frontend`, `make deps-frontend` / `up-frontend`
- [x] Удалить `backend/app/static/auth-test.html` и `GET /test/auth`

**Проверка:** `http://localhost:3001/login` → Device Flow → профиль в header; `/` — генерация плейлиста.

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

**Цель:** стабильно **25 релевантных** треков на промптах без артистов (kitchen, coding, …); latency в бюджете.

- [x] Универсальный SEO pre-filter (`quality.py`)
- [x] Embedding без `reference_artists` в query + anchor boost
- [x] Adaptive elbow + fill + sort (tail без raise до `score[N-1]`)
- [x] Retrieval: similar seeds, frequency-rank discovered + similar, `min_clean_candidates`
- [x] Scoring feedback при `selected < N`; `pool_stats` в ответе
- [x] **P0:** kitchen curl/UI → `tracks.length == 25`, `clean ≥ 40`
- [x] Frontend: генерация без заглушки, таблица + `pool_stats`
- [x] **P1:** хвост без embedding-мусора (Hauvy и т.п.); cap якорей ~60%
- [x] **P2:** latency budget 7–12 сек (`SCORING_EMBED_LIMIT` / меньше double-embed)

**Handoff для агента:** [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md) — не добавлять regex под промпт; Q1–Q5 ✅; план хвоста **Q6–Q8** (shortfall → two-phase → source prior) — там же (2026-09-17).  
**UI-тест:** [FRONTEND.md](FRONTEND.md) § «Ручной тест UI».

**Дальше:** продуктовый бэклог — [PRODUCT.md](PRODUCT.md) (P0 metrics → P1 канал / listening graph).

---

## Этап 6. Продукт вокруг генерации + инженерия

**Цель:** после стабильного качества — UX итерации и история; CI. **Закрыт.**

Приоритет сверху вниз:

- [x] **История генераций** — список своих плейлистов (промпт, дата, URL, `pool_stats`); модель + API + UI
- [x] **Регенерация / итерация** — «ещё вариант» с `source_id` (reuse profile, без LLM); `exclude_artists`
- [x] **Прозрачность профиля** — `MusicProfile` в ответе generate и в UI
- [x] **Опции генерации** — `exclude_artists`, `instrumental_only`, `diversity=high`
- [x] **UX-мелочи** — prefill `?prompt=…`, копирование ссылки+промпта, «API недоступен»
- [x] **CI** — `.github/workflows/ci.yml`: `ruff` + `pytest` + `tsc` / vitest
- [x] **Golden-промпты** — `tests/test_golden_prompts.py` (7 сценариев, sync с `SAMPLE_PROMPTS`; CI = регресс-алерт)
- [x] Frontend-тесты (vitest) на auth-gates и форму генерации

Не делать на этом этапе: новые vector DB, переписывание UI «с нуля», regex под конкретные промпты.

**Миграция:** `a1b2c3d4e5f6_add_playlist_generations` — `make migrate`.

---

## Этап 7+. Продуктовый бэклог (после MVP)

Канон: **[PRODUCT.md](PRODUCT.md)** — ICP, metrics, P0–P3, DoD, «не сейчас».

Краткий чеклист (статусы синхронизировать с PRODUCT.md):

### P0 — видеть продукт

- [x] **P0.1** Product metrics (latency, selected==N, clean, warnings, regen vs new, diversity)
- [x] **P0.2** Regen / return-7d — [docs/analytics/product_metrics.sql](analytics/product_metrics.sql)
- [x] **P0.3** Like / dislike на результат
- [x] **P0.4** Отчёт p50/p95 latency, % full-N, warnings, regen — `GET /api/v1/metrics/product` + [analytics/product_metrics.sql](analytics/product_metrics.sql)
- [x] **P0.5** Golden 7 промптов + UI checklist — `tests/test_golden_prompts.py`, [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md) § Golden UI checklist

### P1 — рост и дифференциатор

- [~] **P1.1** Telegram — см. [TELEGRAM.md](TELEGRAM.md) (код в репо; E2E на dev-server ⏸)
- [x] **P1.2** Галерея промптов → `/?prompt=…`
- [x] **P1.3** Персонализация: likes / recently played Яндекса (soft bias)
- [x] **P1.4** Онбординг (ожидание 7–20 сек + 3 ситуации)
- [x] **P1.5** Soft-квоты N генераций/сутки

### P2 — pain и polish

- [x] **P2.1** Lyrics: «без слов» / NSFW
- [x] **P2.2** AI-обложка
- [x] **P2.3** Шаринг промпт+ссылка с UTMs
- [x] **P2.4** Выкинуть / заменить трек без полной реген
- [x] **P2.5** Мягкий показ latency («Ещё вариант — без LLM»)

### P3 — по триггеру

- [ ] **P3.1** BPM (`librosa`) — только по флагу
- [ ] **P3.2** Celery/Arq — если p95 ≫ 20 сек или очередь бота
- [ ] **P3.3** Hard rate-limit Яндекс + backoff UX
- [ ] **P3.4** Freemium / Pro
- [ ] **P3.5** White-label / B2B

**Порядок:** P0 → P1.1∥P1.4 → P1.5 → P1.3 → P1.2 → P2 → P3 по триггеру.

**Не сейчас:** multi-catalog, org-mode, перепись UI, редакционка, монетизация «Ещё вариант», regex под жанр.

### Telegram (P1.1) — пауза

Канон состояния и чеклист возобновления: **[TELEGRAM.md](TELEGRAM.md)**.

---

## Техдолг

Актуально на 2026-09-18. Качество/latency + Q1–Q8 — [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md). Продукт — [PRODUCT.md](PRODUCT.md).

### Приоритет A — качество и latency (этап 5.5) ✅

| # | Что | Где | Зачем |
|---|-----|-----|--------|
| A1 | ~~Embedding false positives в хвосте~~ | `utils/scoring/floors.py` | ✅ `filter_by_top_median_gap` |
| A2 | ~~Cap якорей ~60% плейлиста~~ | `select_playlist_tracks` | ✅ `max_anchor_tracks` |
| A3 | ~~Double-embed на feedback~~ | `rank_pool_merge` | ✅ encode только новых |
| A4 | ~~`SCORING_EMBED_LIMIT` drift~~ | `.env` / config | ✅ `0` везде |

### Приоритет B — продукт (дыры этапа 6) ✅

| # | Что | Где | Зачем |
|---|-----|-----|--------|
| B1 | ~~«Ещё вариант» сбрасывает опции~~ | result + `options` | ✅ |
| B2 | ~~History не восстанавливает options~~ | API + history | ✅ |
| B3 | ~~`PIPELINE_TIMEOUT_SEC` мёртв~~ | endpoint + abort | ✅ |
| B4 | ~~`exclude_artists` silent no-op~~ | `warnings[]` | ✅ |

### Приоритет C — инженерия

| # | Что | Где | Зачем |
|---|-----|-----|--------|
| C1 | ~~Нет тестов feedback-path~~ | `test_playlist.py` | ✅ |
| C2 | ~~Дубль discovered vs feedback expand~~ | `retrieval_service` | ✅ `_expand_by_artist_names` |
| C3 | ~~Дубль generate error handling~~ | form / result / utils | ✅ |
| C4 | ~~Размер `quality.py`~~ | `utils/quality/` | ✅ сплит |
| C5 | ~~Cost-per-playlist (LLM tokens + # Yandex calls)~~ | `generation_cost` JSONB + лог + `GET /metrics/product` | ✅ 2026-09-18 |
| C6 | E2E smoke vs staging Яндекс в CI | optional | Когда будет test-аккаунт |

**Порядок:** P1.1 Telegram E2E; C6 по необходимости.

---

## Dev-инструменты

| Инструмент | Статус |
|------------|--------|
| `ruff` | ✅ в `pyproject.toml` |
| `pytest` | ✅ auth, health, llm, retrieval, scoring, quality, playlist, export, golden |
| `tsc` | ✅ `make typecheck` |
| `vitest` | ✅ auth-gates + playlist form (`make test-frontend`) |
| CI (`.github/`) | ✅ `ci.yml` |

```bash
cd backend
ruff check app tests
ruff format .
pytest
```
