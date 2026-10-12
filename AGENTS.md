# Инструкции для coding agents

Область действия: весь репозиторий. Дополнительные правила находятся в
`.cursor/rules/`.

## Перед изменениями

1. Прочитайте [docs/README.md](docs/README.md) и профильный документ.
2. Считайте код и миграции источником истины; roadmap не доказывает наличие
   функциональности.
3. Не добавляйте regex под отдельный промпт, жанр или артиста.
4. Не меняйте scoring/retrieval после MVP без регресса
   `backend/tests/test_golden_prompts.py`.

## Границы

- HTTP: `backend/app/api/v1/endpoints/`; endpoint вызывает service.
- DI: `backend/app/api/deps.py`.
- Бизнес-логика: `backend/app/services/`.
- Данные: `backend/app/repositories/` и `backend/app/db/models/`.
- Контракты: `backend/app/schemas/`; канонический `MusicProfile` —
  `backend/app/schemas/llm.py`.
- Browser API client: `frontend/src/lib/api.ts`.
- Никогда не передавайте OAuth-токен Яндекса в frontend: клиенту выдаётся
  только Bearer `session_id`.

## Проверки

```bash
cd backend
ruff check app tests
python -m pytest tests/ -q

cd ../frontend
npm run typecheck
npm test
```

Для локальных auth/playlist-тестов нужен валидный `TOKEN_ENCRYPTION_KEY`.
Unit CI не проверяет live Яндекс/OpenAI, реальную embedding-модель, Docker build
или Telegram E2E.

## Изменения данных и контрактов

- Изменение модели БД требует новой Alembic-миграции; существующие миграции не
  переписывать.
- Изменение API требует синхронизации `docs/API.md`, Pydantic-схем,
  `frontend/src/types/` и `frontend/src/lib/api.ts`, если endpoint используется UI.
- Новую переменную окружения добавить в `backend/.env.example` и
  `docs/CONFIGURATION.md`; секретные значения не коммитить.
- При изменении команд, topology или startup обновить README и
  `docs/OPERATIONS.md`.
