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

## Retrieval (Candidate Pool)

### `POST /api/v1/retrieval/candidates`

Сбор пула кандидатов из каталога Яндекс Музыки по `MusicProfile`.

**Headers:** `Authorization: Bearer <session_id>`

**Запрос:**
```json
{
  "profile": { "...": "MusicProfile" },
  "reference_track_id": "9442712"
}
```

| Поле | Тип | Обязательно | По умолчанию |
|------|-----|-------------|--------------|
| `profile` | MusicProfile | да | — |
| `reference_track_id` | string | нет | null |

**Ответ `200`:**
```json
{
  "count": 287,
  "elapsed_ms": 3214,
  "tracks": [
    {
      "id": "9442712",
      "title": "Nightcall",
      "artists": ["Kavinsky"],
      "album": "OutRun",
      "genre": "synthwave",
      "version": "",
      "duration_ms": 259000,
      "available": true
    }
  ]
}
```

**Ошибки:**
- `401` — невалидная или истёкшая сессия
- `503` — Яндекс API недоступен

CLI: `prompt-dj retrieval fetch --prompt "…" --token "$YANDEX_OAUTH_TOKEN"`.

---

## Scoring (Ranking)

### `POST /api/v1/scoring/rank`

Ранжирование кандидатов: embeddings + diversity + fallback. Авторизация не требуется (кандидаты уже в теле запроса).

**Запрос:**
```json
{
  "profile": { "...": "MusicProfile" },
  "candidates": [ { "id": "9442712", "title": "Nightcall", "artists": ["Kavinsky"] } ],
  "prompt": "dark synthwave for night coding"
}
```

| Поле | Тип | Обязательно | По умолчанию |
|------|-----|-------------|--------------|
| `profile` | MusicProfile | да | — |
| `candidates` | TrackCandidate[] | да | min 1 |
| `prompt` | string | нет | null — дополняет embedding query |

**Ответ `200`:**
```json
{
  "count": 25,
  "elapsed_ms": 1842,
  "method": "embedding",
  "tracks": [
    {
      "id": "9442712",
      "title": "Nightcall",
      "artists": ["Kavinsky"],
      "album": "OutRun",
      "genre": "synthwave",
      "duration_ms": 259000,
      "score": 0.924
    }
  ]
}
```

`method`: `"embedding"` | `"fallback"` (жанры + порядок retrieval, если модель недоступна).

**Ошибки:**
- `422` — пустой список кандидатов
- `500` — внутренняя ошибка скоринга

При недоступности модели сервис возвращает `200` с `"method": "fallback"` (жанры + reference artists).

CLI: `prompt-dj scoring rank --prompt "…" --token "$YANDEX_OAUTH_TOKEN"` (полный пайплайн LLM → retrieval → scoring).

---

## Playlists

### `POST /api/v1/playlists/generate`

Единственная точка входа end-to-end пайплайна: промпт → плейлист в аккаунте Яндекс Музыки → запись в историю.

**Пайплайн (синхронный, один HTTP-запрос):**

```
prompt → LLM (MusicProfile) | reuse profile (source_id)
      → retrieval → scoring → export (Яндекс) → persist (playlist_generations)
```

| Этап | Сервис | OAuth Яндекса | Типичное время |
|------|--------|---------------|----------------|
| LLM | `LLMService.parse_prompt` (пропуск при `source_id`) | нет | 0–3 сек |
| Retrieval | `RetrievalService.collect_candidates` | да (из сессии) | 2–4 сек |
| Scoring | `ScoringService.rank` | нет | 1–2 сек (после warmup) |
| Export | `YandexMusicService.export_playlist` | да | 1–3 сек |

**Целевая latency:** 7–12 сек (промпт → `playlist_url`).

**Headers:** `Authorization: Bearer <session_id>` (обязательно; OAuth-токен Яндекса берётся из сессии на сервере)

**Запрос:**
```json
{
  "prompt": "Саундтрек для ночной поездки по пустому шоссе в стиле нео-нуар и синтвейв",
  "track_count": 25,
  "instrumental_only": false,
  "exclude_artists": ["Kavinsky"],
  "diversity": "normal",
  "source_id": null
}
```

