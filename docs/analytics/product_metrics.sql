-- Product metrics over playlist_generations (P0.2 / P0.4)
-- Window: last 7 days. Adjust the interval as needed.
-- HTTP: GET /api/v1/metrics/product?days=7  (header X-Metrics-Token)

-- 1) Regen rate: share of generations that are «Ещё вариант» (source_id set)
SELECT
  count(*) FILTER (WHERE source_id IS NOT NULL)::float
    / nullif(count(*), 0) AS regen_rate,
  count(*) FILTER (WHERE source_id IS NOT NULL) AS regen_count,
  count(*) AS total_generations
FROM playlist_generations
WHERE created_at >= now() - interval '7 days';

-- 2) Return-7d (primary PRODUCT metric):
-- share of users with ≥2 generations in the last 7 days
-- (new or regen = «повторное действие»)
WITH active AS (
  SELECT
    user_id,
    count(*) AS gens
  FROM playlist_generations
  WHERE created_at >= now() - interval '7 days'
  GROUP BY user_id
)
SELECT
  count(*) FILTER (WHERE gens >= 2)::float
    / nullif(count(*), 0) AS return_7d,
  count(*) FILTER (WHERE gens >= 2) AS returning_users,
  count(*) AS active_users
FROM active;

-- 3) Latency p50 / p95
SELECT
  percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) AS latency_p50_ms,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS latency_p95_ms,
  avg(latency_ms)::int AS latency_avg_ms,
  count(*) FILTER (WHERE latency_ms IS NOT NULL) AS with_latency
FROM playlist_generations
WHERE created_at >= now() - interval '7 days';

-- 4) Full-N rate + warnings rate + avg clean
SELECT
  count(*) FILTER (
    WHERE (pool_stats->>'selected')::int = (options->>'track_count')::int
  )::float / nullif(count(*), 0) AS full_n_rate,
  count(*) FILTER (WHERE warnings_count > 0)::float
    / nullif(count(*), 0) AS warnings_rate,
  avg((pool_stats->>'clean')::float) AS avg_clean,
  avg(warnings_count)::float AS avg_warnings_count
FROM playlist_generations
WHERE created_at >= now() - interval '7 days'
  AND pool_stats IS NOT NULL
  AND options ? 'track_count';

-- 5) Like / dislike rates (among generations that received feedback)
SELECT
  count(*) FILTER (WHERE feedback = 1)::float
    / nullif(count(*) FILTER (WHERE feedback IS NOT NULL), 0) AS like_rate,
  count(*) FILTER (WHERE feedback = -1)::float
    / nullif(count(*) FILTER (WHERE feedback IS NOT NULL), 0) AS dislike_rate,
  count(*) FILTER (WHERE feedback = 1) AS likes,
  count(*) FILTER (WHERE feedback = -1) AS dislikes,
  count(*) FILTER (WHERE feedback IS NOT NULL) AS with_feedback,
  count(*) AS total_generations
FROM playlist_generations
WHERE created_at >= now() - interval '7 days';

-- 6) Diversity mix
SELECT
  options->>'diversity' AS diversity,
  count(*) AS cnt
FROM playlist_generations
WHERE created_at >= now() - interval '7 days'
GROUP BY 1
ORDER BY cnt DESC;

-- 7) Client channel (web vs telegram)
SELECT
  client_channel,
  count(*) AS cnt
FROM playlist_generations
WHERE created_at >= now() - interval '7 days'
GROUP BY 1
ORDER BY cnt DESC;

-- 8) Cost-per-generation (C5): LLM tokens + Yandex API calls
SELECT
  count(*) FILTER (WHERE generation_cost IS NOT NULL) AS with_cost,
  avg((generation_cost->'llm'->>'total_tokens')::float) AS avg_llm_total_tokens,
  avg((generation_cost->'yandex'->>'api_calls')::float) AS avg_yandex_api_calls,
  avg((generation_cost->'cover'->>'image_requests')::float) AS avg_cover_image_requests
FROM playlist_generations
WHERE created_at >= now() - interval '7 days'
  AND generation_cost IS NOT NULL;
