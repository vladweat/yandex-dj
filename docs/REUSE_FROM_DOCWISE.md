# Переиспользование Docwise

Источник: соседний репозиторий `../docwise`. Это **карта порта**, не backlog: при появлении `frontend/` копировать выбранные части, а не весь репозиторий.

Docwise сам портировал каркас из ChainWise; для Prompt DJ берём **обвязку Next.js** из docwise и меняем auth + главный экран.

## Что копировать почти целиком

| Docwise | Prompt DJ | Примечание |
| --- | --- | --- |
| `frontend/package.json` (зависимости без pdfjs) | `frontend/package.json` | Убрать `pdfjs-dist`, `@react-pdf-viewer` если есть |
| `frontend/next.config.ts` | упрощённый | Без pdf worker / canvas alias |
| `frontend/Dockerfile` | тот же паттерн | `NEXT_PUBLIC_API_URL`, offline `node_modules` |
| `frontend/postcss.config.mjs`, `components.json` | как есть | Tailwind 4 + shadcn |
| `frontend/src/app/globals.css` | палитра | Акцент можно сменить на жёлтый (Яндекс) |
| `frontend/src/app/layout.tsx` | shell | QueryProvider, AuthProvider, AppHeader, ToastHost |
| `frontend/src/components/query-provider.tsx` | как есть | |
| `frontend/src/components/toast-host.tsx` | как есть | |
| `frontend/src/stores/toast-store.ts` | как есть | |
| `frontend/src/components/ui/*` | shadcn-примитивы | button, input, card, alert, skeleton, tabs… |
| `frontend/src/lib/utils.ts` | `cn()` | |
| `frontend/src/lib/reset-client-state.ts` | адаптировать | Сброс playlist-store вместо chat-store |
| `frontend/scripts/prepare-deps.sh` | `make deps-frontend` | |
| `Makefile` цели | `deps-frontend`, `up-frontend`, `typecheck`, `test-frontend` | |
| `docker-compose.yml` сервис `frontend` | порт `3001:3000` | `NEXT_PUBLIC_API_URL=http://localhost:8000` |

## Что адаптировать

| Docwise | Prompt DJ |
| --- | --- |
| `lib/api.ts` — cookie + refresh | Bearer `session_id` из `localStorage`; без `credentials: "include"` refresh |
| `features/auth/auth-provider.tsx` — login/register/Google | Device Flow: `start` → poll loop → сохранить `session_id` |
| `features/auth/auth-panel.tsx` | Код `user_code`, ссылка `verification_url`, статус poll |
| `features/auth/auth-gate.tsx`, `guest-gate.tsx` | Та же логика редиректов |
| `components/app-header.tsx` | Навигация: «Генерация»; профиль: `login` из `/auth/me` |
| `types/auth.ts` | `AuthMeResponse`: `session_id`, `login`, `yandex_uid`, `expires_at` |

## Что не копировать

| Docwise | Причина |
| --- | --- |
| `features/chat/*` | Нет чата и PDF viewer |
| `features/documents/*` | Нет knowledge base |
| `features/settings/*`, `inspect/*` | Нет org/SSO/billing |
| `lib/sse.ts`, stream chat | Генерация плейлиста — один POST (позже optional polling) |
| Cookie auth, Google, SSO endpoints | Device Flow + Bearer session |
| Backend docwise | Свой async FastAPI уже в `backend/` |

## Новое в Prompt DJ (нет в docwise)

| Модуль | Назначение |
| --- | --- |
| `features/playlist/playlist-form.tsx` | Промпт + опции |
| `features/playlist/playlist-result.tsx` | Треки + ссылка |
| `types/playlist.ts` | Контракт `POST /playlists/generate` |
| `lib/api.ts` → `generatePlaylist()` | |

## Порядок порта (рекомендуемый)

1. Скелет `frontend/`: package.json, tsconfig, tailwind, Dockerfile, `components/ui`.
2. `lib/api.ts` + `types/auth.ts` под Device Flow и `/auth/me`.
3. `features/auth/*` + `/login`.
4. `AppHeader`, gates, `/` с заглушкой генерации.
5. `docker-compose` + Makefile; удалить `backend/app/static/auth-test.html` и `GET /test/auth`.
6. После `POST /playlists/generate` ≠ 501 — `features/playlist/*`.

## Ссылки

- Docwise: `docs/frontend.md`, `docs/conventions.md`, `.cursor/rules/frontend.mdc`
- Prompt DJ: [FRONTEND.md](FRONTEND.md), [API.md](API.md)
