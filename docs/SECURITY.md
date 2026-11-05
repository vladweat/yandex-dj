# Безопасность приложения

Документ описывает механизмы безопасности, реализованные в исходном коде. Защита production deployment также зависит от reverse proxy, TLS, секретов и сетевой конфигурации окружения.

## Границы доверия

~~~mermaid
flowchart LR
    B[Browser / Telegram WebView] -->|Bearer session_id| API[FastAPI]
    API -->|encrypted token at rest| DB[(PostgreSQL)]
    API -->|OAuth token in memory| YM[Yandex Music API]
    API -->|API key| LLM[OpenAI-compatible API]
    API --> R[(Redis)]
    BOT[aiogram bot] --> TG[Telegram Bot API]
~~~

Браузер не получает OAuth-токен Яндекса. После Device Flow backend шифрует токен Fernet-ключом, хранит зашифрованное значение в PostgreSQL и выдаёт клиенту случайный session_id.

## Аутентификация и сессии

Защищённые endpoints проверяют Bearer session_id, загружают пользователя и сессию и проверяют срок действия. OAuth-токен используется backend при запросах к Яндекс Музыке.

Telegram Web App initData проверяется по HMAC с помощью bot token; возраст auth_date ограничен 24 часами. Привязка Telegram ID относится к уже аутентифицированной сессии.

## Хранение секретов

- OAuth-токен Яндекса хранится в sessions.encrypted_token.
- Fernet-ключ, API keys и bot token передаются через environment.
- Реальные .env, API keys, OAuth-токены и bot tokens не должны попадать в Git или логи.
- Доступ одновременно к базе и TOKEN_ENCRYPTION_KEY позволяет расшифровать сохранённый OAuth-токен.

## Сессия браузера

Frontend хранит session_id в localStorage и добавляет его в Authorization header. Это исключает cookie-based CSRF, но делает токен доступным JavaScript в том же origin. Cookie с флагом httpOnly и Content Security Policy в приложении не настроены.

Logout очищает локальное состояние браузера; server-side отзыв сессии через отдельный endpoint не предусмотрен. Скопированный Bearer остаётся действительным до истечения срока сессии.

## Границы приложения и окружения

- CORS использует список origins из CORS_ORIGINS; методы и заголовки разрешены приложением.
- Endpoint /scoring/rank доступен без пользовательской сессии и может выполнять вычисления над переданными кандидатами.
- В приложении нет встроенного rate limiting, ограничения размера запроса и TLS termination.
- Compose-конфигурация предназначена для локальной разработки; TLS и reverse proxy относятся к deployment окружению.
- Схема ролей ограничивается владением пользовательскими объектами и отдельным секретом endpoint метрик.

## Данные пользователя

В PostgreSQL сохраняются Yandex UID/login, Telegram user ID при привязке, промпты, история треков и зашифрованный OAuth-токен. Проект не включает отдельный API удаления истории или сессии. В логах генерации используются технические показатели; секреты и OAuth-токены не должны логироваться.
