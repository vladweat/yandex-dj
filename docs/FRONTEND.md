# Frontend: UI/UX

Стек: Next.js 15 App Router, React 19, TypeScript 5, Tailwind CSS 4, shadcn/ui (Radix). Состояние: TanStack Query + Zustand.

Каркас копируется из соседнего репозитория **docwise** ([REUSE_FROM_DOCWISE.md](REUSE_FROM_DOCWISE.md)): `layout`, `components/ui`, `query-provider`, `toast-host`, `lib/api.ts`, auth-gates. Интерактив и сторы фичи — `src/features/{auth,playlist,health}`. Маршруты в `app/` — RSC (`metadata` + остров). Общий HTTP — `lib/api.ts`. Типы — `types/` (1:1 с Pydantic).

## Маршруты

| Путь | Экран |
| --- | --- |
| `/login` | OAuth Device Flow: код + ссылка на ya.ru/device, poll до `authenticated` |
| `/` | Генерация + результат + история; `?prompt=` prefill |
| `/health` | Статус API (опционально, для отладки) |
| `/debug` | Статус аккаунта Яндекс Музыки (опционально) |

## Авторизация (отличие от docwise)

Docwise: cookie-сессия, `credentials: "include"`, `POST /auth/login`.

Prompt DJ: **Bearer `session_id`** (UUID из Device Flow).

| Шаг | API |
| --- | --- |
| Старт | `POST /api/v1/auth/device-flow/start` |
| Poll | `POST /api/v1/auth/device-flow/poll` с `device_code` |
| Профиль | `GET /api/v1/auth/me` с `Authorization: Bearer <session_id>` |

Клиент хранит `session_id` в `localStorage` (ключ `prompt_dj_session_id`). В `lib/api.ts` — заголовок `Authorization`, без cookie refresh.

`auth-provider.tsx`: boot через `fetchMe()`; при 401 — сброс сессии. Logout — очистка `localStorage` + сброс TanStack Query / Zustand (`reset-client-state.ts`).

## Главный экран (генерация)

Одна колонка (без split-pane docwise):

1. **Форма:** промпт, `track_count`, `instrumental_only`, `diversity` (normal/high), `exclude_artists` (через запятую); кнопка «Отменить» во время запроса (`AbortController`).
2. **Prefill:** `?prompt=…` из query; draft из истории («Повторить») — **включая options**.
3. **Быстрые примеры:** кнопки под textarea (kitchen / coding / synthwave).
4. **Submit:** `POST /api/v1/playlists/generate`; при `401` — сброс → `/login`; `504` — toast таймаута; `warnings` — info toast.
5. **Состояния:** idle → loading («Генерируем…») → success | error; сеть/502/503 → баннер «API недоступен».
6. **Результат:** `title`, `description`, ссылка в Яндекс, «Копировать ссылку и промпт», «Ещё вариант» (`source_id` + **те же options**), badges `pool_stats`, блок `MusicProfile`, таблица треков.
7. **История:** `GET /api/v1/playlists` — список с `options`; клик → `GET /playlists/{id}`; «Повторить» → prefill промпта **и опций**.

Ошибки — тост/баннер, без разрыва страницы:

| Код | UX |
| --- | --- |
| `0` / сеть | Баннер + тост «API недоступен» |
| `401` | Сброс `session_id`, тост, редирект на `/login` |
| `422` | Валидация промпта под полем (1–2000 символов, `track_count` 1–50) |
| `499` (abort) | Тост «Генерация отменена» |
| `502` / `503` | Баннер/тост «API недоступен» |
| `504` | Тост: превышен `PIPELINE_TIMEOUT_SEC` |

Полный контракт: [API.md](API.md) § Playlists.  
Качество: [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md).

### Ручной тест UI

```bash
make up-frontend   # http://localhost:3001
# 1) /login → Device Flow
# 2) / → пример «под настроение пока варю макароны»
# 3) Ожидание: 25 треков, profile-блок, запись в «История»
# 4) «Ещё вариант» → новый плейлист без LLM; история обновилась
# 5) /?prompt=test → промпт подставлен
```

## Shell

- `AppHeader`: логотип, навигация (`/`), логин Яндекса (`login`), кнопка «Выйти».
- `AuthGate` на защищённых маршрутах → `/login` без сессии.
- `GuestGate` на `/login` → редирект на `/` при валидной сессии.
- Тёмная тема: CSS-переменные в `globals.css` (как docwise).

## Запреты UX

- Не хранить OAuth-токен Яндекса во фронтенде — только `session_id`.
- Не слать `session_id` в теле запросов, кроме как Bearer в заголовке.
- Не подменять поля API в TypeScript (имена как в [API.md](API.md)).
- При logout/login сбрасывать кэш React Query и playlist-store.

## Dev и Docker

| Команда | Назначение |
| --- | --- |
| `make deps-frontend` | Offline deps для Docker |
| `make up-frontend` | Поднять frontend на `:3001` |
| `make typecheck` | `tsc --noEmit` |
| `make test-frontend` | vitest (auth-gates + playlist form) |
| `make logs-frontend` | Логи контейнера |