| Поле | Тип | Обязательно | По умолчанию | Ограничения |
|------|-----|-------------|--------------|-------------|
| `prompt` | string | да | — | 1–2000 символов |
| `track_count` | int | нет | 25 | 1–50 |
| `instrumental_only` | bool | нет | `false` | передаётся в LLM как `vocal_type: instrumental_only` |
| `exclude_artists` | string[] | нет | `[]` | max 20; убирает артистов из якорей и кандидатов |
| `diversity` | `"normal"` \| `"high"` | нет | `"normal"` | `high` — жёстче diversity (1 трек/артист, 2 для якорей) |
| `source_id` | UUID \| null | нет | `null` | своя генерация: reuse `MusicProfile`, LLM не вызывается; всегда **новый** плейлист в Яндексе |

**Ответ `200`:**
```json
{
  "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "prompt": "Саундтрек для ночной поездки…",
  "title": "Ночной Неон: Пустое Шоссе",
  "description": "Атмосферный синтвейв и ретровейв для ночной дороги\n\nПромпт: Саундтрек для ночной поездки…",
  "playlist_url": "https://music.yandex.ru/users/username/playlists/1003",
  "tracks": [
    {
      "id": "40133452",
      "title": "Nightcall",
      "artist": "Kavinsky",
      "duration_ms": 259000,
      "similarity_score": 0.89
    }
  ],
  "pool_stats": {
    "raw": 180,
    "clean": 72,
    "selected": 25
  },
  "profile": {
    "playlist_title": "Ночной Неон: Пустое Шоссе",
    "playlist_description": "Атмосферный синтвейв…",
    "primary_genres": ["synthwave", "retrowave"],
    "mood_tags": ["nocturnal", "atmospheric"],
    "vocal_type": "any",
    "reference_artists": ["Kavinsky", "Perturbator", "Gunship", "Timecop1983"],
    "search_queries": ["synthwave night drive", "retrowave neon", "dark synth"],
    "target_track_count": 25
  },
  "options": {
    "track_count": 25,
    "instrumental_only": false,
    "exclude_artists": ["Kavinsky"],
    "diversity": "normal"
  },
  "warnings": []
}
```

**Семантика полей ответа:**

| Поле | Источник | Примечание |
|------|----------|------------|
| `id` | PostgreSQL `playlist_generations` | id записи истории |
| `prompt` | запрос | исходный промпт |
| `title` | `MusicProfile.playlist_title` (LLM) | же название, что у плейлиста в Яндексе |
| `description` | `playlist_description` + промпт | формат: `{описание}\n\nПромпт: {prompt}`; промпт не дублируется, если уже есть в описании |
| `playlist_url` | export | `https://music.yandex.ru/users/{login}/playlists/{kind}`; `login` — из сессии |
| `tracks` | scoring, в порядке релевантности | длина = `track_count` (или меньше при нехватке кандидатов) |
| `tracks[].artist` | scoring | несколько исполнителей через `", "` |
| `tracks[].similarity_score` | scoring | cosine similarity (embedding) или fallback-score; округление до 4 знаков |
| `pool_stats` | retrieval + scoring | `raw` / `clean` (после pre-filter) / `selected`; диагностика полноты |
| `profile` | LLM или reuse из `source_id` | полный `MusicProfile` после опций (`exclude_artists` и т.д.) |
| `options` | запрос | `track_count`, `instrumental_only`, `exclude_artists`, `diversity` — для regen/history |
| `warnings` | pipeline | напр. `exclude_artists` не сняты с якорей (нужно ≥4); не блокирует `200` |

**Export (что происходит в Яндексе):**

1. `users_playlists_create(title=profile.playlist_title)`
2. `users_playlists_insert_track(kind, track_id, album_id, at=i, revision=…)` — по одному, `revision` обновляется после каждой вставки
3. `users_playlists_description(kind, description)` — описание из ответа API
4. URL по `login` сессии и `kind` созданного плейлиста
5. Persist в `playlist_generations` (история пользователя)

Подробности SDK: [YANDEX_MUSIC.md](YANDEX_MUSIC.md) § «Экспорт плейлиста».

**Scoring внутри пайплайна:** при недоступности embedding-модели используется fallback (жанры + reference artists), но запрос всё равно завершается `200`, если export успешен. Поле `method` в ответ **не** включается (оно есть только у `POST /scoring/rank`).

**Логи сервера (latency по этапам):**

