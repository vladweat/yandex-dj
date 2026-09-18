# Техническое задание: «Промпт-диджей» (Prompt DJ)

> Канонический документ требований. При расхождении с другими файлами приоритет у этого.

## 1. Общие сведения

### 1.1. Назначение

**«Промпт-диджей»** — программный комплекс для формирования персонализированных плейлистов в Яндекс Музыке на основе произвольного текстового описания (промпта).

### 1.2. Проблема

Стандартный поиск ориентирован на точное совпадение метаданных и не интерпретирует ассоциативные, эмоциональные и ситуационные запросы.

**Примеры неподдерживаемых запросов:**
- *«спокойная музыка для кодинга поздней ночью с элементами эмбиента и лоу-фая без слов»*
- *«музыка для тренировки с разгоном темпа»*

### 1.3. Цель

Трансформировать абстрактный запрос в структурированный музыкальный профиль, выполнить семантический поиск и ранжирование в каталоге Яндекс Музыки, автоматически сохранить плейлист в аккаунт пользователя.

---

## 2. Технологический стек

Зафиксированный стек: [STACK.md](STACK.md).

| Подсистема | Стек |
|------------|------|
| Язык | Python 3.12 |
| API Яндекс Музыки | `yandex-music` v3+ |
| LLM | **OpenAI API** (`openai` SDK, `gpt-4o-mini`) |
| Structured Output | Pydantic v2 + **instructor** |
| Embeddings | **sentence-transformers** (`intfloat/multilingual-e5-base`) — с первого релиза скоринга |
| Скоринг | **numpy** (cosine similarity) |
| Бэкенд и UI (первый) | **FastAPI** + uvicorn |
| CLI (вспомогательный) | **click** |
| БД | **PostgreSQL 15** + SQLAlchemy |
| Кэш | Redis 7 (этап retrieval) |
| Dev | **ruff**, pytest |
| Backlog | Telegram, Celery, audio ML |

---

## 3. Архитектура

```
[Пользователь] ──> (Промпт + Токен)
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Prompt Understanding (LLM Engine)                        │
│    Декомпозиция NL → MusicProfile (JSON)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Candidate Retrieval (Yandex Music Crawler)               │
│    Параллельный опрос API → пул 150–300 кандидатов          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Scoring & Ranking (ML / Embeddings)                      │
│    Векторизация → cosine similarity → diversity → топ-N     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Playlist Builder & Export                                │
│    Создание плейлиста → публичная ссылка                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Функциональные требования

### 4.1. Авторизация

1. **OAuth Device Flow:**
   - `client.request_device_code()` → ссылка + одноразовый код
   - Пользователь подтверждает на `ya.ru/device`
   - `poll_device_token()` до подтверждения или таймаута (120 сек)
2. **Безопасность:**
   - Токен в БД зашифрован (Fernet / AES-256)
   - Только чтение каталога + запись плейлиста
   - Пароли Яндекса не сохраняются

### 4.2. Парсер намерений (LLM)

**Вход:** текст на русском или английском.

**Логика:**
- Жанры (прямые и неявные), mood, activity
- Инструментальность (`vocal_type`)
- 4–8 референсных артистов
- 3–5 поисковых фраз
- Название и описание плейлиста

**Выход:** `MusicProfile` — см. [LLM_SCHEMA.md](LLM_SCHEMA.md).

### 4.3. Сбор кандидатов

Пул **150–300** raw, цель **≥50 clean** после pre-filter — см. [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md).

| Источник | Метод | Объём |
|----------|-------|-------|
| Полнотекстовый поиск | `client.search` | по `search_queries` |
| Артисты-референсы | `client.artists_tracks` | топ-20 на артиста |
| Похожие треки | `client.tracks_similar` | seeds от якорей (до 12 вызовов) |
| Discovered artists | `artists_tracks` + `tracks_similar` | frequency-rank не-якорных → топы + similar |
| Scoring feedback | tops + similar | если selected < N — лучшие не-якорные из ranked pool |
| Expand passes | `expand_search_queries` | до 4 проходов при малом пуле |

**Нормализация:**
- Дедупликация по `track.id`
- Исключение `available == False`
- Дедупликация по «Артист + Название» (разные альбомы)

### 4.4. Скоринг и ранжирование

**Паспорт трека:**
```
Название: {title}. Исполнитель: {artists}. Альбом: {album}. Жанр: {genre}. Версия: {version}
```

**Формула:**
\[
\text{Score}(t) = \frac{\vec{v}_{prompt} \cdot \vec{v}_t}{\|\vec{v}_{prompt}\| \|\vec{v}_t\|}
\]

**Diversity Filtering:**
- ≤25 треков → max **2** трека на артиста
- 26–50 треков → max **3** трека на артиста
- Лимит считается по **всем** исполнителям в `artists[]` (не только первому)
- Дедуп по нормализованному названию трека
- Топ-N по умолчанию N=25; допустимо меньше при нехватке релевантных кандидатов

**Промпт без артистов:** пользователь может описать только настроение или ситуацию («пока карю макароны»). LLM сам подберёт `reference_artists` и `search_queries` для retrieval; embedding-запрос строится из **исходного промпта** + описания/жанров/настроения, без списка артистов.

**Принцип отбора (универсальный, без хардкода жанров):**
1. **Pre-filter** — объективный мусор каталога: аранжировки/каверы, compilation-artist (`саундтрек`, `Soundtrack & Theme Orchestra`), SEO-шаблоны (`… - Vibe for …`, genre-as-title `Upbeat Indie Pop`, лейблы `Vinyl Sounds` / `MoodMode`), reference artist в title без исполнителя
2. **Embedding** — весь пул кандидатов (`SCORING_EMBED_LIMIT=0`); cosine similarity к промпту пользователя и атмосфере
3. **Reference anchor boost** — +0.03 к score треков якорных артистов из retrieval (в embedding-запрос не входят)
4. **Adaptive cutoff** — порог по наибольшему разрыву score (elbow) в ранжированном списке
5. **Diversity** — max 2/3 трека на исполнителя; для якорных `reference_artists` — до **3** (tail fill до **5**)
6. **Fill** — три фазы (strict elbow → soft score[N−1] → tail last−0.04); финальная сортировка по score
   - Tail **не** поднимает пол до score[N−1]: иначе при концентрации якорей в топе недобор (19/25 при clean≫N)

Релевантность промпту определяет **модель**, не regex. Допустимо < N треков, если **clean-пул** после pre-filter меньше N (текущая проблема — см. [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md)).

**Fallback:** при недоступности эмбеддингов — ранжирование по жанрам + reference artists.

### 4.5. Экспорт

1. `users_playlists_create(title)`
2. `users_playlists_insert_track()` — пакетно
3. Описание с исходным промптом
4. Ссылка: `https://music.yandex.ru/users/{login}/playlists/{kind}`

