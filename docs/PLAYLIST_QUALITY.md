# Качество плейлистов — статус и handoff

> **Для следующего агента.** Читать перед любыми правками retrieval/scoring/quality.  
> Обновлено: 2026-09-17 — Q1–Q5 ✅ (search hygiene, SEO, hard/soft anchors, plateau, language/diversity constraints).

## TL;DR

| Что | Статус |
|-----|--------|
| End-to-end пайплайн | ✅ `POST /playlists/generate` → 200, ссылка, треки |
| Frontend для теста | ✅ `/lab` — full форма + таблица + `pool_stats`; `/` — пользовательский UI |
| Промпт без артистов | ✅ LLM подбирает якоря, embedding по user prompt |
| SEO pre-filter | ✅ Универсальный (не список cooking/sleep) + Sad Rap / Melancholy |
| Топ релевантности | ✅ kitchen: Parcels / Khruangbin / Men I Trust / Camyo |
| **Полнота N треков** | ✅ discovered similar + frequency-rank; tail fill без `score[N-1]` |
| `pool_stats` в ответе | ✅ `{raw, clean, selected}` |
| Хвост / якоря / latency | ✅ gap, cap 60% hard-якорей, `rank_pool_merge`, `SCORING_EMBED_LIMIT=0` |
| Situational golden | ✅ сильный cold-start (кухня/код/сон…) |
| Named-artist + constraints | ✅ Q1–Q5 + structural: genre-only search ban, type beat, ref near-dup |
| Следующий фокус | Продукт — [PRODUCT.md](PRODUCT.md); пайплайн только с регрессом golden |

**Не ходить по кругу:** не добавлять regex под конкретный промпт/жанр.  
**Граница качества (продукт):** «достаточно хорошо, чтобы слушать целиком», не редакционка.

**Краткий диагноз (2026-09-17):** система сильна на situational cold-start; слабее на **named-artist + constraints + diversity**, потому что LLM раздувает якоря/`search_queries`, а при плоских scores ranking не отделяет сцену от lexical SEO. Максимальный ROI — **входы в пул** (queries + SEO filter + budget якорей), не ещё один проход retrieval и не rewrite user prompt.

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
    ↓ +0.03 hard-anchor boost (`hard_reference_artists`; soft refs — только retrieval)
    ↓ select: gap → mood-demote → plateau reorder → elbow → soft/tail fill → diversity
    ↓ diversity (2/3 обычно, 3 hard-якорям, 5 hard в tail) + cap hard-якорей ~60%
    ↓ prompt constraints: `разнообразн*` → diversity=high; `исключи русск*` → drop кириллицы
    ↓ [если selected < N] feedback: tops+similar лучших не-якорных → incremental re-score
    ↓ export
```

### Ключевые файлы

| Файл | Роль |
|------|------|
| `backend/app/services/llm_prompts.py` | Системный промпт, few-shot «макароны» / named-artist |
| `backend/app/services/retrieval_service.py` | Пул: search, tops, similar, discovered, feedback expand |
| `backend/app/utils/quality.py` | Pre-filter: SEO, genre-as-title, mood-keyword, hard helpers |
| `backend/app/utils/scoring.py` | Embedding query, elbow, fill, diversity, hard boost, plateau |
| `backend/app/utils/search_queries.py` | Блок generic SEO + mood-bait search-фраз |
| `backend/app/utils/prompt_constraints.py` | Q3/Q5: hard anchors, diversity hint, exclude_languages |
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
6. Mood-keyword artist: `Cozy'`, `COZY YiELDS`, `Melancholy Mø`
7. Mood-keyword title: `Cozy Forever`, `Sad Vibes`
8. Mood/genre-as-title: `Sad Rap`, `Get Est Rap`, `Asterisk Gang Emo Rap`, long genre-stack
9. Production spam: `type beat` / `free beat`
10. Reference в title (near-dup `ghostmane`≈Ghostemane) или размазан title+artist (`Night`+`Lovell…`)
11. Точный match артистов (не `Parcel` ≈ `Parcels` в поле artist)

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
| Anchor slots | 3 (strict), 5 (tail fill); **суммарный cap ~60%** плейлиста |
| Top-median gap | медиана топ-10 − 0.15 (отсекает embedding FP вроде Hauvy) |
| Fill фазы | strict elbow → soft (score[N−1]) → tail (**last−0.04**, без raise до score[N−1]) |
| Финал | сортировка по `similarity_score` desc |
| Feedback | `rank_pool_merge` — encode только новых кандидатов |

