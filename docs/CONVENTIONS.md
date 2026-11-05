# Соглашения по структуре кода

Код организован по направлениям зависимостей. Изменения должны сохранять явные интерфейсы между HTTP, бизнес-логикой, хранением данных и frontend.

## Структура

~~~text
yandex-dj/
  backend/
    app/
      api/v1/endpoints/  # HTTP и mapping запросов
      api/deps.py        # DI и сессия пользователя
      core/              # конфигурация, безопасность, интеграции
      schemas/           # входные и выходные контракты
      services/          # бизнес-логика
      repositories/      # доступ к БД
      db/models/         # ORM-модели
    alembic/             # миграции
    tests/
  frontend/
    src/
      app/               # маршруты Next.js
      features/          # функции приложения
      components/        # общие компоненты
      lib/               # API-клиент и helpers
      types/             # типы API
  scripts/
  docs/
~~~

## Backend

- HTTP: endpoints → services → repositories → db/models.
- Services не зависят от FastAPI и HTTP-исключений.
- DI и пользовательская сессия подключаются через backend/app/api/deps.py.
- MusicProfile находится в backend/app/schemas/llm.py.

## Frontend

- Маршруты и metadata находятся в src/app.
- Экраны и локальное состояние функций находятся в src/features.
- Общий browser API-клиент находится в src/lib/api.ts.
- API-типы синхронизируются с backend schemas.

## Документы и проверки

- API-контракт описан в [API.md](API.md); обзор системы — в [ARCHITECTURE.md](ARCHITECTURE.md).
- Команды проверок собраны в [TESTING.md](TESTING.md).
- Код, миграции и исполняемая конфигурация имеют приоритет над описанием.
- Изменения scoring/retrieval проверяются на golden-сценариях.
