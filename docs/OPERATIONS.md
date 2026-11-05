# Эксплуатация

Документ описывает локальную Compose-топологию, startup-команды и обслуживание сервисов.

## Runtime topology

| Service | Образ / entrypoint | Host port | Persistent data |
|---|---|---:|---|
| `api` | `uvicorn app.main:app --reload` | 8000 | bind mount covers и `.auth` |
| `db` | `postgres:15` | 5432 | volume `prompt_dj_pgdata` |
| `redis` | `redis:7` | 6379 | нет volume |
| `bot` | `python -m app.bot.main` | — | нет |
| `frontend` | Next.js production server | 3001 | нет |

API ждёт healthy PostgreSQL и запущенный Redis. Bot ждёт только PostgreSQL.
Frontend зависит от API на уровне порядка старта, но readiness не проверяет.

## Профили запуска

Backend unit-проверки не требуют Compose или подготовленных ML-артефактов:

```bash
./scripts/test-backend.sh
```

Для запуска API на хосте используйте PostgreSQL и Redis из Compose. Образцы
адресов в `backend/.env.example` рассчитаны на этот вариант:

```bash
cp backend/.env.example backend/.env
./scripts/build-venv.sh
docker compose up -d db redis
cd backend
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --reload
```

`TOKEN_ENCRYPTION_KEY` нужен для auth, а `OPENAI_API_KEY` — для live-генерации
и обложек. Заполняйте их только для соответствующего сценария.

## Полный Compose-профиль

Dockerfile backend и frontend не устанавливают зависимости из сети. Они
копируют подготовленные `.venv`, embedding-модель и `node_modules`. Скрипт
подготовки backend рассчитан на Python 3.12 и Linux x86_64 и использует
системную библиотеку `libgomp.so.1`.

```bash
cp backend/.env.example backend/.env
make install
make deps-frontend
make build
make up-frontend
make up
make migrate
```

`make build` собирает только `api` и `bot`; `make up-frontend` отдельно собирает
frontend. `make up` сам не создаёт отсутствующие offline artifacts и запускает
все services, включая bot.

Чтобы запустить Compose без Telegram bot, после сборки поднимайте выбранные
сервисы явно: `docker compose up -d db redis api frontend`. Compose заменяет
host `localhost` из `.env` на service hostname `db`.

Startup API:

1. `apply_internal_no_proxy()` дополняет proxy bypass;
2. импортируется router;
3. lifespan прогревает embedding model через executor;
4. после startup принимаются запросы;
5. на shutdown закрывается SQLAlchemy engine.

Redis client не имеет явного shutdown hook. Миграции при startup не
выполняются.

## Health и readiness

```bash
curl -fsS http://localhost:8000/api/v1/health
docker compose ps
docker compose exec -T db pg_isready -U prompt_dj -d prompt_dj
docker compose exec -T redis redis-cli ping
```

`/api/v1/health` возвращает только `status` и версию процесса. Ответ `200` не
доказывает доступность PostgreSQL, Redis, LLM, embeddings или Яндекс API.
Compose healthcheck определён только для PostgreSQL.

## Миграции

```bash
make migrate
docker compose exec -T api python -m alembic current
docker compose exec -T api python -m alembic heads
```

Перед rollout новой версии миграции должны быть совместимы с выбранным порядком
deployment. Автоматизированный rollback в репозитории отсутствует. Downgrade
может удалять данные, поэтому не запускайте его без backup и проверки конкретной
ревизии.

## Логи и метрики

```bash
make logs
make logs-frontend
docker compose logs -f bot redis
```

Backend использует стандартный Python logging. `PlaylistService` пишет
stage latency, pool sizes, scoring method, warnings count и usage. JSON logging,
request/correlation ID, tracing, error tracker и Prometheus exporter не
реализованы.

Продуктовые агрегаты доступны через
`GET /api/v1/metrics/product?days=7` с `X-Metrics-Token`; это не infrastructure
monitoring. SQL-эквивалент — `docs/analytics/product_metrics.sql`.

## Offline bundle

```bash
make install
make pack
```

`scripts/pack-offline-bundle.sh` включает backend venv/model/code, migrations,
Compose и backend scripts. Он **не включает** frontend, `node_modules`, `.env`,
данные PostgreSQL, covers или Docker base images. Поэтому текущий archive нельзя
считать полным offline-дистрибутивом всего продукта.

Base images должны быть перенесены отдельно через доверенный image distribution
process. Команды `docker save/load` допустимы локально, но политика подписи и
проверки image в репозитории не задана.

## Backup и recovery

Автоматизация отсутствует. Состояние распределено между:

- PostgreSQL volume — users, sessions, generations;
- `backend/data/covers` — AI covers;
- Redis — восстанавливаемый cache;
- `.auth/pending.json` — временный CLI Device Flow artifact.

Production runbook должен определить RPO/RTO, backup encryption, retention и
регулярный restore test. Текущий volume сам по себе не является backup.

## Troubleshooting

### API не стартует

1. Проверить `docker compose logs api`.
2. Проверить наличие `backend/.venv`, `.models`, `.libs` после `make install`.
3. Проверить PostgreSQL `pg_isready`.
4. Если ошибка на embedding warmup — проверить модель в `.models` и совместимость
   `sentence-transformers`; unit install `.[dev]` не включает `[ml]`.

### Auth или playlist tests падают на Fernet

В `backend/.env`/environment нужен валидный `TOKEN_ENCRYPTION_KEY`, созданный
`Fernet.generate_key()`. Пустая строка не является допустимым dev default.

### UI не достигает API

1. Проверить browser Network и `NEXT_PUBLIC_API_URL`.
2. Помнить, что URL baked at build time: пересобрать frontend.
3. Добавить точный UI origin в `CORS_ORIGINS`.
4. Для browser URL использовать доступный host (например, localhost), а не
   внутреннее Compose-имя `api`.

### Генерация возвращает `504`

Посмотреть pipeline stage latency в API log. `PIPELINE_TIMEOUT_SEC` ограничивает
весь synchronous request. Увеличение timeout скрывает, но не устраняет медленный
LLM/Яндекс/scoring. Очередь задач не реализована.

### Redis недоступен

Track cache обрабатывает часть ошибок как cache miss и пишет warning, но
readiness этого не показывает. Проверить `redis-cli ping` и `REDIS_URL`.

### Cover отсутствует

Cover — best effort. Проверить `PLAYLIST_COVER_ENABLED`, image model/key,
`PLAYLIST_COVER_TIMEOUT_SEC`, write permissions `COVER_STORAGE_DIR` и warning в
pipeline log. Отсутствие cover не отменяет генерацию плейлиста.

### Bot завершается

Проверить `TG_BOT_TOKEN`, egress к `api.telegram.org`, proxy variables и
`TELEGRAM_BOT_USE_PROXY`. Требования к запуску Mini App и бота описаны в [TELEGRAM.md](TELEGRAM.md).
