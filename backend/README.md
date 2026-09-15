# Backend (FastAPI)

## Запуск

```bash
make up              # api + db + redis в Docker
make migrate         # alembic в контейнере (как docwise)
make test            # pytest в контейнере

# CLI на хосте — OAuth (нужен HTTPS_PROXY)
cd backend && pip install -e ".[dev]"
prompt-dj auth start

# Poll (нужен DATABASE_URL=@db) — через Makefile:
make auth-poll   # = docker compose exec api python -m app.cli.main auth poll
```

- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## CLI (отладка пайплайна)

```bash
# LLM
prompt-dj llm parse "dark synthwave for night coding"

# Retrieval (нужен YANDEX_OAUTH_TOKEN)
prompt-dj retrieval fetch --prompt "dark synthwave" --token "$YANDEX_OAUTH_TOKEN"

# Scoring (LLM → retrieval → rank)
prompt-dj scoring rank --prompt "dark synthwave for night coding" --token "$YANDEX_OAUTH_TOKEN"
```

Контракты HTTP: [docs/API.md](../docs/API.md).

## Структура

```
app/
├── main.py                 # точка входа FastAPI (+ warmup embeddings)
├── api/
│   ├── deps.py             # Depends: db, services
│   └── v1/
│       ├── router.py
│       └── endpoints/      # health, auth, llm, retrieval, scoring, playlists
├── core/
│   ├── config.py           # Settings
│   ├── embedding.py        # sentence-transformers loader
│   ├── security.py         # Fernet
│   └── exceptions.py
├── db/
│   ├── session.py
│   └── models/
├── schemas/                # Pydantic request/response
├── repositories/           # доступ к БД
├── services/               # бизнес-логика
├── utils/                  # tracks, scoring, search_queries
└── cli/                    # click (отладка)
```

### Слои (async)

| Слой | Назначение |
|------|------------|
| `endpoints` | `async def` — HTTP, вызов service |
| `services` | `async def` — бизнес-логика |
| `repositories` | `async def` — CRUD через `AsyncSession` |
| `schemas` | Pydantic request/response |
| `core` | config, security, exceptions |
| `db` | `create_async_engine` + asyncpg |

`DATABASE_URL=postgresql+asyncpg://...` — для приложения.  
Alembic использует sync URL (`postgresql+psycopg2://...`) автоматически.

## Dev

```bash
pytest
ruff check app tests
```

## Docker (offline)

```bash
# online — Python 3.12 на хосте; для scoring нужен [ml]:
pip install -e ".[ml,dev]"

make venv          # venv + модель e5-base + libgomp

# offline
make build && make up
```

См. [docs/INFRASTRUCTURE.md](../docs/INFRASTRUCTURE.md)
