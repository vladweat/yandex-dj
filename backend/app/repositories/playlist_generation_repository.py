import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.playlist_generation import PlaylistGeneration


class PlaylistGenerationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def count_new_generations_since(
        self,
        user_id: uuid.UUID,
        *,
        since: datetime,
    ) -> int:
        """Считает только новые генерации (без source_id) — soft-квота freemium."""
        result = await self._db.execute(
            select(func.count())
            .select_from(PlaylistGeneration)
            .where(
                PlaylistGeneration.user_id == user_id,
                PlaylistGeneration.source_id.is_(None),
                PlaylistGeneration.created_at >= since,
            )
        )
        return int(result.scalar_one())

    async def aggregate_product_metrics(self, *, since: datetime) -> dict[str, Any]:
        """Single-window product report (P0.4). Mirrors docs/analytics/product_metrics.sql."""
        result = await self._db.execute(
            text(
                """
                WITH windowed AS (
                  SELECT *
                  FROM playlist_generations
                  WHERE created_at >= :since
                ),
                active AS (
                  SELECT user_id, count(*) AS gens
                  FROM windowed
                  GROUP BY user_id
                )
                SELECT
                  (SELECT count(*) FROM windowed)::int AS total_generations,
                  (SELECT percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms)
                     FROM windowed WHERE latency_ms IS NOT NULL) AS latency_p50_ms,
                  (SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
                     FROM windowed WHERE latency_ms IS NOT NULL) AS latency_p95_ms,
                  (SELECT avg(latency_ms)
                     FROM windowed WHERE latency_ms IS NOT NULL) AS latency_avg_ms,
                  (SELECT count(*) FILTER (WHERE latency_ms IS NOT NULL)
                     FROM windowed)::int AS with_latency,
                  (SELECT count(*) FILTER (
                       WHERE pool_stats IS NOT NULL
                         AND options ? 'track_count'
                         AND (pool_stats->>'selected')::int
                             = (options->>'track_count')::int
                     )::float / nullif(count(*), 0)
                     FROM windowed) AS full_n_rate,
                  (SELECT count(*) FILTER (WHERE warnings_count > 0)::float
                       / nullif(count(*), 0)
                     FROM windowed) AS warnings_rate,
                  (SELECT count(*) FILTER (WHERE source_id IS NOT NULL)::float
                       / nullif(count(*), 0)
                     FROM windowed) AS regen_rate,
                  (SELECT count(*) FILTER (WHERE source_id IS NOT NULL)
                     FROM windowed)::int AS regen_count,
                  (SELECT count(*) FILTER (WHERE gens >= 2)::float
                       / nullif(count(*), 0)
                     FROM active) AS return_7d,
                  (SELECT count(*) FILTER (WHERE gens >= 2)
                     FROM active)::int AS returning_users,
                  (SELECT count(*) FROM active)::int AS active_users,
                  (SELECT count(*) FILTER (WHERE feedback = 1)::float
                       / nullif(count(*) FILTER (WHERE feedback IS NOT NULL), 0)
                     FROM windowed) AS like_rate,
                  (SELECT count(*) FILTER (WHERE feedback = -1)::float
                       / nullif(count(*) FILTER (WHERE feedback IS NOT NULL), 0)
                     FROM windowed) AS dislike_rate,
                  (SELECT count(*) FILTER (WHERE feedback IS NOT NULL)
                     FROM windowed)::int AS with_feedback,
                  (SELECT avg((pool_stats->>'clean')::float)
                     FROM windowed
                     WHERE pool_stats IS NOT NULL AND pool_stats ? 'clean') AS avg_clean,
                  (SELECT count(*) FILTER (WHERE client_channel = 'telegram')
                     FROM windowed)::int AS generations_telegram,
                  (SELECT count(*) FILTER (WHERE client_channel = 'web')
                     FROM windowed)::int AS generations_web
                """
            ),
            {"since": since},
        )
        row = result.mappings().one()
        out: dict[str, Any] = {}
        for key, value in dict(row).items():
            if isinstance(value, Decimal):
                out[key] = float(value)
            else:
                out[key] = value
        return out

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        prompt: str,
        title: str,
        description: str,
        playlist_url: str,
        yandex_kind: str | None,
        profile: dict[str, Any],
        tracks: list[Any],
        pool_stats: dict[str, Any] | None,
        options: dict[str, Any],
        source_id: uuid.UUID | None = None,
        id: uuid.UUID | None = None,
        latency_ms: int | None = None,
        latency_breakdown: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
        warnings_count: int = 0,
        client_channel: str = "web",
        cover_storage_key: str | None = None,
    ) -> PlaylistGeneration:
        row = PlaylistGeneration(
            id=id or uuid.uuid4(),
            user_id=user_id,
            prompt=prompt,
            title=title,
            description=description,
            playlist_url=playlist_url,
            yandex_kind=yandex_kind,
            profile=profile,
            tracks=tracks,
            pool_stats=pool_stats,
            options=options,
            source_id=source_id,
            latency_ms=latency_ms,
            latency_breakdown=latency_breakdown,
            warnings=warnings,
            warnings_count=warnings_count,
            client_channel=client_channel,
            cover_storage_key=cover_storage_key,
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.commit()
        return row

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PlaylistGeneration]:
        result = await self._db.execute(
            select(PlaylistGeneration)
            .where(PlaylistGeneration.user_id == user_id)
            .order_by(PlaylistGeneration.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self,
        generation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PlaylistGeneration | None:
        result = await self._db.execute(
            select(PlaylistGeneration).where(
                PlaylistGeneration.id == generation_id,
                PlaylistGeneration.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_feedback(
        self,
        generation_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        feedback: int | None,
    ) -> PlaylistGeneration | None:
        row = await self.get_by_id_for_user(generation_id, user_id)
        if row is None:
            return None
        row.feedback = feedback
        row.feedback_at = datetime.now(UTC) if feedback is not None else None
        await self._db.commit()
        await self._db.refresh(row)
        return row
