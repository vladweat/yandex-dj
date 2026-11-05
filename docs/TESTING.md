# Проверки и тестирование

## Backend

Unit suite находится в backend/tests и использует pytest и pytest-asyncio. Тесты покрывают HTTP-контракты, auth, генерацию плейлистов, retrieval, scoring, фильтры качества, export, метрики и Telegram initData validation.

Запуск из корня репозитория:

~~~
./scripts/test-backend.sh
~~~

Скрипт создаёт отдельное тестовое окружение, устанавливает dev-зависимости, задаёт временный Fernet key и запускает Ruff с pytest. Для первой установки нужны Python 3.12 и доступ к package index. Docker, PostgreSQL, Redis и credentials внешних API не требуются. Команда make test запускает тот же сценарий.

Для полного локального scoring runtime установите extra ml вместе с dev-зависимостями. CI использует только dev extra и не загружает sentence-transformers model.

Golden regression:

~~~
cd backend
python -m pytest tests/test_golden_prompts.py -q
~~~

Golden tests используют фиксированные fixtures и проверяют алгоритмические инварианты; они не оценивают ответы live LLM или каталога Яндекса.

## Frontend

~~~
cd frontend
npm ci
npm run typecheck
npm test
~~~

Vitest работает с jsdom. UI-тесты проверяют компоненты в тестовой среде и не запускают браузер против live API.

## CI

GitHub Actions запускает backend проверки на Python 3.12 и frontend проверки на Node.js 20:

- Backend: установка dev extra, Ruff и pytest.
- Frontend: npm ci, TypeScript typecheck и Vitest.

CI не обращается к live Yandex Music, LLM или Telegram API, не загружает реальную embedding-модель, не собирает Docker/Compose образы и не проверяет Alembic против отдельного PostgreSQL сервиса. Эти интеграции и deployment-процедуры требуют соответствующего окружения и тестовых credentials.

Python-зависимости заданы в pyproject.toml без lockfile; frontend использует package-lock.json.
