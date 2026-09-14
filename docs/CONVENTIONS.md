# Соглашения репозитория

## Каталоги (целевые)

```
yandex-dj/
  backend/
    app/                 # FastAPI (async)
      api/v1/endpoints/  # HTTP: один модуль на ресурс
      api/deps.py        # AsyncSession, get_current_session
      core/              # config, security, exceptions, proxy
      schemas/           # Pydantic in/out
      services/          # бизнес-логика
      repositories/      # доступ к БД
      db/models/         # SQLAlchemy ORM
      cli/               # click, отладка
    alembic/
    tests/
  frontend/              # Next.js App Router (каркас из docwise)
    src/
      app/               # RSC-маршруты и metadata
      features/          # auth, playlist, health
      components/        # shell + shadcn ui/
      lib/               # api.ts, format, reset-client-state
      stores/            # toast и пр.
      types/             # контракты API
  scripts/
  docs/
  .cursor/rules/
  docker-compose.yml
  Makefile
```

### Слои backend

| Слой | Что входит | Что нет |
| --- | --- | --- |
| `core/` | Settings, Fernet, proxy, exceptions | Доменные правила |
| `services/` | Auth, playlist, LLM, retrieval, scoring, yandex | `HTTPException` |
| `api/v1/endpoints/` | Парсинг запроса, deps, вызов service | Бизнес-логика |
| `repositories/` | CRUD User, Session | HTTP, Яндекс API |
| `schemas/` | Pydantic; `MusicProfile` в `llm.py` | ORM-модели |

### Слои frontend

| Слой | Что входит | Что нет |
| --- | --- | --- |
| `app/` | RSC-маршрут, `metadata`, сборка островов | `"use client"` на `page.tsx` |
| `features/` | Экран фичи, её Zustand, узкие helpers | Общий `api.ts`, shadcn |
| `components/ui` | shadcn/Radix-примитивы | Вёрстка страниц |
| `lib/` | `api.ts`, format, reset-client-state | Парсинг ответов внутри экранов |

Каркас UI — из `../docwise` ([REUSE_FROM_DOCWISE.md](REUSE_FROM_DOCWISE.md)).

## Язык

- Код, идентификаторы API, комментарии в коде: английский.
- Пользовательские строки UI: русский.
- `docs/*`: русский.
- Источник истины: [SPEC.md](SPEC.md), [API.md](API.md), [STACK.md](STACK.md).

## Git и секреты

- Не коммитить `.env`, OAuth-токены, `backend/.auth/pending.json`.
- Пример: `backend/.env.example`.
- Коммиты — по запросу владельца репозитория.

## Качество кода

- Backend: **ruff**, **pytest** (`make test` в Docker).
- Frontend: TypeScript strict, shadcn, без `any` в API-слое.
- Изменение контракта API = обновление [API.md](API.md) в том же изменении.
- Новая продуктовая фича вне SPEC = сначала правка [SPEC.md](SPEC.md).

## Что не делать

- Не копировать из docwise cookie-auth и org/SSO/billing без адаптации.
- Не хранить расшифрованный OAuth-токен Яндекса на клиенте.
- Не вызывать API Яндекса напрямую из браузера.
