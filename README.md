# Промпт-диджей (Prompt DJ) для Яндекс Музыки

Программный комплекс для формирования персонализированных плейлистов в Яндекс Музыке на основе произвольного текстового описания на естественном языке.

**Пример:** *«спокойная музыка для кодинга поздней ночью с элементами эмбиента и лоу-фая без слов»* → готовый плейлист в аккаунте за 7–12 секунд.

## Стек

| Подсистема | Технологии |
|------------|------------|
| Бэкенд | **FastAPI** + uvicorn (`backend/`) |
| LLM | OpenAI + `instructor` |
| Embeddings | `sentence-transformers`, `numpy` |
| БД | PostgreSQL 15 + SQLAlchemy |
| Dev | `ruff`, `pytest`, `click` |

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
│   ├── app/
│   │   ├── api/        # endpoints, deps
│   │   ├── core/       # config, security
│   │   ├── services/   # бизнес-логика
│   │   ├── schemas/
│   │   ├── repositories/
│   │   └── db/
│   ├── tests/
│   ├── Dockerfile          # offline: COPY site-packages
│   └── pyproject.toml
├── scripts/
│   ├── build-venv.sh
│   └── pack-offline-bundle.sh
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
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Roadmap |

## Лицензия

MIT
