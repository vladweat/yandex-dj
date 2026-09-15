# Качество плейлистов — статус и handoff

> **Для следующего агента.** Читать перед любыми правками retrieval/scoring/quality.  
> Обновлено: 2026-09-15 — P0 закрыт (kitchen: 25/25, clean≈275); UI генерации включён.

## TL;DR

| Что | Статус |
|-----|--------|
| End-to-end пайплайн | ✅ `POST /playlists/generate` → 200, ссылка, треки |
| Frontend для теста | ✅ `/` — форма + таблица + `pool_stats` (без «Скоро») |
| Промпт без артистов | ✅ LLM подбирает якоря, embedding по user prompt |
| SEO pre-filter | ✅ Универсальный (не список cooking/sleep) |
| Топ релевантности | ✅ kitchen: Parcels / Khruangbin / Men I Trust / Camyo |
| **Полнота N треков** | ✅ discovered similar + frequency-rank; tail fill без `score[N-1]` |
| `pool_stats` в ответе | ✅ `{raw, clean, selected}` |
| Latency 7–12 сек | ⚠️ Часто 10–20+ сек; feedback/второй embed только если selected < N |

**Не ходить по кругу:** не добавлять regex под конкретный промпт/жанр.

---

## Референсный тест

**UI:** http://localhost:3001 → логин Device Flow → пример «под настроение пока варю макароны» → смотреть таблицу + badges `raw/clean/selected`.

**API:**

```bash
# SESSION_ID — UUID из Device Flow / БД
curl -sS -X POST http://localhost:8000/api/v1/playlists/generate \
  -H "Authorization: Bearer $SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "под настроение пока варю макароны", "track_count": 25}' \
  | jq '{title, n: (.tracks|length), pool_stats, top: [.tracks[:5][]|{score:.similarity_score, artist, title}]}'
```

**Ожидание (зафиксировано 2026-09-15):** `n == 25`, `pool_stats.clean ≥ 40`, в топе Parcels / Khruangbin / Men I Trust / Camyo.

**Типичные провалы хвоста (P1):** Hauvy «Vlone» (embedding false positive). SEO «Indie Pop» / «Vibe for Cooking» — должны отсекаться pre-filter.

**Диагностика в логах API** (`make logs`):

```
Retrieved N candidates (M clean) in …ms
Added … similar tracks from … anchor seeds
Added … tracks from … discovered artists (…)
Scoring pool: raw=N clean=M target=25
Playlist pipeline: … tracks=… method=embedding raw=… clean=…
```

Если `clean < 40` — scoring физически не соберёт 25 качественных треков.

---

## Архитектура (текущая)

```
user prompt
    ↓ LLM → MusicProfile (reference_artists, search_queries — без SEO-фраз)
    ↓ retrieval (search + artist tops + similar + discovered artists)
    ↓ pre-filter (quality.py — универсальный SEO/мусор)
    ↓ embedding (prompt + description + genres + mood; БЕЗ reference_artists в query)
    ↓ +0.03 anchor boost (reference_artists в исполнителях)
    ↓ select: elbow → soft fill → tail (last−0.04) → sort by score
    ↓ diversity (2/3 обычно, 3 якорям, 5 якорям в tail)
    ↓ [если selected < N] feedback: tops+similar лучших не-якорных → re-score
    ↓ export
```

### Ключевые файлы

| Файл | Роль |
|------|------|
| `backend/app/services/llm_prompts.py` | Системный промпт, few-shot «макароны» |
| `backend/app/services/retrieval_service.py` | Пул: search, tops, similar, discovered, feedback expand |
| `backend/app/utils/quality.py` | Pre-filter: SEO, genre-as-title, anchor-in-title |
| `backend/app/utils/scoring.py` | Embedding query, elbow, fill, diversity, anchor boost |
| `backend/app/utils/search_queries.py` | Блок generic SEO search-фраз |
| `backend/app/core/config.py` | `min_clean_candidates`, `discovered_*`, `feedback_*` |
| `frontend/src/features/playlist/*` | Форма генерации + результат для ручного теста |

---

## Pre-filter (quality.py) — что уже есть

**Универсальные правила (не привязка к промпту):**

1. Аранжировки/каверы (`cover`, `piano version`, …)
2. Compilation-artist (`саундтрек`, `Soundtrack & Theme Orchestra`, …)
3. Functional SEO: `vibe for`, `music for` у лейбла, `{context} music`
4. Genre-as-title: `Upbeat Indie Pop`, `Indie Mindy`, стек 2+ жанров
5. SEO-лейблы: `Vinyl Sounds`, `MoodMode`, `Waco Texas Metal`
6. Mood-keyword artist: `Cozy'`, `COZY YiELDS`
7. Mood-keyword title: `Cozy Forever`
8. Reference в title без исполнителя (`Parcel` ≈ `Parcels`, `Nightcall - Kavinsky`)
9. Точный match артистов (не `Parcel` ≈ `Parcels` в поле artist)

