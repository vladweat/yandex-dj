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