```
Playlist pipeline: llm=2140ms retrieval=3214ms scoring=1842ms export=1520ms total=8716ms tracks=25 method=embedding
```

`method`: `embedding` | `fallback`. Смотреть: `docker compose logs -f api` или `make logs`.

**Ошибки:**

| Код | Когда | `detail` (пример) |
|-----|-------|-------------------|
| `401` | нет/невалидный Bearer, истёкшая сессия | `Invalid or expired session` |
| `404` | `source_id` не найден или чужой | `Source generation not found` |
| `422` | пустой промпт, `track_count` вне 1–50, промпт > 2000 символов | Pydantic validation |
| `504` | превышен `PIPELINE_TIMEOUT_SEC` (default 45) | `Playlist generation exceeded …s (PIPELINE_TIMEOUT_SEC)` |
| `500` | scoring вернул 0 треков или внутренняя ошибка ранжирования | `Scoring returned no tracks` |
| `502` | Яндекс API недоступен после retry, ошибка export (создание/вставка/описание) | текст исключения |
| `503` | LLM недоступен (`OPENAI_API_KEY`), retrieval без кандидатов, сбой retrieval | `OPENAI_API_KEY is not configured`, `No candidates found for the prompt` |

**Пример (curl):**

```bash
curl -sS -X POST http://localhost:8000/api/v1/playlists/generate \
  -H "Authorization: Bearer $SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "dark synthwave for night coding", "track_count": 25}'
```

`SESSION_ID` — из `POST /auth/device-flow/poll` (`session_id` в ответе) или `GET /auth/me`.

**Отладка по этапам (без export):** отдельные эндпоинты `POST /llm/parse`, `POST /retrieval/candidates`, `POST /scoring/rank` или CLI `prompt-dj scoring rank --prompt "…" --token "$YANDEX_OAUTH_TOKEN"`.

### `GET /api/v1/playlists`

Список генераций текущего пользователя (новые сверху).

**Query:** `limit` (1–50, default 20), `offset` (default 0).

**Ответ `200`:**
```json
{
  "items": [
    {
      "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
      "prompt": "dark synthwave for night coding",
      "title": "Ночной неон",
      "playlist_url": "https://music.yandex.ru/users/username/playlists/1003",
      "pool_stats": {"raw": 180, "clean": 72, "selected": 25},
      "options": {
        "track_count": 25,
        "instrumental_only": false,
        "exclude_artists": [],
        "diversity": "high"
      },
      "created_at": "2026-09-15T12:00:00Z"
    }
  ],
  "limit": 20,
  "offset": 0
}
```

### `GET /api/v1/playlists/{id}`

Полная запись генерации (тот же контракт, что ответ `POST /generate`).

**Ошибки:** `401`, `404` (чужой или несуществующий id).

---

## Yandex Music API (SDK)

