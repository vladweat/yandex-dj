# Telegram Mini App и бот

В проекте есть Telegram Mini App и небольшой бот для его запуска. Генерация использует тот же backend API, что и web-интерфейс.

## Компоненты

| Компонент | Реализация |
| --- | --- |
| Mini App | Frontend-маршруты /tg и /tg/login, Telegram Web Apps SDK |
| Бот | aiogram; команда /start и кнопка открытия Mini App |
| Backend | Маркировка канала генерации и привязка Telegram-пользователя к существующей сессии |
| Данные | client_channel в playlist_generations и необязательный telegram_user_id у пользователя |

## Настройка запуска

1. Задайте TG_BOT_TOKEN и TELEGRAM_WEB_APP_URL в backend/.env. Для Telegram Mini App требуется доступный по HTTPS адрес.
2. Настройте URL Mini App в меню бота через BotFather.
3. Укажите корректный NEXT_PUBLIC_API_URL при сборке frontend.
4. Запустите миграции и сервисы согласно [OPERATIONS.md](OPERATIONS.md).

Переменные перечислены в [CONFIGURATION.md](CONFIGURATION.md). Сборка и Compose-сервис бота описаны в [INFRASTRUCTURE.md](INFRASTRUCTURE.md).

## Локальная разработка

Маршрут /tg можно открыть в браузере при локально запущенном frontend. Без Telegram WebView запросы идут как обычный web-канал. Для локальной web-разработки бот можно не запускать.

## Связанные интерфейсы

- [API.md](API.md) — client channel и привязка Telegram-пользователя.
- [FRONTEND.md](FRONTEND.md) — маршруты и клиентская сессия.
