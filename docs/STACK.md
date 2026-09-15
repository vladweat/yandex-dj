# Стек технологий (зафиксирован)

> Итоговые решения по инструментам и библиотекам. При расхождении с черновиками в других документах — приоритет у этого файла.

## Язык и окружение

| Компонент | Выбор |
|-----------|-------|
| Python | 3.12 (совместим с 3.11+) |
| Менеджер зависимостей | `pip` + `venv` |
| Сборка | `pyproject.toml` |
| Линтер / форматтер | **ruff** |
| Тесты | **pytest** |
| Контейнеризация | Docker + Docker Compose |

## Яндекс Музыка

| Компонент | Выбор |
|-----------|-------|
| Клиент API | **yandex-music[async]** v3+ (`ClientAsync`, `aiohttp`) |
| Авторизация | OAuth Device Flow |
| Хранение токена | PostgreSQL (зашифрован Fernet) |

## LLM

| Компонент | Выбор |
|-----------|-------|
| Провайдер | **OpenAI** (только API, без Ollama) |
| SDK | **openai** (официальный) |
| Модель | `gpt-4o-mini` (основная), `gpt-4o` (при необходимости) |
| Structured output | **instructor** + Pydantic v2 |
| Схема | `MusicProfile` |

## Embeddings и скоринг

| Компонент | Выбор | Примечание |
|-----------|-------|------------|
| Библиотека | **sentence-transformers** | С этапа scoring |
| Модель | `intfloat/multilingual-e5-base` | Меньше RAM на dev-машине |
| Математика | **numpy** | Cosine similarity |
| Fallback | Жанры + популярность | При сбое загрузки модели |

Embeddings подключаются **сразу** (не откладываются на поздний этап).

## Бэкенд

| Компонент | Выбор |
|-----------|-------|
| Framework | **FastAPI** |
| ASGI-сервер | **uvicorn** |
| CLI (вспомогательный) | **click** |

## Frontend

| Компонент | Выбор |
|-----------|-------|
| Framework | **Next.js 15** (App Router) |
| UI | **React 19**, **TypeScript 5**, **Tailwind CSS 4** |
| Компоненты | **shadcn/ui** (Radix) |
| Состояние | **TanStack Query** + **Zustand** |
| Тесты UI | **Vitest** |
| Каркас | Порт из **docwise** ([REUSE_FROM_DOCWISE.md](REUSE_FROM_DOCWISE.md)) |

Авторизация UI: Bearer `session_id` (Device Flow), не cookie. Подробнее: [FRONTEND.md](FRONTEND.md).

Telegram-бот — этап 7 backlog ([DEVELOPMENT.md](DEVELOPMENT.md)).

## База данных

| Компонент | Выбор |
|-----------|-------|
| СУБД | **PostgreSQL 15** (Docker-образ `postgres:15`) |
| ORM | **SQLAlchemy** |
| Миграции | **Alembic** (`users` / `sessions` и далее) |
| Шифрование токенов | **cryptography** (Fernet) |

SQLite не используется.

## Кэш

| Компонент | Выбор | Назначение |
|-----------|-------|------------|
| Redis 7 | Кэш метаданных треков | retrieval |

## Конфигурация

| Компонент | Выбор |
|-----------|-------|
| Настройки | **pydantic-settings** |
| Переменные окружения | `.env` + **python-dotenv** |

## Не используем на MVP

| Компонент | Причина |
|-----------|---------|
| Ollama / локальные LLM | OpenAI API; 3.8 GiB RAM |
| SQLite | PostgreSQL с первого этапа |
| typer | click |
| Telegram / aiogram | FastAPI первым |
| Celery / Arq | Пайплайн укладывается в 7–12 сек |
| Qdrant | Пул 150–300 в памяти |
| scikit-learn | Достаточно numpy |

## Зависимости (сводка)

```
# core
yandex-music[async]
pydantic
pydantic-settings
python-dotenv
cryptography

# llm
openai
instructor

# ml
sentence-transformers
numpy
torch  # transitive dep of sentence-transformers

# api
fastapi
uvicorn[standard]

# db (async runtime + sync migrations)
sqlalchemy[asyncio]
asyncpg
psycopg2-binary  # только Alembic
alembic

# cli
click

# dev
pytest
ruff
httpx  # тесты FastAPI
```

## Docker-сервисы

```yaml
services:
  db:        postgres:15
  redis:     redis:7
  api:       prompt-dj-api (offline build, см. ниже)
  frontend:  node:20-alpine → Next.js :3001
```

Порты по умолчанию: API `8000`, frontend `3001` (как docwise, без конфликта с другими проектами).

## Offline / air-gapped deploy

Сборка образа **без интернета**: venv, модель и `.libs` готовятся на хосте с Python 3.12.

| Этап | Где | Команда |
|------|-----|---------|
| 1. Venv + модель | online | `make venv` |
| 2. Перенос | USB / registry | `make pack` или `docker save` |
| 3. Образ | **offline** | `make build` |
| 4. Запуск | offline | `make up` |

**Правила:**

- хост: **Python 3.12** (та же версия, что `python:3.12-slim`)
- в образ копируется `.venv/lib/python3.12/site-packages/` → `/usr/local/lib/python3.12/site-packages/`
- модель: `backend/.models` → `/opt/models`; `HF_HUB_OFFLINE=1`
- `libgomp.so.1` → `backend/.libs` (для torch в slim)
- `pip install -e` **не используется** — только `pip install ".[ml]"`
- исходник зависимостей: `pyproject.toml`

Подробнее: [INFRASTRUCTURE.md](INFRASTRUCTURE.md)
