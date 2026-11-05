# Документация Prompt DJ

Документы описывают пользовательские сценарии и устройство проекта. Исходный код, миграции и конфигурация являются источником истины для текущего поведения.

## Для первого знакомства

1. [README](../README.md) — назначение проекта, демонстрационные макеты и локальный запуск.
2. [PRODUCT.md](PRODUCT.md) — пользовательский сценарий и реализованные возможности.
3. [ARCHITECTURE.md](ARCHITECTURE.md) — компоненты и поток генерации.
4. [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md) — подход к релевантности, разнообразию и проверкам качества.

## Разработка и эксплуатация

- [OPERATIONS.md](OPERATIONS.md) — запуск сервисов и миграции.
- [CONFIGURATION.md](CONFIGURATION.md) — переменные окружения.
- [TESTING.md](TESTING.md) — локальные и CI-проверки.
- [CONTRIBUTING.md](../CONTRIBUTING.md) — правила изменений и подготовки pull request.
- [AGENTS.md](../AGENTS.md) — технические границы модулей для coding agents.

## Справочник

- [API.md](API.md) — REST-контракты.
- [DATABASE.md](DATABASE.md) — модели данных и миграции.
- [LLM_SCHEMA.md](LLM_SCHEMA.md) — профиль музыки, используемый генератором.
- [FRONTEND.md](FRONTEND.md) — маршруты, сессия и структура web-интерфейса.
- [TELEGRAM.md](TELEGRAM.md) — компоненты Telegram Mini App и бота.
- [SECURITY.md](SECURITY.md) — сессии, credentials и границы приложения.
- [YANDEX_MUSIC.md](YANDEX_MUSIC.md) — взаимодействие с каталогом и экспорт плейлиста.
- [STACK.md](STACK.md) — технологии и версии.
- [CONVENTIONS.md](CONVENTIONS.md) — соглашения по структуре кода.
- [INFRASTRUCTURE.md](INFRASTRUCTURE.md) — локальная Compose-топология и подготовка зависимостей.
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — внешние визуальные ресурсы.
- [analytics/product_metrics.sql](analytics/product_metrics.sql) — примеры запросов к метрикам генераций.