**Критичный фикс shortfall 19/25:** tail не должен брать `max(..., scores[N-1])` — топ-N часто занят якорями на cap, и пол блокировал остальных артистов.

---

## Открытые задачи (приоритет)

### P0 — Полнота 25 без мусора

1. ✅ Frequency-rank discovered + similar seeds.
2. ✅ Scoring feedback при `selected < N`.
3. ✅ `pool_stats` в API + badges в `/lab`.
4. ✅ Tail fill без `score[N-1]` — kitchen `n=25`, `clean≈275`.
5. Если API throttled — увеличить `yandex_rate_limit_delay_sec`, не убирать фильтры.

### P1 — Хвост ✅

1. ✅ Embedding false positives: `filter_by_top_median_gap` (медиана топ-10 − 0.15).
2. ✅ Cap якорей ~60% (`max_anchor_tracks`).

### P2 — Latency ✅

1. ✅ `/lab` показывает `tracks` + `similarity_score` + `pool_stats` (на `/` — без debug-метрик).
2. ✅ Double-embed убран: `rank_pool_merge` на feedback.
3. ✅ `SCORING_EMBED_LIMIT=0` в `.env` / example / config.
4. ✅ Референсный curl живёт здесь и в [API.md](API.md).

**Этап 6 (продукт/CI) ✅.** Дальше: [PRODUCT.md](PRODUCT.md) (metrics → бот → listening graph). Пайплайн не крутить без регресса golden; качество named-artist — секция ниже.

---

## Live-кейс: named-artist (2026-09-17)

**Промпт:** «хочется грустить под американский реп, по типу Bones или суисайд бойз, исключи русские треки, а также сделай плейлист разнообразным»

**`/lab`:** `raw=300`, `clean=250`, `selected=25` — пул здоровый; проблема не в shortfall.

| Поле профиля | Значение |
|--------------|----------|
| Жанры | hip hop, trap, emo rap |
| Mood | sad, melancholic, introspective |
| Референсы | Bones, $uicideboy$, Night Lovell, Lil Peep |
| Search | `Bones sad rap` · `$uicideboy$ emotional` · … · `Bones` |

**Scores:** 0.881 → 0.830 (почти плоско). Топ: Bones×5, $B×5, Night Lovell×4, Lil Peep×1 ≈ **60% cap якорей**. Хвост: `Sad Rap` (Musical Kay), Melancholy Mø, Token, Krayzie Bone, `Get Est Rap` (DISTXRD).

| Сработало | Сломалось |
|-----------|-----------|
| Сцена и якоря в топе | Токсичный query `Bones sad rap` → SEO в пул и в ranking |
| `clean=250` | 4 равноправных якоря съели diversity / cap |
| Нет явных RU-артистов | «разнообразным» не → `diversity=high`; «исключи русские» не first-class |
| | Flat tail: lexical SEO и коллизия имён (Krayzie Bone ≠ BONES) |

**Вердикт:** профиль и топ по смыслу верные; «всё верно» — нет. Слушать ~1–12/15; дальше шум. При жирном clean система *могла* выбрать лучше.

---

## Видение: где ломается класс named-artist

```
LLM понял сцену ✅
    → search_queries с mood+artist ❌  → SEO в raw
    → 4–8 reference_artists как hard-якоря ❌ → 60% слотов
constraints в NL («без русских», «разнообразно») ❌ → не опции
embedding + mood-слова ✅ для атмосферы
    → title «Sad Rap» / artist «Melancholy …» получают высокий cosine ❌
score plateau ❌ → tail = следующий по cosine, не «лучший из discovered»
```

Situational golden (без имён) этим почти не бьётся — поэтому CI зелёный, а live named-artist выглядит слабо.

---

## Бэклог качества (после MVP)

По рычагу × риск регресса golden. **Не** regex под cloud rap / Bones.

| # | Доработка | Зачем | Риск |
|---|-----------|-------|------|
| **Q1** | Гигиена `search_queries` (LLM few-shot + post-validate): запрет `{artist}+mood/genre`, `{mood} rap`; предпочитать имя / сцена / «like X» | Убрать Musical Kay-класс из пула | ✅ 2026-09-17 |
| **Q2** | Structural SEO: title ≈ genre+mood (`Sad Rap`, `Get Est Rap`); mood-keyword artist (`Melancholy …`) — расширение уже существующих правил; при правке — C4 split `quality.py` | Хвост при `clean≫N` | ✅ 2026-09-17 (без C4 split) |
| **Q3** | Hard vs soft anchors: из промпта / топ-2 = boost+slots; остальные refs — только retrieval | «Bones/$B + разнообразно» без стены из 15 треков | ✅ `hard_reference_artists` + scoring |
| **Q4** | Score plateau: при малом размахе топ-N предпочитать discovered/similar не-якорных; опц. demote lexical overlap title↔mood | Ghostemane остаётся, Token/SEO — нет | ✅ plateau reorder + mood demote |
| **Q5** | Constraints → опции: `exclude_languages` / map «разнообразн*» → `diversity=high` | Частый RU-каталожный pain | ✅ `prompt_constraints.py` + API field |

