# Техническое руководство

Этот файл помогает ориентироваться в структуре проекта. Актуальное поведение определяется исходным кодом, миграциями и конфигурацией.

## Основные границы

- HTTP endpoints находятся в backend/app/api/v1/endpoints и вызывают services.
- Бизнес-логика находится в backend/app/services.
- Репозитории и модели данных находятся в backend/app/repositories и backend/app/db/models.
- Pydantic-контракты находятся в backend/app/schemas; MusicProfile определён в llm.py.
- Browser API client и frontend types находятся в frontend/src/lib/api.ts и frontend/src/types.
- OAuth-токен Яндекса остаётся на backend; браузер получает только session_id.

## При изменениях

- Для изменения схемы БД добавляйте новую Alembic-миграцию; опубликованные миграции не переписывайте.
- При изменении API синхронизируйте docs/API.md, схемы backend и типы frontend.
- Новые переменные окружения добавляйте в backend/.env.example и docs/CONFIGURATION.md; секреты не коммитьте.
- При изменении startup-команд или Compose topology обновляйте README.md и docs/OPERATIONS.md.
- Изменения retrieval и scoring должны сохранять golden-регрессии описанные в docs/PLAYLIST_QUALITY.md.

## Проверки

Команды для backend и frontend собраны в [docs/TESTING.md](docs/TESTING.md). Для локальных auth- и playlist-проверок требуется TOKEN_ENCRYPTION_KEY.
