# Unit economics и монетизация

> Оценка себестоимости одной генерации плейлиста, тарифы провайдера, черновик цен.  
> Счётчики в проде: `playlist_generations.generation_cost` (C5), SQL — [analytics/product_metrics.sql](analytics/product_metrics.sql).  
> Обновлено: 2026-09-18.

## Провайдер и модели в пайплайне

| Компонент | Реализация | API-деньги |
|-----------|------------|------------|
| LLM → `MusicProfile` | KodikRouter, `openai/gpt-4o-mini` ([llm_config.py](../backend/app/core/llm_config.py)) | да |
| Scoring | `intfloat/multilingual-e5-base` на CPU в API-контейнере | нет |
| Retrieval / export | OAuth пользователя, **yandex-music** | нет |
| AI-обложка (P2.2) | KodikRouter `POST /v1/images/generations`, **`qwen/qwen-image-3-pro`**, default **1K**, **1:1** | да |

Тарифы ниже — **KodikRouter** (рубли за единицу). При смене провайдера или прайса обновить этот файл и пересчитать примеры.

### Тарифы KodikRouter (зафиксировано 2026-09-18)

**`gpt-4o-mini` (OpenAI)**

| | ₽ |
|--|---|
| Вход / 1M токенов | 7,22 |
| Выход / 1M токенов | 28,88 |
| Кэш-чтение / 1M | 3,61 |
| Контекст | 128k |

**`qwen` image (`/v1/images/generations`)**

| | ₽ |
|--|---|
| Входное изображение / изобр. | 0,289 |
| Выход **1K** / изобр. | **3,85** |
| Выход **2K** / изобр. | **7,22** |

Текст→image без референса: платится **выход** (1K или 2K). Вход 0,289 ₽ — только при image-to-image.

Конфиг по умолчанию: `PLAYLIST_COVER_ENABLED=true`, `PLAYLIST_COVER_RESOLUTION=1K` — см. [backend/.env.example](../backend/.env.example).

---

## Что считается в `generation_cost`

Структура ([schemas/generation_cost.py](../backend/app/schemas/generation_cost.py)):

- `llm`: `prompt_tokens`, `completion_tokens`, `total_tokens`, `requests` — **1 запрос** на новую генерацию; при regen (`source_id`) — **0**.
- `yandex`: `api_calls` — диагностика нагрузки на API, **не биллинг**.
- `cover`: `image_requests` — обычно **1** на генерацию, если обложка включена и API не упал.

Оценка в рублях в БД **пока не пишется** — только сырые счётчики; рубли считаются по формулам ниже.

---

## Формулы COGS (переменная часть)

**LLM (₽):**

```text
llm_rub = prompt_tokens / 1e6 × 7.22 + completion_tokens / 1e6 × 28.88
```

**Обложка (₽):**

```text
cover_rub = image_requests × (3.85 если 1K | 7.22 если 2K)
```

**Полная новая генерация:**

```text
total_rub ≈ llm_rub + cover_rub   # при PLAYLIST_COVER_ENABLED=true
```

**Regen («Ещё вариант»):** `llm_rub = 0`; если обложка снова запрашивается — снова **~3,85 ₽** (1K).

**Без обложки:** `total_rub ≈ llm_rub` (**~0,01–0,03 ₽** на типичном промпте).

---

## Ориентиры по токенам и COGS

| База | Prompt | Completion | LLM ₽ | + cover 1K | Итого ₽ |
|------|--------|------------|-------|------------|---------|
| Пример ответа API ([API.md](API.md)) | 1 820 | 640 | **0,031** | 3,85 | **~3,88** |
| Среднее по dev-БД (мало выборки) | 1 348 | 123 | **0,013** | 3,85 | **~3,86** |

Вывод: при включённой обложке **~99%** переменных расходов — **Qwen 1K (3,85 ₽)**; LLM на mini — копейки.

Яндекс и embeddings в COGS **не входят** (токен пользователя + свой CPU/RAM на VPS). Фикс инфраструктуры — порядок **~3 000–6 000 ₽/мес** на один инстанс API+БД+Redis; см. [INFRASTRUCTURE.md](INFRASTRUCTURE.md).

### Масштаб (только Kodik, новая gen + cover 1K ≈ 3,87 ₽)

| Генераций / мес | COGS Kodik ≈ |
|-----------------|--------------|
| 500 | ~1 900 ₽ |
| 5 000 | ~19 000 ₽ |
| 50 000 | ~190 000 ₽ |

Если regen тоже с новой обложкой, «клик» остаётся **~3,85–3,87 ₽** — regen почти не дешевле, пока не reuse обложки (бэклог, см. ниже).

---

## Продуктовые рычаги (связь с деньгами)

1. **Free без AI-обложки** — COGS **&lt;0,1 ₽** на генерацию; дневной лимит (`DAILY_GENERATION_LIMIT`) — от абьюза и latency, не от LLM.
2. **Pro = обложка 1K + выше лимит** — платят за то, что стоит **3,85 ₽** за запрос.
3. **«Ещё вариант»** — не paywall ([PRODUCT.md](PRODUCT.md)); экономика: **не перегенерировать cover** на каждый regen (reuse `cover_storage_key` / флаг «без новой обложки»).
4. **2K** — только осознанно: **+3,37 ₽** к 1K на каждую картинку.

---

## Черновик монетизации (не в коде)

Согласовано со стратегией в [PRODUCT.md](PRODUCT.md) §4: freemium N/день, Pro за лимиты и polish; regen не давить.

| Tier | Обложка | Лимит (идея) | Заметки |
|------|---------|--------------|---------|
| **Free** | нет | 3–5 новых / сутки (сейчас soft **10** UTC) | regen вне квоты |
| **Pro ~299 ₽/мес** | 1K | cap **~30–40** полных gen/мес с cover | при 30×3,87 ₽ COGS ≈ **116 ₽** → **~183 ₽** до инфра |
| **Пакет ~99 ₽** | 1K | +15 новых gen | COGS ≈ **58 ₽**, маржа ~**41 ₽** |
| **Pro+** | 2K опционально | только если явный запрос | +**3,37 ₽**/картинка vs 1K |

Окупаемость инфры **~4 000 ₽/мес** (грубо): **~25** платящих Pro при ~30 gen/мес и марже **~183 ₽** после Kodik.

Триггер внедрения биллинга в продукт: **P3.4** в [PRODUCT.md](PRODUCT.md) — есть спрос и метрики P0.

---

## Definition of Done «понятная экономика»

- [x] Счётчики C5 в БД и отчёт `/metrics/product`
- [x] Этот документ с тарифами и формулами
- [ ] `estimated_cost_rub` в `generation_cost` (опционально)
- [ ] Tiering в коде (Pro / cover gating / reuse cover on regen)

---

## Ссылки

- Контракт `generation_cost` в ответе generate: [API.md](API.md) § `POST /playlists/generate`
- SQL агрегаты: [analytics/product_metrics.sql](analytics/product_metrics.sql) §8
