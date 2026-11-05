# Инфраструктура и offline-сборка

Документ описывает локальную Docker Compose-топологию и подготовку offline-
артефактов. Команды запуска сервисов приведены в [OPERATIONS.md](OPERATIONS.md).

## Локальная топология

| Сервис | Порт host | Назначение |
| --- | ---: | --- |
| API | 8000 | FastAPI |
| PostgreSQL | 5432 | пользователи, сессии и история |
| Redis | 6379 | кэш метаданных треков |
| Frontend | 3001 в Compose, 3000 в dev server | Next.js |
| Bot | — | Telegram polling; нужен `TG_BOT_TOKEN` |

Compose открывает порты локально для разработки. Настройки не предназначены
для прямого production-развёртывания.

## Подготовка offline-артефактов

Backend Dockerfile копирует Python-зависимости из `backend/.venv`, embedding
модель из `backend/.models` и `libgomp.so.1` из `backend/.libs`. Подготовка
выполняется `scripts/build-venv.sh`: она устанавливает CPU PyTorch, extra `ml`
и скачивает модель. Скрипт рассчитан на Python 3.12 и Linux x86_64; он использует системную
библиотеку libgomp.so.1.

Frontend Dockerfile собирает Next.js из заранее подготовленного
`frontend/node_modules`; Compose отключает сеть для этого build. Подготовить
зависимости нужно до сборки образа командой
`bash frontend/scripts/prepare-deps.sh`.

Обе процедуры требуют доступа к package index и model registry во время
подготовки. После этого `docker compose build` использует локальные артефакты.
Unit-проверки backend не требуют этих ML- и Docker-артефактов:
`./scripts/test-backend.sh`.

## Состав Compose

- `api` — локальный FastAPI с reload и bind mounts;
- `db` — PostgreSQL 15 с named volume;
- `redis` — Redis 7;
- `frontend` — Next.js production server;
- `bot` — Telegram polling, если настроен токен.

См. [OPERATIONS.md](OPERATIONS.md) для запуска и
[SECURITY.md](SECURITY.md) для ограничений конфигурации.
