# Аудит документации

Дата статической сверки: 2026-10-12. Источники: application code, migrations,
tests, Compose, Makefile, CI и существующие Markdown-файлы.

## Решение по структуре

Существующий `docs/` уже является каноническим каталогом. Параллельный
`new_docs/` не создан: это дублировало бы API, architecture, product и quality
документы. Новые темы добавлены в текущую навигацию.

## Статус документов

| Документ | Решение | Результат аудита |
|---|---|---|
| `README.md` | обновлён | Quick start, проверки, ограничения и навигация приведены к Makefile/Compose |
| `backend/README.md` | обновлён | Уточнены scope `make up`, test env, CLI и ссылки |
| `docs/README.md` | обновлён | Стал единым индексом по аудиториям |
| `docs/ARCHITECTURE.md` | обновлён | Исправлены module paths, Redis status, lifecycle/data flow |
| `docs/API.md` | обновлён | Удалены несуществующие async routes, исправлены health/poll/export |
| `docs/DEVELOPMENT.md` | сохранён, точечно исправлен | Это historical roadmap; не используется как operations guide |
| `docs/INFRASTRUCTURE.md` | сохранён как historical snapshot | Значения конкретной VM не являются current requirements; заменён ссылкой на operations |
| `docs/PRODUCT.md` | сохранён | Канон продуктового backlog |
| `docs/PLAYLIST_QUALITY.md` | сохранён | Канон golden/live quality |
| `docs/FRONTEND.md` | сохранён | В целом соответствует routes и client-only auth |
| `docs/STACK.md` | сохранён | Канон stack; версии package lock/CI имеют приоритет |
| `docs/LLM_SCHEMA.md` | сохранён | Проверять вместе с `schemas/llm.py` |
| `docs/YANDEX_MUSIC.md` | сохранён | Внешняя интеграция; live behavior статически не подтверждён |
| `docs/TELEGRAM.md` | сохранён | Явно фиксирует незавершённый E2E |
| `docs/UNIT_ECONOMICS.md` | сохранён | Продуктовые формулы, не runtime contract |
| `docs/REUSE_FROM_DOCWISE.md` | сохранён как provenance | Ссылается на внешний соседний repo и не является setup requirement |

Добавлены `CONFIGURATION.md`, `DATABASE.md`, `OPERATIONS.md`, `SECURITY.md`,
`TESTING.md`, `TECHNICAL_DEBT.md`, а также root `AGENTS.md` и
`CONTRIBUTING.md`.

## Исправленные расхождения

- `/health` фактически не возвращает status dependencies.
- HTTP Device Flow poll не возвращает собственный `408`: клиент выполняет
  повторные poll requests.
- Async generate/task endpoints не существуют.
- Export использует один playlist change diff, а не N вставок.
- Redis давно реализован и не является будущим «этапом 3».
- Главная страница UI использует simple variant; full diagnostics — `/lab`.
- `make build` не собирает frontend, а offline archive его не включает.
- `NEXT_PUBLIC_API_URL` является build-time browser setting.

## Полнота

Полностью описаны на уровне статической реализации:

- module boundaries и request flow;
- API route surface и auth modes;
- data model, migrations и текущие transaction boundaries;
- environment variables;
- local Compose topology, startup и troubleshooting;
- unit test/CI scope;
- security trust boundaries и подтверждённые ограничения.

Частично описаны, потому что repository evidence недостаточно:

- production deployment и rollback;
- backup/restore;
- live SLO/monitoring;
- external API failure contracts;
- Telegram E2E;
- data retention и incident response.

Для этих тем документированы пробелы, а не вымышленные процедуры.

## Выполненная валидация

| Проверка | Результат |
|---|---|
| Relative Markdown links | 27 файлов, broken paths не найдены |
| Ключевые referenced paths | существуют |
| `Settings` ↔ `CONFIGURATION.md` | 58 из 58 полей перечислены |
| FastAPI OpenAPI | 17 реализованных paths; phantom async routes отсутствуют |
| Backend tests | 209 passed с `TOKEN_ENCRYPTION_KEY`, как в [TESTING.md](TESTING.md) |
| Frontend TypeScript + Vitest | passed; 3 files, 26 tests |
| Secret-pattern scan Markdown | совпадений не найдено |
| `ruff check app tests` | failed: 6 существующих ошибок (2× E501, 4× I001) |
| Markdown/Mermaid syntax tooling | пропущено: validators не входят в зависимости проекта |

Backend lint не исправлялся, потому что аудит документации не разрешает
functional/source cleanup. Ошибки находятся в
`backend/app/api/v1/endpoints/playlists.py`, `backend/app/bot/main.py`,
`backend/app/services/auth_service.py`, `backend/tests/conftest.py`,
`backend/tests/test_cover_art.py` и `backend/tests/test_telegram_webapp.py`.

## Maintenance

При каждом изменении:

- route/schema → `API.md` и frontend types/client;
- `Settings` → `.env.example` и `CONFIGURATION.md`;
- model/migration → `DATABASE.md`;
- Compose/Docker/Makefile → README и `OPERATIONS.md`;
- security boundary → `SECURITY.md`;
- новый подтверждённый риск → `TECHNICAL_DEBT.md`.

ADR в репозитории не добавлены: историческая мотивация текущих решений не
подтверждена. Observable trade-offs описаны в architecture/security/debt.
