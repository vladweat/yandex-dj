# Frontend: UI/UX

Стек: Next.js 15 App Router, React 19, TypeScript 5, Tailwind CSS 4, shadcn/ui (Radix). Состояние: TanStack Query + Zustand.

Frontend использует layout, общие UI-компоненты, query-provider, toast-host,
lib/api.ts и auth-gates. Интерактив и состояние функций находятся в
src/features/{auth,playlist,health}. Маршруты в app/ используют RSC для metadata
и интерактивные компоненты; типы в types/ соответствуют API-контрактам.

## Маршруты

| Путь | Экран |
| --- | --- |
| `/login` | OAuth Device Flow: код + ссылка на ya.ru/device, poll до `authenticated` |
| `/` | **Пользовательский** UI: textarea-hero → результат → история; `?prompt=` prefill |
| `/lab` | **Полный** UI (опции, MusicProfile, pool_stats, scores) — для отладки |
| `/gallery` | Публичная галерея промптов (без логина) → `/?prompt=…` |
| `/tg` | **Telegram Mini App** — тот же simple UI, что `/`; `X-Client-Channel: telegram` |
| `/tg/login` | Device Flow для Mini App |
| `/health` | Статус API (опционально) |
| `/debug` | Статус аккаунта Яндекс Музыки; ссылка на `/lab` |

Форма/результат/история принимают `variant: "simple" | "full"`.

## Авторизация

Приложение использует **Bearer `session_id`** (UUID из Device Flow).

| Шаг | API |
| --- | --- |
| Старт | `POST /api/v1/auth/device-flow/start` |
| Poll | `POST /api/v1/auth/device-flow/poll` с `device_code` |
| Профиль | `GET /api/v1/auth/me` с `Authorization: Bearer <session_id>` |

Клиент хранит `session_id` в `localStorage` (ключ `prompt_dj_session_id`). В `lib/api.ts` — заголовок `Authorization`, без cookie refresh.

`auth-provider.tsx`: boot через `fetchMe()`; при 401 — сброс сессии. Logout — очистка `localStorage` + сброс TanStack Query / Zustand (`reset-client-state.ts`).

Server-side revoke отсутствует; XSS trade-off `localStorage` описан в
[SECURITY.md](SECURITY.md).

`NEXT_PUBLIC_API_URL` встраивается в browser bundle во время `next build`.
Runtime env уже собранного контейнера его не меняет; см.
[CONFIGURATION.md](CONFIGURATION.md).

## Главный экран `/` (пользователь)

Одна колонка генерации + история сбоку (чтобы форма и результат жили в одном окне):

1. **Hero:** бренд Prompt DJ + короткий tagline + textarea (после результата форма сжимается: `compact`).
2. **Форма (simple):** промпт, 3 чипа-ситуации (до первого результата), ссылка на `/gallery`, чекбокс `use_library`, soft-квота; дефолты: 25 треков, `diversity=normal`. «Отменить» + мягкий latency copy.
3. **Prefill:** `?prompt=…`; draft из истории («Снова»). AuthGate → `?next=` (cold share links).
4. **Submit:** `POST /api/v1/playlists/generate`; при `401` → `/login`; `504` / `429` / `warnings` — как раньше.
5. **Результат (simple):** primary — «Открыть в Яндекс Музыке» + like/dislike; AI-обложка (`has_cover` → blob fetch, **только здесь** — в Яндексе другая обложка); secondary — «Ещё вариант», share/copy; треки **свёрнуты** (раскрываются по клику); **без** MusicProfile / pool_stats.
6. **История:** справа rail на `lg+`; на мобиле — кнопка «История» → drawer. Не занимает вертикаль генерации.

## Lab `/lab` (полный функционал)

Тот же пайплайн с `variant="full"`:

1. Все опции: `track_count`, `diversity`, `instrumental_only`, `exclude_artists`, `use_library`.
2. Примеры — 7 golden-промптов.
3. Результат: copy/share, MusicProfile, badges `raw/clean/selected`, таблица со `similarity_score`.
4. История с pool_stats и «Повторить» (все options).
5. Ссылка на `/debug` (Yandex account).

Ситуации для быстрого старта представлены чипами в форме генерации.

Ошибки — тост/баннер, без разрыва страницы:

| Код | UX |
| --- | --- |
| `0` / сеть | Баннер + тост «API недоступен» |
| `401` | Сброс `session_id`, тост, редирект на `/login` |
| `422` | Валидация промпта под полем (1–2000 символов, `track_count` 1–50) |
| `429` | Баннер soft-квоты + тост; кнопка генерации disabled; «Ещё вариант» доступен |
| `499` (abort) | Тост «Генерация отменена» |
| `502` / `503` | Баннер/тост «API недоступен» |
| `504` | Тост: превышен `PIPELINE_TIMEOUT_SEC` |

Полный контракт: [API.md](API.md) § Playlists.  
Качество: [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md).

### Ручной тест UI

```bash
make up-frontend   # http://localhost:3001
# 1) /login → Device Flow
# 2) / → чип «Кухня» или свой промпт → «Собрать плейлист»
# 3) Ожидание: primary «Открыть в Яндекс Музыке» + like/dislike; без profile/scores
# 4) «Ещё вариант» → новый плейлист; история обновилась
# 5) /?prompt=test → промпт подставлен (гостевая ссылка переживает login)
# 6) /gallery → карточка → /?prompt=…
# 7) /lab → полный UI (опции, MusicProfile, pool_stats)
# 8) Проверьте сохранение оценки и обновление истории после генерации
```

## Shell

- `AppHeader`: логотип, навигация (Галерея всегда; Генерация + Lab после логина), «Войти» / «Выйти». Lab подсвечивается и на `/debug`.
- `AuthGate` на защищённых маршрутах → `/login?next=<path+query>` без сессии.
- `GuestGate` на `/login` → редирект на `next` при валидной сессии.
- Тема: Manrope + Unbounded через Google Fonts в runtime (offline Docker build без `next/font/google`); мягкий radial фон, glass-rail истории.

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
