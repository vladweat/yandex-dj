# Технологический стек

## Приложение

| Область | Технологии |
| --- | --- |
| Backend API | Python 3.12, FastAPI, Uvicorn |
| Модели и миграции | SQLAlchemy, Pydantic, Alembic |
| Хранение | PostgreSQL 15, Redis 7 |
| Web | Next.js 15, React 19, TypeScript 5, Tailwind CSS 4 |
| Frontend state и тесты | TanStack Query, Zustand, Vitest |
| Telegram | aiogram 3 и Telegram Mini Apps SDK |

## Генерация музыки

- LLM API формирует структурированный MusicProfile.
- sentence-transformers и multilingual E5 используются для embedding-based ранжирования.
- Яндекс Музыка предоставляет каталог и экспорт плейлистов.
- AI-обложки генерируются отдельно и отображаются в web-приложении.

Точные версии и параметры моделей настраиваются в исходном коде и конфигурации. Схема профиля описана в [LLM_SCHEMA.md](LLM_SCHEMA.md), компоненты — в [ARCHITECTURE.md](ARCHITECTURE.md).

## Сборка и проверки

Backend-зависимости определены в backend/pyproject.toml и устанавливаются через pip. Frontend использует package.json и package-lock.json. Локальная Compose-топология описана в [INFRASTRUCTURE.md](INFRASTRUCTURE.md); команды проверок — в [TESTING.md](TESTING.md).
