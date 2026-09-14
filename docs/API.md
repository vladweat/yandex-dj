# REST API (FastAPI)

Базовый URL: `/api/v1`

Авторизация сессии: `Authorization: Bearer <session_id>`

## Auth: Device Flow

### `POST /api/v1/auth/device-flow/start`

Инициирует OAuth Device Flow.

**Ответ `200`:**
```json
{
  "device_code": "XXXX-XXXX",
  "user_code": "ABCD-EFGH",
  "verification_url": "https://passport.yandex.ru/auth/device",
  "expires_in": 300,
  "interval": 5
}
```

### `POST /api/v1/auth/device-flow/poll`

**Запрос:**
```json
{
  "device_code": "XXXX-XXXX"
}
```

**Ответ `200` (ожидание):**
```json
{
  "status": "pending"
}
```

**Ответ `200` (успех):**
```json
{
  "status": "authenticated",
  "session_id": "uuid4-token"
}
```

**Ошибки:**
- `408` — таймаут (120 сек)
- `400` — невалидный или истёкший `device_code`
- `502` — Яндекс API недоступен

> Для отладки на стенде с разрывом сети (хост с прокси → контейнер с PostgreSQL) используйте CLI: `prompt-dj auth start` / `poll` и `make auth-poll`. См. [DEVELOPMENT.md](DEVELOPMENT.md).

### `GET /api/v1/auth/me`

Профиль текущей сессии.

**Headers:** `Authorization: Bearer <session_id>`

**Ответ `200`:**
```json
{
  "session_id": "uuid4",
  "login": "username",
  "yandex_uid": 411193386,
  "expires_at": "2026-10-14T12:23:41.148639Z"
}
```

**Ошибки:**
- `401` — невалидная или истёкшая сессия

Используется Next.js UI при boot (`auth-provider`) и после Device Flow. См. [FRONTEND.md](FRONTEND.md).

---

## LLM (Prompt Understanding)

### `POST /api/v1/llm/parse`

Разбор текстового промпта в `MusicProfile` (OpenAI SDK + instructor; провайдер — [KodikRouter](https://kodikrouter.ru/docs/base) или OpenAI).

**Headers:** `Authorization: Bearer <session_id>`

**Запрос:**
```json
{
  "prompt": "спокойная музыка для кодинга поздней ночью, эмбиент без слов",
  "track_count": 25,
  "instrumental_only": false
}
```

| Поле | Тип | Обязательно | По умолчанию |
|------|-----|-------------|--------------|
| `prompt` | string | да | — |
| `track_count` | int | нет | из LLM (обычно 25) |
| `instrumental_only` | bool | нет | false |

**Ответ `200`:**
```json
{
  "profile": {
    "playlist_title": "Ночной фокус",
    "playlist_description": "Спокойный эмбиент и лоу-фай для глубокой концентрации",
    "primary_genres": ["ambient", "lo-fi"],
    "mood_tags": ["calm", "focused"],
    "vocal_type": "instrumental_only",
    "reference_artists": ["Tycho", "Nujabes", "Bonobo", "Helios"],
    "search_queries": ["lo-fi beats study", "ambient coding night", "instrumental chill focus"],
    "target_track_count": 25
  }
}
```

**Ошибки:**
- `401` — невалидная или истёкшая сессия
- `422` — пустой или слишком длинный промпт
- `503` — LLM недоступен или `OPENAI_API_KEY` не задан

CLI: `prompt-dj llm parse "…"`. Конфиг: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` (см. `.env.example`).

---

## Playlists

### `POST /api/v1/playlists/generate`

Генерация и экспорт плейлиста.

**Headers:** `Authorization: Bearer <session_id>`

**Запрос:**
```json
{
  "prompt": "Саундтрек для ночной поездки по пустому шоссе в стиле нео-нуар и синтвейв",
  "track_count": 25,
  "instrumental_only": false
}
```

| Поле | Тип | Обязательно | По умолчанию |
|------|-----|-------------|--------------|
| `prompt` | string | да | — |
| `track_count` | int | нет | 25 |
| `instrumental_only` | bool | нет | false |

**Ответ `200`:**
```json
{
  "title": "Ночной Неон: Пустое Шоссе",
  "description": "Атмосферный синтвейв и ретровейв для ночной дороги",
  "playlist_url": "https://music.yandex.ru/users/username/playlists/1003",
  "tracks": [
    {
      "id": "40133452",
      "title": "Nightcall",
      "artist": "Kavinsky",
      "duration_ms": 259000,
      "similarity_score": 0.89
    }
  ]
}
```

**Ошибки:**
- `401` — невалидная или истёкшая сессия
- `422` — пустой или слишком длинный промпт
- `502` — ошибка API Яндекс Музыки после retry
- `503` — LLM или embedding model недоступны

---

## Health

### `GET /api/v1/health`

```json
{
  "status": "ok",
  "version": "0.1.0",
  "dependencies": {
    "database": "ok",
    "redis": "ok",
    "llm": "ok",
    "embeddings": "ok"
  }
}
```

---

## Асинхронная генерация (опционально, Этап 5+)

### `POST /api/v1/playlists/generate/async`

Возвращает `task_id` для длительных запросов (>12 сек).

### `GET /api/v1/playlists/tasks/{task_id}`

```json
{
  "status": "processing",
  "progress": "scoring",
  "result": null
}
```

Статусы: `pending` → `parsing` → `retrieving` → `scoring` → `exporting` → `completed` | `failed`.