---

## 5. Нефункциональные требования

| Требование | Значение |
|------------|----------|
| Latency (промпт → ссылка) | 7–12 сек |
| LLM | 2–3 сек |
| Retrieval (async) | 2–4 сек |
| Scoring (CPU) | 1–2 сек |
| Rate limiting | Паузы + retry с exponential backoff |
| Изоляция данных | Пользователь видит только свои плейлисты |

---

## 6. Контракты данных

### 6.1. MusicProfile

См. [LLM_SCHEMA.md](LLM_SCHEMA.md).

### 6.2. REST API

См. [API.md](API.md).

---

## 7. Roadmap

| Этап | Содержание | Статус |
|------|------------|--------|
| 0–1 | Инфраструктура, OAuth Device Flow | ✅ |
| 1.5 | Next.js UI (Device Flow + генерация) | ✅ |
| 2–4 | LLM → retrieval → scoring | ✅ |
| 5 | Export + FastAPI end-to-end | ✅ |
| 5.5 | Качество: P0/P1/P2 (хвост, якоря, latency) | ✅ |
| 6 | История, реген, опции, UX, CI | ✅ |
| **7+** | Product: metrics → бот → listening graph → lyrics/обложка | backlog — [PRODUCT.md](PRODUCT.md) |

Детальный чеклист: [DEVELOPMENT.md](DEVELOPMENT.md). Качество: [PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md). Продукт: [PRODUCT.md](PRODUCT.md).

---

## 8. Ближайшие доработки и backlog

**Закрыто (ядро):**
- ✅ Этап 5.5: хвост (top-median gap, cap якорей 60%), latency (`rank_pool_merge`, `SCORING_EMBED_LIMIT=0`)
- ✅ Этап 6: история, «ещё вариант», options, warnings, timeout/abort, CI, golden
- ✅ Eng debt A/B/C1–C5 (`generation_cost`, split `quality.py`)
- ✅ Продукт P0–P2 (см. [PRODUCT.md](PRODUCT.md))

**Открыто — [PRODUCT.md](PRODUCT.md):**

| Приоритет | Фокус |
|-----------|--------|
| **P1.1** | Telegram E2E (код ✅, [TELEGRAM.md](TELEGRAM.md)) |
| **P3** | BPM, Celery, hard rate-limit Яндекс, freemium — по триггеру |
| **C6** | E2E smoke Яндекс в CI (test-аккаунт) |

**Не сейчас:** multi-catalog, org-mode, перепись UI, редакционный уровень, монетизация «Ещё вариант».

**Инвариант качества:** релевантность — моделью, не regex под промпт/жанр ([PLAYLIST_QUALITY.md](PLAYLIST_QUALITY.md)).