# Документация Prompt DJ

## С чего начать

1. [SPEC.md](SPEC.md) — ТЗ, пайплайн, критерии.
2. [PRODUCT.md](PRODUCT.md) — продуктовый разбор, ICP, metrics, бэклог P0–P3 (**следующий фокус**).
3. [STACK.md](STACK.md) — зафиксированный стек (backend + frontend).
4. [ARCHITECTURE.md](ARCHITECTURE.md) — модули, latency, структура кода.
5. [API.md](API.md) — REST-контракты FastAPI.
6. [FRONTEND.md](FRONTEND.md) — маршруты, Device Flow UX, экран генерации.
7. [REUSE_FROM_DOCWISE.md](REUSE_FROM_DOCWISE.md) — что копировать из соседнего `../docwise`.
8. [CONVENTIONS.md](CONVENTIONS.md) — слои backend/frontend, соглашения.
9. [DEVELOPMENT.md](DEVELOPMENT.md) — roadmap этапов 0–6 ✅ + чеклист этапа 7+ + техдолг.
10. [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md) — качество плейлистов, golden, handoff для агентов.
11. [INFRASTRUCTURE.md](INFRASTRUCTURE.md) — Docker, offline-сборка, ресурсы dev-машины.

Специализированные: [LLM_SCHEMA.md](LLM_SCHEMA.md), [YANDEX_MUSIC.md](YANDEX_MUSIC.md), [analytics/product_metrics.sql](analytics/product_metrics.sql).

## Правила Cursor

`.cursor/rules/` — `project.mdc` (всегда), `python.mdc`, `interfaces.mdc`, `frontend.mdc`. При противоречии сначала `docs/`, затем правила и код.

## Инварианты

- OAuth-токен Яндекса только в PostgreSQL (Fernet); клиенту — `session_id`.
- Endpoints тонкие; бизнес-логика в `services/`.
- `MusicProfile` — единая схема LLM ([LLM_SCHEMA.md](LLM_SCHEMA.md)).
- Целевой latency пайплайна: **7–12 сек** (hard stop `PIPELINE_TIMEOUT_SEC=90`).
- Релевантность — embedding/LLM, **не** regex под конкретный промпт/жанр.
- После MVP: сначала **metrics → канал → listening graph**, не multi-catalog ([PRODUCT.md](PRODUCT.md)).