Все вызовы — через `ClientAsync` ([yandex-music-api](https://github.com/MarshalX/yandex-music-api) v3+), обёртка `YandexMusicService` (`backend/app/services/yandex_music_service.py`). OAuth-токен пользователя хранится в сессии (Fernet), в браузер не отдаётся.

**Поведение обёртки (для всех методов ниже):**

| Параметр | Значение по умолчанию | Env |
|----------|----------------------|-----|
| Пауза между запросами | 150 ms | `YANDEX_RATE_LIMIT_DELAY_SEC` |
| Retry при сетевых ошибках | 3 попытки, exponential backoff | `YANDEX_API_MAX_RETRIES` |
| Прокси | `HTTPS_PROXY` / `HTTP_PROXY` | см. `.env.example` |
| Исключения | `YandexMusicError` → HTTP `502`/`503` | — |

### Auth — OAuth Device Flow

| Метод SDK (`ClientAsync`) | Обёртка | Наш REST | Назначение |
|---------------------------|---------|----------|------------|
| `request_device_code()` | `request_device_code` | `POST /auth/device-flow/start` | Код для пользователя |
| `poll_device_token(device_code)` | `poll_device_token` | `POST /auth/device-flow/poll` | Опрос до `access_token` |
| `device_auth(on_code, timeout)` | `device_auth` | CLI `auth login` | Обёртка start + poll |
| `init()` | `init_client(token)` | — (внутри retrieval/export) | Инициализация клиента с токеном |
| `account_status()` | `get_account_status` | `GET /yandex/account`, `GET /auth/me` | `uid`, `login` для сессии и URL |

**Ответ `request_device_code` → наш `DeviceFlowStartResponse`:**

| Поле SDK | Поле REST |
|----------|-----------|
| `device_code` | `device_code` |
| `user_code` | `user_code` |
| `verification_url` | `verification_url` |
| `expires_in` | `expires_in` |
| `interval` | `interval` |

Таймаут poll: 120 сек (`DEVICE_FLOW_TIMEOUT_SEC`).

### Retrieval — сбор кандидатов

Вызывается из `RetrievalService.collect_candidates` (`POST /retrieval/candidates`, этап retrieval в `/playlists/generate`). Запросы по `MusicProfile` — **параллельно** (`asyncio.gather`).

| Метод SDK | Обёртка | Источник данных | Лимиты (defaults) |
|-----------|---------|-----------------|-------------------|
| `search(query, type_="track", page=N)` | `search_tracks` | `profile.search_queries` (+ expand) | 50 треков × 2 страницы на запрос |
| `search(name, type_="artist")` | `search_artist_id` | `profile.reference_artists` | первый результат |
| `artists_tracks(artist_id, page=0, page_size=N)` | `artists_top_tracks` | после `search_artist_id` | 10 треков на артиста |
| `tracks_similar(track_id)` | `tracks_similar_list` | `reference_track_id` (опционально) | все similar |
| `tracks(track_ids)` | `fetch_tracks` | обогащение кэша (album, genre, `available`) | batch по missing ids |

**Нормализация пула:** дедуп по `id` и `artist|title`, пропуск `available=False`. Цель: 150–300 кандидатов (`TARGET_CANDIDATES_POOL`, `MAX_CANDIDATES`).

**Кэш:** Redis, ключи по `track_id`, TTL 24h (`TRACK_CACHE_TTL_SEC`) — метод `tracks()` не дергается повторно для известных id.

### Export — создание плейлиста

Вызывается из `YandexMusicService.export_playlist` (этап export в `/playlists/generate`). Порядок **строгий**:

| # | Метод SDK | Сигнатура (ключевые аргументы) | Что передаём |
|---|-----------|-------------------------------|--------------|
| 1 | `users_playlists_create` | `(title, visibility="public")` | `profile.playlist_title` |
| 2 | `tracks` | `(track_ids)` | resolve `album_id` для каждого ranked track |
| 3 | `users_playlists_insert_track` | `(kind, track_id, album_id, at=i, revision=rev)` | по одному треку; `revision` из ответа предыдущей вставки |
| 4 | `users_playlists_description` | `(kind, description)` | `{playlist_description}\n\nПромпт: …` |
| — | URL (не SDK) | — | `https://music.yandex.ru/users/{login}/playlists/{kind}` |

**Важно для `insert_track`:** обязателен `album_id` (из `track.albums[0].id`). Треки без `album_id` пропускаются; если не осталось ни одного — `502` (`No tracks available for export`).

**Пример последовательности (псевдокод):**

```python
playlist = await client.users_playlists_create(title="Ночной неон")
# playlist.kind == 1003, playlist.revision == 1

for i, (track_id, album_id) in enumerate(refs):
    playlist = await client.users_playlists_insert_track(
        playlist.kind, track_id, album_id, at=i, revision=playlist.revision
    )
    # playlist.revision увеличивается на 1 после каждой вставки

await client.users_playlists_description(playlist.kind, description)
url = f"https://music.yandex.ru/users/{login}/playlists/{playlist.kind}"
```

### Сводка: какой REST → какие вызовы Яндекса

| Наш endpoint | Методы SDK (типичный набор) |
|--------------|----------------------------|
| `POST /auth/device-flow/start` | `request_device_code` |
| `POST /auth/device-flow/poll` | `poll_device_token`, `init`, `account_status` |
| `GET /auth/me` | — (данные из БД; токен не раскрывается) |
| `GET /yandex/account` | `init`, `account_status` |
| `POST /retrieval/candidates` | `init`, `search`×N, `artists_tracks`×4, `tracks_similar`?, `tracks` |
| `POST /playlists/generate` | всё из retrieval + export (`users_playlists_*`, `tracks`) |

Полная документация SDK, паспорт трека, нормализация: [YANDEX_MUSIC.md](YANDEX_MUSIC.md).

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
