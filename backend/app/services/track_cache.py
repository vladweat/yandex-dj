"""Redis-кэш метаданных треков (TTL 24h)."""

import json
import logging

import redis.asyncio as redis

from app.core.config import settings
from app.schemas.track import TrackCandidate

logger = logging.getLogger(__name__)

_TRACK_KEY_PREFIX = "track:"
_LYRICS_KEY_PREFIX = "lyrics:"


class TrackCacheService:
    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._client: redis.Redis | None = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_many(self, track_ids: list[str]) -> dict[str, TrackCandidate]:
        if not track_ids:
            return {}

        client = await self._get_client()
        keys = [f"{_TRACK_KEY_PREFIX}{track_id}" for track_id in track_ids]
        try:
            values = await client.mget(keys)
        except redis.RedisError as exc:
            logger.warning("Redis mget failed: %s", exc)
            return {}

        cached: dict[str, TrackCandidate] = {}
        for track_id, raw in zip(track_ids, values, strict=True):
            if not raw:
                continue
            try:
                cached[track_id] = TrackCandidate.model_validate_json(raw)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.debug("Invalid cache entry for %s: %s", track_id, exc)
        return cached

    async def set_many(self, tracks: list[TrackCandidate]) -> None:
        if not tracks:
            return

        client = await self._get_client()
        ttl = settings.track_cache_ttl_sec
        try:
            async with client.pipeline(transaction=False) as pipe:
                for track in tracks:
                    key = f"{_TRACK_KEY_PREFIX}{track.id}"
                    pipe.set(key, track.model_dump_json(), ex=ttl)
                await pipe.execute()
        except redis.RedisError as exc:
            logger.warning("Redis set_many failed: %s", exc)

    async def get_lyrics_presence_many(self, track_ids: list[str]) -> dict[str, bool]:
        if not track_ids:
            return {}

        client = await self._get_client()
        keys = [f"{_LYRICS_KEY_PREFIX}{track_id}" for track_id in track_ids]
        try:
            values = await client.mget(keys)
        except redis.RedisError as exc:
            logger.warning("Redis lyrics mget failed: %s", exc)
            return {}

        cached: dict[str, bool] = {}
        for track_id, raw in zip(track_ids, values, strict=True):
            if raw is None:
                continue
            cached[track_id] = raw == "1"
        return cached

    async def set_lyrics_presence_many(self, presence: dict[str, bool]) -> None:
        if not presence:
            return

        client = await self._get_client()
        ttl = settings.track_cache_ttl_sec
        try:
            async with client.pipeline(transaction=False) as pipe:
                for track_id, has_lyrics in presence.items():
                    key = f"{_LYRICS_KEY_PREFIX}{track_id}"
                    pipe.set(key, "1" if has_lyrics else "0", ex=ttl)
                await pipe.execute()
        except redis.RedisError as exc:
            logger.warning("Redis lyrics set_many failed: %s", exc)
