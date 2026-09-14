# Промпт-диджей (Prompt DJ) для Яндекс Музыки

Программный комплекс для формирования персонализированных плейлистов в Яндекс Музыке на основе произвольного текстового описания на естественном языке.

**Пример:** *«спокойная музыка для кодинга поздней ночью с элементами эмбиента и лоу-фая без слов»* → готовый плейлист в аккаунте за 7–12 секунд.

## Стек

| Подсистема | Технологии |
|------------|------------|
| Бэкенд | **FastAPI** + uvicorn (`backend/`) |
| Frontend | **Next.js 15** + Tailwind 4 + shadcn (`frontend/`, каркас из docwise) |
| LLM | OpenAI + `instructor` |
| Embeddings | `sentence-transformers`, `numpy` |
| БД | PostgreSQL 15 + SQLAlchemy |
| Dev | `ruff`, `pytest`, `click`, `vitest` |

Полный список: [docs/STACK.md](docs/STACK.md)

## Быстрый старт

```bash
# PostgreSQL
docker compose up -d db

# Backend
make install          # production venv + модель (для Docker)
# dev без Docker:
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Подробнее: [backend/README.md](backend/README.md)

## Структура репозитория

```
yandex-dj/
├── backend/
│   ├── app/            # FastAPI (api, services, schemas, db)
│   ├── tests/
│   ├── Dockerfile      # offline: COPY site-packages
│   └── pyproject.toml
├── frontend/           # Next.js (порт из docwise)
│   └── src/
│       ├── app/
│       ├── features/
│       └── components/
├── scripts/
├── Makefile
├── docs/
└── docker-compose.yml
```

## Документация

| Документ | Содержание |
|----------|------------|
| [STACK.md](docs/STACK.md) | Зафиксированный стек |
| [SPEC.md](docs/SPEC.md) | Техническое задание |
| [API.md](docs/API.md) | REST API контракты |
| [FRONTEND.md](docs/FRONTEND.md) | UI/UX, маршруты, Device Flow |
| [REUSE_FROM_DOCWISE.md](docs/REUSE_FROM_DOCWISE.md) | Карта порта из docwise |
| [CONVENTIONS.md](docs/CONVENTIONS.md) | Слои backend и frontend |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Roadmap |

## Лицензия

MIT
