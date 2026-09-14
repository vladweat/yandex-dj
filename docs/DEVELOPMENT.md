# План разработки (Roadmap)

Стек: [STACK.md](STACK.md). ТЗ: [SPEC.md](SPEC.md).

## Этап 1. Инфраструктура, PostgreSQL, FastAPI, авторизация

**Цель:** скелет приложения и OAuth Device Flow.

- [ ] `pyproject.toml`: зависимости из STACK.md, dev-группа (`ruff`, `pytest`, `httpx`)
- [ ] `docker-compose.yml`: PostgreSQL 15
- [ ] SQLAlchemy: модели `User`, `Session` (зашифрованный токен)
- [ ] Fernet-шифрование OAuth-токена перед записью в БД
- [ ] FastAPI: каркас приложения, `/api/v1/health`
- [ ] Device Flow endpoints: `auth/device-flow/start`, `auth/device-flow/poll`
- [ ] Обёртка `YandexMusicClient`: retry, rate limiting
- [ ] `click`-команды для отладки: `auth test`, `db init`

**Проверка:** Device Flow через API → токен в PostgreSQL → профиль пользователя Яндекс Музыки.

## Этап 2. LLM Engine

**Цель:** промпт → `MusicProfile` через OpenAI + instructor.

- [ ] Pydantic-модель `MusicProfile` ([LLM_SCHEMA.md](LLM_SCHEMA.md))
- [ ] Системный промпт + few-shot примеры
- [ ] `instructor` + `openai` SDK (`gpt-4o-mini`)
- [ ] FastAPI endpoint или внутренний сервис для парсинга
- [ ] 10–15 тестов с разноплановыми промптами (`pytest`)

**Проверка:** тестовые промпты → валидный `MusicProfile`.

## Этап 3. Retrieval Engine

**Цель:** `MusicProfile` → пул 150–300 кандидатов.

- [ ] `CandidateCollector`: `search` + `artists_tracks` (топ-10) + `tracks_similar`
- [ ] Async через `asyncio`
- [ ] Дедупликация: `track.id` + «Артист + Название»
- [ ] Фильтр `available == False`
- [ ] Redis: кэш метаданных треков (`docker compose` + `redis:7`)

**Проверка:** пул 150+ треков за < 4 сек.

## Этап 4. Scoring Module

**Цель:** кандидаты → отранжированный топ-N (embeddings сразу).

- [ ] `sentence-transformers` (`intfloat/multilingual-e5-base`)
- [ ] Паспорта треков (формат из ТЗ)
- [ ] Batch-эмбеддинг + cosine similarity (`numpy`)
- [ ] Diversity: 2 трека/артист (N≤25), 3 (N 26–50)
- [ ] Fallback: жанры + популярность

**Проверка:** 25 релевантных треков; скоринг < 2 сек.

## Этап 5. Export + end-to-end API

**Цель:** полный пайплайн через FastAPI.

- [ ] `Pipeline.run()` — LLM → retrieval → scoring → export
- [ ] `POST /api/v1/playlists/generate` ([API.md](API.md))
- [ ] Экспорт: create + insert + description + URL
- [ ] Метрики latency по этапам в логах

**Проверка:** промпт через API → ссылка на плейлист за 7–12 сек.

## Этап 6. Backlog

- [ ] Next.js фронтенд
- [ ] Telegram-бот (`aiogram`)
- [ ] BPM-анализ (`librosa`)
- [ ] AI-обложка, анализ lyrics
- [ ] Celery/Arq при необходимости async-генерации

## Dev-инструменты

```bash
ruff check .
ruff format .
pytest
```
