# Prompt DJ для Яндекс Музыки

Сервис преобразует текстовый промпт в `MusicProfile`, собирает кандидатов из
Яндекс Музыки, ранжирует их и экспортирует готовый плейлист в аккаунт
пользователя. Реализованы Device Flow, история и повторная генерация,
персонализация по библиотеке, feedback, продуктовые метрики, web UI и заготовка
Telegram Mini App.

Целевой latency пайплайна — 7–12 секунд; серверный hard timeout по умолчанию —
90 секунд. Это целевые показатели, а не гарантия для любого окружения.

## Стек

| Подсистема | Реализация |
|---|---|
| API | Python 3.11+, FastAPI, uvicorn |
| Данные | PostgreSQL 15, SQLAlchemy 2 async, asyncpg, Alembic |
| Кэш | Redis 7 |
| ML/LLM | OpenAI-compatible API, `instructor`, `sentence-transformers`, NumPy |
| Web | Next.js 15, React 19, Tailwind CSS 4 |
| Telegram | aiogram 3, Telegram Mini App |
| Проверки | pytest, ruff, TypeScript, Vitest |

Версии и ограничения: [docs/STACK.md](docs/STACK.md).

## Предварительные требования

- Python 3.12 для воспроизводимой локальной и Docker-сборки
  (`pyproject.toml` допускает 3.11+, но Docker и CI используют 3.12);
- Node.js 20 для frontend;
- Docker с Compose для PostgreSQL, Redis и полного стека;
- действующие ключи внешних API — только для live Device Flow и генерации.

## Быстрый старт

Полный Compose-сценарий использует offline-ориентированные Dockerfile: перед
первой сборкой нужны локальные Python- и Node-артефакты.

```bash
cp backend/.env.example backend/.env
# Заполнить как минимум TOKEN_ENCRYPTION_KEY; для live-генерации также OPENAI_API_KEY.

make install          # backend/.venv, embedding-модель и libgomp
make deps-frontend    # frontend/node_modules для offline Docker build
make build            # образы api и bot
make up-frontend      # собрать и запустить frontend
make up               # api, db, redis, bot и frontend
make migrate
```

После запуска:

- UI: <http://localhost:3001>
- OpenAPI UI: <http://localhost:8000/docs>
- health: <http://localhost:8000/api/v1/health>

`make up` запускает также `bot`; без `TG_BOT_TOKEN` этот контейнер может
завершиться. Для разработки только backend сначала достаточно
`docker compose up -d db redis` и локального uvicorn:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[ml,dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

## Проверки

```bash
# Backend unit checks; TOKEN_ENCRYPTION_KEY должен быть валидным Fernet-ключом.
cd backend
ruff check app tests
python -m pytest tests/ -q

# Frontend unit checks.
cd ../frontend
npm ci
npm run typecheck
npm test
```

CI не вызывает live Яндекс/OpenAI API и не загружает embedding-модель. Подробно:
[docs/TESTING.md](docs/TESTING.md).

## Конфигурация

Backend загружает `backend/.env` через `Settings` в
`backend/app/core/config.py`; Compose подменяет адреса PostgreSQL и Redis.
Frontend получает `NEXT_PUBLIC_API_URL` во время `next build`, поэтому смена
переменной только у уже запущенного контейнера не меняет browser bundle.

Не коммитьте `.env`, OAuth-токены и Fernet-ключи. Полный каталог переменных:
[docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Структура

```text
backend/app/
  api/            HTTP и DI
  services/       бизнес-логика и orchestration
  repositories/   SQLAlchemy-запросы
  db/models/      модели данных
  schemas/        Pydantic-контракты
  core/           config, security, exceptions
frontend/src/
  app/            Next.js App Router
  features/       auth, playlist, Telegram
  lib/api.ts      browser API client
docs/             инженерная и продуктовая документация
```

## Документация

Начальная точка — [docs/README.md](docs/README.md). Основные документы:

- [архитектура и data flow](docs/ARCHITECTURE.md);
- [REST API](docs/API.md);
- [БД и транзакции](docs/DATABASE.md);
- [локальная разработка](docs/DEVELOPMENT.md);
- [эксплуатация и troubleshooting](docs/OPERATIONS.md);
- [security-модель](docs/SECURITY.md);
- [технический долг и риски](docs/TECHNICAL_DEBT.md).

Правила для участников: [CONTRIBUTING.md](CONTRIBUTING.md); краткие инструкции
для coding agents: [AGENTS.md](AGENTS.md).

## Известные ограничения

- генерация выполняется синхронно внутри HTTP-запроса; очереди задач нет;
- `/health` проверяет только процесс приложения, но не PostgreSQL, Redis и API;
- AI-обложки хранятся на локальном диске API и не загружаются в Яндекс Музыку;
- production deployment, TLS/reverse proxy и backup automation в репозитории не
  определены;
- Telegram E2E пока не подтверждён, см. [docs/TELEGRAM.md](docs/TELEGRAM.md).

## Лицензия

MIT
