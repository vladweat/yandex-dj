import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.playlist_generation import PlaylistGeneration


class PlaylistGenerationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

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
    ) -> PlaylistGeneration:
        row = PlaylistGeneration(
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
