# Telegram (P1.1) — состояние на 2026-09-18

> **Статус: пауза.** Код в репозитории; E2E в Telegram с dev-server **не доведён** (нет стабильного доступа к `api.telegram.org`).

## Решение по продукту

- **Mini App** — тот же simple UI, что `/` (паритет формы).
- **Thin bot** (`aiogram`) — `/start`, Menu → Web App; генерация только через Mini App + существующий `POST /playlists/generate`.
- **Метрики:** `playlist_generations.client_channel` (`web` | `telegram`), `GET /metrics/product` → `generations_telegram` / `generations_web`; опционально `users.telegram_user_id` через `POST /auth/telegram/link`.

## Что сделано (в коде)

| Слой | Артефакт |
|------|----------|
| Frontend | `/tg`, `/tg/login`, `@twa-dev/sdk`, `X-Client-Channel: telegram`, `AppRoutes` для login |
| Backend API | `X-Client-Channel` на generate, `POST /auth/telegram/link`, `AuthMe.telegram_user_id` |
| БД | миграция `c4d5e6f7a8b9`: `client_channel`, `users.telegram_user_id` |
| Bot | `backend/app/bot/main.py`, сервис `bot` в `docker-compose.yml`, прокси как у Яндекса + `aiohttp-socks` |
| Конфиг | `TG_BOT_TOKEN`, `TELEGRAM_WEB_APP_URL`, `TELEGRAM_BOT_USE_PROXY` (см. `.env.example`) |
| Сборка | `make build` → `api` + `bot` |

## Что не закрыто (блокер)

На **dev-server** исходящие к Telegram через корпоративный `HTTPS_PROXY` дают **timeout** (`Proxy connection timed out: 60`). Без связи с `api.telegram.org` не работают polling, `/start`, Menu API.

В Docker без прокси ранее был **DNS** до `api.telegram.org` (отдельная проблема сети контейнера).

**DoD PRODUCT «Есть канал»** (плейлист из Telegram в аккаунте Яндекса) — **не выполнен** до появления рабочего маршрута к Telegram API.

## Как продолжить (чеклист)

1. `make migrate` (если ещё не: `c4d5e6f7a8b9`).
2. Зависимости: `aiohttp-socks` в venv → `docker compose build --no-cache api bot`.
3. Сеть (один из вариантов):
   - прокси с доступом к `api.telegram.org`;
   - `TELEGRAM_BOT_USE_PROXY=false` + прямой выход/DNS из контейнера или хоста;
   - бот на **другой машине** (только `TG_BOT_TOKEN` + polling), API/фронт остаются на сервере;
   - Mini App: **HTTPS** tunnel на `/tg` + доступный с телефона `NEXT_PUBLIC_API_URL`.
4. BotFather: Web App URL = `TELEGRAM_WEB_APP_URL`.
5. Проверка:
   - логи: `Telegram API ok, bot @…`, `Received /start`;
   - SQL: `client_channel = 'telegram'` после генерации из Mini App;
   - `telegram_user_id` заполняется только внутри реального WebView (не в обычном браузере на `/tg`).

## Локальная отладка без Telegram

- Web: `http://localhost:3001/tg` — тот же UI и API (канал в метриках останется `web`, пока не Mini App).
- Бот в compose можно не поднимать: `docker compose up -d api frontend db redis`.

## Ссылки

- [API.md](API.md) — `X-Client-Channel`, `/auth/telegram/link`
- [FRONTEND.md](FRONTEND.md) — маршруты `/tg`
- [DEVELOPMENT.md](DEVELOPMENT.md) — env и compose
