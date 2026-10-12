# Документация Prompt DJ

## Маршруты чтения

Новый инженер:

1. [корневой README](../README.md) — назначение и запуск;
2. [ARCHITECTURE.md](ARCHITECTURE.md) — компоненты и data flow;
3. [CONFIGURATION.md](CONFIGURATION.md) — environment;
4. [TESTING.md](TESTING.md) — проверки и границы CI.

Backend/API:

- [API.md](API.md) — реализованные REST-контракты;
- [DATABASE.md](DATABASE.md) — schema, migrations, transactions;
- [LLM_SCHEMA.md](LLM_SCHEMA.md) — `MusicProfile`;
- [YANDEX_MUSIC.md](YANDEX_MUSIC.md) — SDK boundary.

Эксплуатация и безопасность:

- [OPERATIONS.md](OPERATIONS.md) — Compose, startup, health, troubleshooting;
- [SECURITY.md](SECURITY.md) — auth, secrets и trust boundaries;
- [TECHNICAL_DEBT.md](TECHNICAL_DEBT.md) — приоритетные риски;
- [DOCUMENTATION_AUDIT.md](DOCUMENTATION_AUDIT.md) — coverage и unresolved gaps.

Frontend и продукт:

- [FRONTEND.md](FRONTEND.md) — маршруты и Device Flow UX;
- [TELEGRAM.md](TELEGRAM.md) — Mini App/bot и текущий E2E status;
- [PRODUCT.md](PRODUCT.md) — единственный канон продуктового backlog;
- [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md) — golden и live quality;
- [UNIT_ECONOMICS.md](UNIT_ECONOMICS.md) — COGS и продуктовые формулы.

Справочные и исторические:

- [SPEC.md](SPEC.md) — исходное ТЗ;
- [STACK.md](STACK.md) — принятый стек;
- [CONVENTIONS.md](CONVENTIONS.md) — code conventions;
- [DEVELOPMENT.md](DEVELOPMENT.md) — история этапов и roadmap;
- [INFRASTRUCTURE.md](INFRASTRUCTURE.md) — historical snapshot dev-машины;
- [REUSE_FROM_DOCWISE.md](REUSE_FROM_DOCWISE.md) — provenance порта из внешнего
  соседнего репозитория;
- [analytics/product_metrics.sql](analytics/product_metrics.sql) — SQL-метрики.

Правила contribution: [../CONTRIBUTING.md](../CONTRIBUTING.md). Инструкции
coding agents: [../AGENTS.md](../AGENTS.md).

## Правила Cursor

`.cursor/rules/` — `project.mdc` (всегда), `python.mdc`, `interfaces.mdc`,
`frontend.mdc`. При расхождении код, migrations и executable configuration
имеют приоритет над документацией; расхождение нужно исправить в том же change.

## Инварианты

- OAuth-токен Яндекса только в PostgreSQL (Fernet); клиенту — `session_id`.
- Endpoints тонкие; бизнес-логика в `services/`.
- `MusicProfile` — единая схема LLM ([LLM_SCHEMA.md](LLM_SCHEMA.md)).
- Целевой latency пайплайна: **7–12 сек** (hard stop `PIPELINE_TIMEOUT_SEC=90`).
- Релевантность — embedding/LLM, **не** regex под конкретный промпт/жанр.
- После MVP: сначала **metrics → канал → listening graph**, не multi-catalog ([PRODUCT.md](PRODUCT.md)).
