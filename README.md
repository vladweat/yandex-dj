# Промпт-диджей (Prompt DJ) для Яндекс Музыки

Программный комплекс для формирования персонализированных плейлистов в Яндекс Музыке на основе произвольного текстового описания на естественном языке.

**Пример:** *«спокойная музыка для кодинга поздней ночью с элементами эмбиента и лоу-фая без слов»* → готовый плейлист в аккаунте за 7–12 секунд.

## Стек

| Подсистема | Технологии |
|------------|------------|
| Язык | Python 3.12 |
| API Яндекс Музыки | `yandex-music` v3+ |
| LLM | OpenAI (`openai` SDK, `gpt-4o-mini`) + `instructor` |
| Embeddings | `sentence-transformers`, `numpy` |
| Бэкенд / UI | **FastAPI** + uvicorn |
| БД | **PostgreSQL 15** + SQLAlchemy |
| CLI | `click` |
| Dev | `ruff`, `pytest` |

Полный список: [docs/STACK.md](docs/STACK.md)

## Быстрый старт

```bash
cd yandex-dj
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
docker compose up -d db

uvicorn prompt_dj.api.main:app --reload
# Swagger: http://localhost:8000/docs
```

## Структура проекта

```
yandex-dj/
├── src/prompt_dj/
│   ├── api/            # FastAPI (/api/v1/...)
│   ├── auth/           # Device Flow, Fernet, сессии
│   ├── db/             # PostgreSQL / SQLAlchemy
│   ├── llm/            # MusicProfile, instructor + OpenAI
│   ├── candidates/     # async retrieval
│   ├── scoring/        # sentence-transformers
│   ├── export/         # playlist builder
│   └── pipeline.py
├── docs/
└── tests/
```

## Документация

| Документ | Содержание |
|----------|------------|
| [STACK.md](docs/STACK.md) | Зафиксированный стек |
| [SPEC.md](docs/SPEC.md) | Техническое задание |
| [API.md](docs/API.md) | REST API контракты |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Архитектура |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Roadmap |

## Лицензия

MIT
