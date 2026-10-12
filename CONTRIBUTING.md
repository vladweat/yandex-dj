# Участие в разработке

## Подготовка окружения

Backend рассчитан на Python 3.12 в CI и Docker, frontend — на Node.js 20.
Подробный запуск: [README.md](README.md) и
[docs/OPERATIONS.md](docs/OPERATIONS.md).

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[ml,dev]"
cp .env.example .env

cd ../frontend
npm ci
```

Для `TOKEN_ENCRYPTION_KEY` используйте локально сгенерированный Fernet-ключ:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
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
cd backend
ruff check app tests
python -m pytest tests/ -q

cd ../frontend
npm run typecheck
npm test
```

CI запускает именно эти unit-проверки (без `[ml]`, live API и Docker build).
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
- Код и конфигурация имеют приоритет над roadmap.
- При изменении API обновляйте `docs/API.md`; при изменении env —
  `docs/CONFIGURATION.md`; при изменении runtime — `docs/OPERATIONS.md`.
- Не дублируйте продуктовый backlog: его канон — `docs/PRODUCT.md`.
- Новые ADR создавайте только для реально принятого и подтверждённого решения.
