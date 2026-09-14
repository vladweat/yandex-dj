# Работа с библиотекой yandex-music

Документация по интеграции с [yandex-music-api](https://github.com/MarshalX/yandex-music-api) v3+.

## Авторизация (OAuth Device Flow)

Соответствует ТЗ §4.1.

```python
from yandex_music import Client

client = Client()

# 1. Запрос кода
device_code = client.request_device_code()
# → user_code, verification_url (ya.ru/device), device_code, expires_in, interval

# 2. Показать пользователю user_code и verification_url

# 3. Опрос до подтверждения (таймаут 120 сек)
token = client.poll_device_token(device_code.device_code)
# Альтернатива: client.device_auth() — обёртка над обоими шагами

client = Client(token).init()
```

**Безопасность:**
- Токен шифруется (Fernet) перед записью в PostgreSQL
- Пароли Яндекса не используются и не сохраняются
- Токен — только чтение каталога + запись плейлиста

## Сбор кандидатов (ТЗ §4.3)

| Метод | Назначение | Лимит |
|-------|------------|-------|
| `client.search(query, type_='track')` | По `search_queries` от LLM | все фразы |
| `client.artists_tracks(artist_id)` | По `reference_artists` | топ-10 на артиста |
| `client.tracks_similar(track_id)` | Если указан трек-референс | — |

Выполнять **параллельно** через async-обёртку.

## Обогащение метаданных

| Метод | Назначение |
|-------|------------|
| `client.tracks(track_ids)` | Длительность, альбом, жанры, `available` |
| `client.tracks_lyrics(track_id)` | Текст (backlog: фильтрация контента) |

Кэшировать в Redis (TTL 24h), чтобы не спамить API.

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

Целевой размер: **150–300** уникальных треков.

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

## Экспорт плейлиста (ТЗ §4.5)

```python
playlist = client.users_playlists_create(title=profile.playlist_title)

for i, track_id in enumerate(ranked_ids):
    client.users_playlists_insert_track(
        playlist.kind,
        track_id,
        revision=playlist.revision,
        at=i,
    )
    playlist.revision += 1  # обновлять revision после каждой вставки

# URL результата
url = f"https://music.yandex.ru/users/{login}/playlists/{playlist.kind}"
```

Описание плейлиста — `profile.playlist_description` + исходный промпт пользователя.

## Паттерны в коде

- Все вызовы — через `YandexMusicClient`, не напрямую
- Rate limiting: пауза 100–200ms между batch-запросами
- Retry с exponential backoff при HTTP 429/5xx
- `available=False` — пропуск без исключения
