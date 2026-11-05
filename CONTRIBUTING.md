# Участие в разработке

## Подготовка окружения

Для backend unit-проверок нужны Python 3.12 и package index при первой
установке. Runner создаст отдельное тестовое окружение:

```bash
./scripts/test-backend.sh
```

Для запуска приложения, ML-модели и Compose см.
[README.md](README.md) и [docs/OPERATIONS.md](docs/OPERATIONS.md). Frontend
проверяется отдельно на Node.js 20:

```bash
cd frontend
npm ci
```

Не публикуйте `.env`, OAuth-токены и API keys.

## Архитектурные правила

- Сохраняйте направление зависимостей
  `endpoints → services → repositories → db/models`.
- Endpoints отвечают за HTTP mapping, а services не зависят от FastAPI.
- `MusicProfile` в `backend/app/schemas/llm.py` — единый контракт LLM.
- CPU-bound embedding запускается через executor; сетевой I/O остаётся async.
- Не добавляйте prompt-specific regex. Изменения retrieval/scoring должны
  сохранять golden-регрессии.

## Проверки перед review

```bash
./scripts/test-backend.sh

cd frontend
npm run typecheck
npm test
```

CI запускает те же проверки backend и frontend (без `[ml]`, live API и Docker
build). Backend runner создаёт временный Fernet key автоматически.
Live-проверки качества описаны в
[docs/PLAYLIST_QUALITY.md](docs/PLAYLIST_QUALITY.md).

## Миграции

Создавайте новую ревизию из `backend/` и проверяйте обе стороны:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Не редактируйте уже применённые миграции. В Compose используйте
`make migrate`.

## Документация

- Пишите по-русски, сохраняя English names для symbols, API и команд.
- Код, миграции и конфигурация являются источником истины для текущего поведения.
- При изменении API обновляйте `docs/API.md`; при изменении env —
  `docs/CONFIGURATION.md`; при изменении runtime — `docs/OPERATIONS.md`.
- Если меняется пользовательский сценарий или область продукта, синхронизируйте [docs/PRODUCT.md](docs/PRODUCT.md).
- Используйте ADR для архитектурных решений, которые важно объяснить будущим участникам проекта.
