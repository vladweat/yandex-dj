# Документация Prompt DJ

## С чего начать

1. [SPEC.md](SPEC.md) — ТЗ, пайплайн, критерии.
2. [STACK.md](STACK.md) — зафиксированный стек (backend + frontend).
3. [ARCHITECTURE.md](ARCHITECTURE.md) — модули, latency, структура кода.
4. [API.md](API.md) — REST-контракты FastAPI.
5. [FRONTEND.md](FRONTEND.md) — маршруты, Device Flow UX, экран генерации.
6. [REUSE_FROM_DOCWISE.md](REUSE_FROM_DOCWISE.md) — что копировать из соседнего `../docwise`.
7. [CONVENTIONS.md](CONVENTIONS.md) — слои backend/frontend, соглашения.
8. [DEVELOPMENT.md](DEVELOPMENT.md) — roadmap с чекбоксами (MVP ✅ → 5.5 качество → 6 продукт → 7 backlog).
9. [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md) — качество плейлистов, P1/P2, handoff для агентов.
10. [INFRASTRUCTURE.md](INFRASTRUCTURE.md) — Docker, offline-сборка, ресурсы dev-машины.

Специализированные: [LLM_SCHEMA.md](LLM_SCHEMA.md), [YANDEX_MUSIC.md](YANDEX_MUSIC.md).

## Правила Cursor

`.cursor/rules/` — `project.mdc` (всегда), `python.mdc`, `interfaces.mdc`, `frontend.mdc`. При противоречии сначала `docs/`, затем правила и код.

## Инварианты

- OAuth-токен Яндекса только в PostgreSQL (Fernet); клиенту — `session_id`.
- Endpoints тонкие; бизнес-логика в `services/`.
- `MusicProfile` — единая схема LLM ([LLM_SCHEMA.md](LLM_SCHEMA.md)).
- Целевой latency пайплайна: **7–12 сек**.
