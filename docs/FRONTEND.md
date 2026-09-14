# Frontend: UI/UX

Стек: Next.js 15 App Router, React 19, TypeScript 5, Tailwind CSS 4, shadcn/ui (Radix). Состояние: TanStack Query + Zustand.

Каркас копируется из соседнего репозитория **docwise** ([REUSE_FROM_DOCWISE.md](REUSE_FROM_DOCWISE.md)): `layout`, `components/ui`, `query-provider`, `toast-host`, `lib/api.ts`, auth-gates. Интерактив и сторы фичи — `src/features/{auth,playlist,health}`. Маршруты в `app/` — RSC (`metadata` + остров). Общий HTTP — `lib/api.ts`. Типы — `types/` (1:1 с Pydantic).

## Маршруты

| Путь | Экран |
| --- | --- |
| `/login` | OAuth Device Flow: код + ссылка на ya.ru/device, poll до `authenticated` |
| `/` | Генерация плейлиста: промпт, опции, результат (ссылка + треки) |
| `/health` | Статус API (опционально, для отладки) |

Временная HTML-страница `GET /test/auth` (FastAPI static) — только для отладки до появления `frontend/`; после скелета Next.js удалить.

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

1. **Форма:** текстовый промпт, `track_count` (по умолчанию 25), `instrumental_only`.
2. **Submit:** `POST /api/v1/playlists/generate` с Bearer.
3. **Состояния:** idle → loading (7–12 сек, спиннер + этап при появлении async API) → success | error.
4. **Результат:** `title`, `description`, кнопка «Открыть в Яндекс Музыке» (`playlist_url`), таблица треков (`title`, `artist`, `similarity_score`).

Ошибки — тост/баннер, без разрыва страницы:

| Код | UX |
| --- | --- |
| `401` | Редирект на `/login` |
| `422` | Валидация промпта под полем |
| `502` / `503` | Тост «Сервис временно недоступен» |

Пока `POST /playlists/generate` возвращает `501` — показывать заглушку «Скоро» или скрыть кнопку генерации.

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
| `make deps-frontend` | `node_modules` на хосте (offline build) |
| `make up-frontend` | пересборка только UI |
| `make typecheck` | `tsc --noEmit` в `frontend/` |
| `make test-frontend` | `vitest run` |

Переменные: `NEXT_PUBLIC_API_URL=http://localhost:8000` (порт API Prompt DJ). Frontend — `:3001` (как docwise, чтобы не конфликтовать с другими проектами).

Подробнее: [CONVENTIONS.md](CONVENTIONS.md), [INFRASTRUCTURE.md](INFRASTRUCTURE.md).
