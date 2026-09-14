# Backend (FastAPI)

## Запуск

```bash
make up              # api + db в Docker
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

## Структура

```
app/
├── main.py                 # точка входа FastAPI
├── api/
│   ├── deps.py             # Depends: db, services
│   └── v1/
│       ├── router.py
│       └── endpoints/      # health, auth, playlists
├── core/
│   ├── config.py           # Settings
│   ├── security.py         # Fernet
│   └── exceptions.py
├── db/
│   ├── session.py
│   └── models/
├── schemas/                # Pydantic request/response
├── repositories/           # доступ к БД
├── services/               # бизнес-логика
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
# online — Python 3.12 на хосте
make venv

# offline
make build && make up
```

См. [docs/INFRASTRUCTURE.md](../docs/INFRASTRUCTURE.md)