**Исключение:** Brian Eno «Music for Airports» — не фильтруется.

**Не делать:** regex под synthwave/pop-punk/cooking; keyword match user prompt в фильтрах.

---

## Retrieval — что уже есть

| Механизм | Config / код |
|----------|----------------|
| Search по `search_queries` | `search_tracks_per_query=50`, `search_pages=2` |
| Топы якорей | `artist_tracks_limit=20` |
| Expand search | `retrieval_expand_passes=4`, `expand_search_queries()` |
| Similar от якорей | до 3 seed × артистов, `max_similar_requests=12` |
| **Discovered artists** | frequency-rank → топы + similar (`discovered_artists_limit=12`, `discovered_similar_seeds=8`) |
| Quality loop | пока `clean < min_clean_candidates` (50), до 5 проходов |
| **Scoring feedback** | если selected < N → tops+similar топ не-якорных |

**Зачем similar у discovered:** топы дают *глубину* по тем же артистам (diversity 2/артист), similar — *ширину* (новые исполнители в пул).

---

## Scoring — что уже есть

| Параметр | Значение |
|----------|----------|
| `SCORING_EMBED_LIMIT` | `0` (весь пул) |
| Anchor boost | `+0.03` |
| Anchor slots | 3 (strict), 5 (tail fill) |
| Fill фазы | strict elbow → soft (score[N−1]) → tail (**last−0.04**, без raise до score[N−1]) |
| Финал | сортировка по `similarity_score` desc |

**Критичный фикс shortfall 19/25:** tail не должен брать `max(..., scores[N-1])` — топ-N часто занят якорями на cap, и пол блокировал остальных артистов.

---

## Открытые задачи (приоритет)

### P0 — Полнота 25 без мусора

1. ✅ Frequency-rank discovered + similar seeds.
2. ✅ Scoring feedback при `selected < N`.
3. ✅ `pool_stats` в API + badges во frontend.
4. ✅ Tail fill без `score[N-1]` — kitchen `n=25`, `clean≈275`.
5. Если API throttled — увеличить `yandex_rate_limit_delay_sec`, не убирать фильтры.

### P1 — Хвост

1. **Embedding false positives** (Hauvy «Vlone»): не лечится regex. Варианты:
   - минимальный gap к медиане топ-10;
   - штраф треков без жанрового пересечения с `primary_genres` (осторожно, универсально);
   - rerank top-50 cross-encoder (дорого).
2. **Перекос на якоря** (~80%): после набора 25 увеличить diversity на non-anchor или cap anchor at 60% плейлиста.

### P2 — Продукт

1. ✅ Frontend показывает `tracks` + `similarity_score` + `pool_stats`.
2. **Latency budget:** full-pool embed vs 7–12 сек — замерить; возможно `SCORING_EMBED_LIMIT=80`.
3. ✅ Референсный curl живёт здесь и в [API.md](API.md); SPEC §8 только ссылается.

---

## Что уже пробовали (не повторять без новой гипотезы)

| Подход | Результат |
|--------|-----------|
| Regex под cooking/sleep SEO | Заменён структурным `vibe for` / genre-as-title |
| `reference_artists` в embedding | Убрано — тянет SEO по жанру |
| Жёсткий `min_score=0.82` | Убрано → adaptive elbow |
| `merge_embedding_rank` fallback tail | Убрано — заливал мусор |
| Tail fill `min_score=None` | Заливал metal/мусор → заменён tail floor |
| Tail `max(..., score[N-1])` | Shortfall 19/25 при якорях в топе → убран |
| Только больше regex | Пул не растёт, топ уже хорош |

---

## Тесты

```bash
cd backend && ./.venv/bin/python -m pytest tests/ -q
# или
make test
```

Критичные: `tests/test_quality.py`, `tests/test_scoring.py`, `tests/test_retrieval.py`, `tests/test_playlist.py`.

После правок API: `docker compose restart api`.  
Frontend: `make up-frontend` или hot-reload контейнера `frontend`.

---

## Связанные документы

- [SPEC.md](SPEC.md) §4.3–4.4 — требования retrieval/scoring
- [API.md](API.md) — контракт `POST /playlists/generate` + `pool_stats`
- [FRONTEND.md](FRONTEND.md) — ручной тест через UI
- [DEVELOPMENT.md](DEVELOPMENT.md) — этапы roadmap
