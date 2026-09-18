# Работа с библиотекой yandex-music

Документация по интеграции с [yandex-music-api](https://github.com/MarshalX/yandex-music-api) v3+.  
Справочник «наш REST → SDK» — [API.md](API.md) § Yandex Music API.

**Обёртка в коде:** `YandexMusicService` (`backend/app/services/yandex_music_service.py`).  
Прямые вызовы `ClientAsync` вне сервиса — только в CLI для отладки.

## Авторизация (OAuth Device Flow)

Соответствует ТЗ §4.1. На REST — `POST /auth/device-flow/start` и `poll`.

| SDK | Async-обёртка | Возвращает |
|-----|---------------|------------|
| `client.request_device_code()` | `request_device_code()` | `DeviceCode`: `device_code`, `user_code`, `verification_url`, `expires_in`, `interval` |
| `client.poll_device_token(device_code)` | `poll_device_token(device_code)` | `OAuthToken` или `None` (ещё ждём) |
| `client.device_auth(on_code, timeout=120)` | `device_auth(...)` | `access_token` (CLI) |
| `client.init()` | `init_client(token)` | инициализированный `ClientAsync` |
| `client.account_status()` | `get_account_status(client)` | `Status` → `account.uid`, `account.login` |

```python
from yandex_music import ClientAsync

client = ClientAsync()
device_code = await client.request_device_code()
# → user_code, verification_url (passport.yandex.ru), device_code, expires_in, interval

token = await client.poll_device_token(device_code.device_code)
client = ClientAsync(token.access_token)
await client.init()
status = await client.account_status()
```

**Безопасность:**
- Токен шифруется (Fernet) перед записью в PostgreSQL
- Пароли Яндекса не используются и не сохраняются
- Токен — чтение каталога + создание/редактирование плейлистов пользователя

## Сбор кандидатов (ТЗ §4.3)

`RetrievalService` → параллельные задачи → `normalize_pool`.

| SDK | Обёртка | Источник | Конфиг |
|-----|---------|----------|--------|
| `search(query, type_="track", page=0..1)` | `search_tracks` | `MusicProfile.search_queries` | `SEARCH_TRACKS_PER_QUERY=50`, `SEARCH_PAGES=2` |
| `search(name, type_="artist")` | `search_artist_id` | `reference_artists[i]` | первый артист в выдаче |
| `artists_tracks(artist_id, page=0, page_size=10)` | `artists_top_tracks` | id артиста | `ARTIST_TRACKS_LIMIT=10` |
| `tracks_similar(track_id)` | `tracks_similar_list` | `reference_track_id` (опц.) | — |
| `tracks([id, ...])` | `fetch_tracks` | обогащение метаданных | Redis TTL 24h |

При нехватке пула (< `TARGET_CANDIDATES_POOL`) — дополнительные `search` с expand-запросами (`RETRIEVAL_EXPAND_PASSES`, `SEARCH_EXPAND_MAX_QUERIES`).

## Обогащение метаданных

| SDK | Назначение | Поля для пайплайна |
|-----|------------|-------------------|
| `tracks(track_ids)` | Дозагрузка missing | `duration_ms`, `albums[0].title`, `albums[0].genre`, `available` |
| `tracks_lyrics(track_id)` | `track_has_synced_lyrics` | soft filter «без слов» при `vocal_type=instrumental_only` (Redis cache) |

Кэш: `TrackCacheService` (Redis), TTL `TRACK_CACHE_TTL_SEC` (86400).

## Нормализация пула

```python
def normalize_pool(tracks: list) -> list:
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    result = []
    for track in tracks:
        if not track.available:
            continue
        key = f"{track.artists[0].name}|{track.title}".lower()
        if track.id in seen_ids or key in seen_titles:
            continue
        seen_ids.add(track.id)
        seen_titles.add(key)
        result.append(track)
    return result
```

Целевой размер: **150–300** уникальных треков (`TARGET_CANDIDATES_POOL`, `MAX_CANDIDATES`).

## Паспорт трека для скоринга

```python
def track_passport(track) -> str:
    artists = ", ".join(a.name for a in track.artists)
    album = track.albums[0].title if track.albums else ""
    genre = track.albums[0].genre if track.albums else ""
    version = getattr(track, "version", "") or ""
    return (
        f"Название: {track.title}. "
        f"Исполнитель: {artists}. "
        f"Альбом: {album}. "
        f"Жанр: {genre}. "
        f"Версия: {version}"
    )
```

Короткая версия для embeddings: `TrackCandidate.embedding_passport()` — `title. artists. genre`.

## Экспорт плейлиста (ТЗ §4.5)

`YandexMusicService.export_playlist` — вызывается из `PlaylistService.generate`.

### Сигнатуры SDK

```text
users_playlists_create(title: str, visibility: str = "public") → Playlist
users_playlists_insert_track(kind, track_id, album_id, at=0, revision=1) → Playlist
users_playlists_description(kind, description: str) → Playlist
tracks(track_ids: list) → list[Track]   # для album_id
```

### Порядок вызовов

```python
playlist = await client.users_playlists_create(title=profile.playlist_title)
# playlist.kind, playlist.revision

refs = []  # (track_id, album_id) — album_id из tracks()[].albums[0].id
for i, (track_id, album_id) in enumerate(refs):
    playlist = await client.users_playlists_insert_track(
        playlist.kind,
        track_id,
        album_id,
        at=i,
        revision=playlist.revision,
    )
    # revision обновлять из ответа после КАЖДОЙ вставки

await client.users_playlists_description(playlist.kind, description)
url = f"https://music.yandex.ru/users/{login}/playlists/{playlist.kind}"
```

**Описание:** `profile.playlist_description` + исходный промпт (`\n\nПромпт: …`), если промпт ещё не в тексте.

**Ограничения:**
- `album_id` обязателен для `insert_track`; треки без альбома пропускаются
- вставка по одному треку (revision optimistic locking)
- `login` для URL — из `Session.user.login`, не из SDK

## Паттерны в коде

- Все вызовы — через `YandexMusicService`, не напрямую из endpoints
- Rate limiting: `YANDEX_RATE_LIMIT_DELAY_SEC` (default 150 ms) перед каждым запросом
- Retry: `YANDEX_API_MAX_RETRIES` (default 3), backoff ×2, только `NetworkError` / `TimedOutError`
- `DeviceAuthError` — без retry, пробрасывается наверх
- `available=False` — пропуск при нормализации, не exception
- Прокси: `HTTPS_PROXY` для исходящих запросов к API Яндекса

## Ошибки → HTTP

| Исключение | HTTP (типично) | Где |
|------------|----------------|-----|
| `YandexMusicError` | `502` / `503` | retrieval, export, yandex account |
| `ExportError` | `502` | export (нет треков, битый playlist) |
| `DeviceAuthError` | `400` / `408` | device-flow poll |
