# Тестирование

## Backend

Unit suite находится в `backend/tests/` и использует pytest +
pytest-asyncio. Тесты покрывают HTTP contracts, auth, pipeline orchestration,
retrieval/scoring/quality, export, metrics, Telegram validation и cost tracking.

```bash
cd backend
export TOKEN_ENCRYPTION_KEY="$(python -c \
  'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
ruff check app tests
python -m pytest tests/ -q
```

Для полного локального scoring runtime установите `.[ml,dev]`; CI устанавливает
только `.[dev]`, поэтому не загружает реальную sentence-transformers model.

Golden regression:

```bash
python -m pytest tests/test_golden_prompts.py -q
```

Golden tests проверяют детерминированные fixtures/алгоритмические инварианты, а
не качество live OpenAI/Яндекс ответов. Ручной quality checklist:
[PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md).

## Frontend

```bash
cd frontend
npm ci
npm run typecheck
npm test
```

Vitest работает с jsdom. В репозитории нет Playwright/Cypress E2E и
интеграционных тестов browser ↔ live API.

`npm run lint` объявлен как `next lint`, но Next.js 15.5 может требовать
отдельной настройки ESLint CLI; lint не входит в текущий CI. Не считайте его
подтверждённым gate без успешного запуска.

## CI

`.github/workflows/ci.yml` запускается на push и pull request:

- Python 3.12: `pip install -e ".[dev]"`, ruff, pytest;
- Node 20: `npm ci`, TypeScript, Vitest.

CI намеренно не проверяет:

- live Yandex Music, OpenAI-compatible API и Telegram;
- реальную embedding-модель;
- Docker/Compose build и Alembic against a real PostgreSQL service;
- frontend E2E;
- backup/restore и deployment.

Для этих границ нужны отдельные smoke/E2E environments и test accounts. Не
добавляйте production credentials в GitHub Actions fixtures.

## Проверка документации

Специализированного Markdown/link checker и Mermaid CLI в зависимостях проекта
нет. Поэтому локальные links следует проверять статическим скриптом/редактором,
а диаграммы — review или renderer документации. Наличие файла по relative link
не подтверждает корректность anchors.
