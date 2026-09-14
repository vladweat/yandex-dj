# Инфраструктура и окружение

Снимок состояния dev-машины на момент старта проекта (2026-09-14).

## Системные ресурсы

| Параметр | Значение | Влияние на проект |
|----------|----------|-------------------|
| CPU | 4 ядра | Параллельный сбор кандидатов, батчевая векторизация |
| RAM | 3.8 GiB (доступно ~2.6 GiB) | Ограничение: тяжёлые LLM локально; предпочесть `gpt-4o-mini` API или лёгкие модели |
| Диск | 9.4 GiB свободно (83% занято) | `bge-m3` (~2 GB) + зависимости — следить за местом |
| Python | 3.12.3 | Совместим с требованием 3.11+ |
| Docker | 29.8.0 | Готов к контейнеризации |
| Docker Compose | v5.5.1 | Готов к `docker-compose.yml` |

## Что не установлено локально

| Компонент | Статус | Решение |
|-----------|--------|---------|
| Ollama | Не установлен | `docker run` или OpenAI API |
| redis-cli | Нет | Контейнер `redis:7` (образ есть) |
| psql | Нет | Контейнер `postgres:15` (образ есть) |

## Docker-образы, релевантные для проекта

| Образ | Размер | Назначение в Prompt DJ |
|-------|--------|------------------------|
| `python:3.12-slim` | 179 MB | Базовый образ бэкенда |
| `postgres:15` | 633 MB | PostgreSQL (продакшен) |
| `redis:7` | 170 MB | Кэш метаданных, сессии, Celery broker |
| `nginx:alpine` | 93.6 MB | Reverse proxy для FastAPI + Next.js |
| `node:20-alpine` | 194 MB | Сборка фронтенда Next.js |

Другие образы на машине (`chainwise-*`, `landlords-*`, `docwise-*`, `qdrant`, `minio`) — из других проектов, для MVP Prompt DJ не требуются.

## Рекомендуемая конфигурация для MVP

Учитывая 3.8 GiB RAM, для локальной разработки:

```yaml
# docker-compose.yml (текущий + планируемый frontend)
services:
  api:
    image: prompt-dj-api
    ports: ["8000:8000"]

  db:
    image: postgres:15

  redis:                 # этап 3+
    image: redis:7

  frontend:              # этап 1.5, как docwise
    build: ./frontend
    ports: ["3001:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
```

Frontend: offline-сборка — `node_modules` с хоста (`make deps-frontend`), образ без `npm install` в сети. См. docwise `frontend/Dockerfile`.

**Зафиксированный стек ([STACK.md](STACK.md)):**
- LLM: **OpenAI API** (`gpt-4o-mini`) — не нагружает RAM
- БД: **PostgreSQL 15** (образ есть)
- API: **FastAPI** `:8000`
- UI: **Next.js** `:3001` (каркас из docwise, [FRONTEND.md](FRONTEND.md))
- Эмбеддинги: `intfloat/multilingual-e5-base` (~1 GB)
- Ollama не используется

## Целевые метрики latency (из ТЗ)

| Этап | Бюджет |
|------|--------|
| LLM-парсинг | 2–3 сек |
| Сбор кандидатов (async) | 2–4 сек |
| Векторизация + скоринг | 1–2 сек |
| Экспорт плейлиста | 1–2 сек |
| **Итого** | **7–12 сек** |

## Переменные для Docker-окружения

См. `.env.example` — секции `DATABASE_URL`, `REDIS_URL`, `TOKEN_ENCRYPTION_KEY`.

## Offline-сборка Docker (без интернета)

Ограничение: на целевой машине при `docker build` сети нет. Пакеты копируются из `site-packages` локального venv.

### Online (подготовка артефактов)

```bash
# Базовые образы — сохранить для offline
docker pull python:3.12-slim postgres:15
docker save python:3.12-slim postgres:15 -o dist/base-images.tar

# Python 3.12 на хосте обязателен
make venv    # backend/.venv + .models + .libs

make pack    # dist/prompt-dj-offline-*.tar.gz
```

`make venv` выполняет:
1. `pip install ".[ml]"` в `backend/.venv`
2. копирует `libgomp.so.1` в `backend/.libs`
3. скачивает embedding-модель в `backend/.models`

### Offline (сборка и запуск)

```bash
docker load -i dist/base-images.tar
tar -xzf dist/prompt-dj-offline-YYYYMMDD.tar.gz -C /path/to/project

cd /path/to/project
cp backend/.env.example backend/.env   # заполнить секреты
make build
make up
```

### Файлы

| Файл | Назначение |
|------|------------|
| `Makefile` | `venv`, `build`, `up`, `pack` |
| `scripts/build-venv.sh` | venv + модель + libgomp |
| `backend/scripts/prepare_embeddings.py` | скачивание модели в `.models` |
| `scripts/pack-offline-bundle.sh` | tar.gz для переноса |
| `backend/Dockerfile` | COPY site-packages, без `pip install` |
| `backend/.dockerignore` | оставляет `.venv/lib`, исключает `.venv/bin` |

В Docker: `EMBEDDING_MODEL_PATH=/opt/models`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`.