**Порядок внедрения:** ~~Q1 → Q2 → Q3 → Q4 → Q5~~ ✅.

**Не в приоритете качества:** ещё больший raw-пул; C4 ради рефакторинга; BPM/lyrics (PRODUCT P2); rewrite user prompt как основной рычаг.

---

## Предобработка user prompt — выводы

| Подход | Помогает? | Комментарий |
|--------|-----------|-------------|
| **Rewrite** текста промпта (второй LLM) | Слабо | В кейсе Bones LLM уже понял смысл; +latency/cost, drift, риск golden |
| **Constraint extraction** → опции / hard-soft anchors | Да | «исключи русские», «разнообразно», явные артисты → структура, сырой текст для embedding можно оставить |
| Preprocess **вместо** Q1–Q2 | Нет | Токсичные `search_queries` и SEO-title правятся на профиле / pre-filter |

Итог: тупой rewrite — низкий ROI. Лёгкий NLU → constraints + hard/soft anchors — рычаг **вместе** с валидацией `MusicProfile`, не вместо неё.

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
| Rewrite user prompt как фикс качества | Отклонён как основной рычаг (см. выше) |
| genre+mood / artist+mood в `expand`/`refine` | Убрано → mood-bait filter + artist/genre only (Q1) |
| Голый `primary_genres` в search (`emo rap`) | Убран → genre-only reject; только artist / artist+genre |

---

## Тесты

```bash
cd backend && ./.venv/bin/python -m pytest tests/ -q
# или
make test
```

Критичные: `tests/test_quality.py`, `tests/test_scoring.py`, `tests/test_retrieval.py`, `tests/test_playlist.py`, `tests/test_golden_prompts.py`.  
Feedback-path: `test_playlist_service_feedback_uses_rank_pool_merge` ✅.  
Golden: **7** промптов (kitchen…rain); CI fail = регресс-алерт (P0.5 ✅). Sync с frontend `SAMPLE_PROMPTS`.

После правок API: `docker compose restart api`.  
Frontend: `make up-frontend` или hot-reload контейнера `frontend`.

---

## Golden UI checklist

После правок quality/retrieval/scoring — прогнать unit golden (`make test`) и хотя бы 2–3 live-сценария из таблицы.

| # | Промпт (кнопка SAMPLE на `/lab`) | Ожидание live |
|---|------------------------|---------------|
| 1 | под настроение пока варю макароны | `selected==25`, `clean≥40`, топ без SEO «vibe for cooking» |
| 2 | спокойная музыка для кодинга поздней ночью | спокойный фокус; мало/нет агрессивного вокала |
| 3 | саундтрек для ночной поездки в стиле синтвейв | synthwave/retrowave в топе, не каверы «Nightcall» |
| 4 | энергичная музыка для пробежки | высокий темп/энергия; без sleep/ambient доминирования |
| 5 | тихая музыка чтобы уснуть | тихий эмбиент; без party/workout |
| 6 | танцевальный плейлист для вечеринки дома | danceable; без sleep |
| 7 | грустная музыка под дождь у окна | melancholy; без workout/party |

На каждом (`/lab`): latency в районе 7–12 сек (guardrail: p95 не ≫ 20); «Ещё вариант» работает; like/dislike кликается; смотреть `pool_stats` / scores. На `/` — только пользовательский результат (Яндекс + оценка).

Регресс-алерт: падение `tests/test_golden_prompts.py` в CI; вручную — расхождение с таблицей выше.

---

## Связанные документы

- [SPEC.md](SPEC.md) §4.3–4.4 — требования retrieval/scoring; §7–8 roadmap
- [PRODUCT.md](PRODUCT.md) — продуктовый бэклог после MVP
- [API.md](API.md) — контракт `POST /playlists/generate` + `pool_stats` / `options` / `warnings`
- [FRONTEND.md](FRONTEND.md) — ручной тест через UI
- [DEVELOPMENT.md](DEVELOPMENT.md) — этапы 0–6 ✅; чеклист 7+; техдолг
