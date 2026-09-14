"""Сбор пула кандидатов из каталога Яндекс Музыки."""

import asyncio
import logging
import time
from collections.abc import Awaitable

from yandex_music import ClientAsync, Track

from app.core.config import settings
from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.services.track_cache import TrackCacheService
from app.services.yandex_music_service import YandexMusicService
from app.utils.search_queries import expand_search_queries
from app.utils.tracks import normalize_pool, tracks_to_candidates

logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(
        self,
        yandex: YandexMusicService,
        cache: TrackCacheService | None = None,
    ) -> None:
        self._yandex = yandex
        self._cache = cache or TrackCacheService()

    async def collect_candidates(
        self,
        profile: MusicProfile,
        access_token: str,
        *,
        reference_track_id: str | int | None = None,
    ) -> list[TrackCandidate]:
        started = time.perf_counter()
        client = await self._yandex.init_client(access_token)

        used_queries = {query.lower() for query in profile.search_queries}
        candidates = await self._gather_from_profile(client, profile, reference_track_id)
        candidates = await self._enrich_with_cache(client, candidates)

        expand_pass = 0
        while (
            len(candidates) < settings.target_candidates_pool
            and expand_pass < settings.retrieval_expand_passes
        ):
            extra_queries = expand_search_queries(
                profile,
                used=used_queries,
                pass_num=expand_pass,
            )
            if not extra_queries:
                break

            logger.info(
                "Pool %d < %d, expand pass %d with %d queries",
                len(candidates),
                settings.target_candidates_pool,
                expand_pass + 1,
                len(extra_queries),
            )
            extra = await self._gather_search_queries(client, extra_queries)
            extra = await self._enrich_with_cache(client, extra)
            candidates = normalize_pool(candidates + extra)
            expand_pass += 1

        candidates = candidates[: settings.max_candidates]
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info("Retrieved %d candidates in %d ms", len(candidates), elapsed_ms)
        return candidates

    async def _gather_from_profile(
        self,
        client: ClientAsync,
        profile: MusicProfile,
        reference_track_id: str | int | None,
    ) -> list[TrackCandidate]:
        tasks: list[Awaitable[list[Track]]] = []

        for query in profile.search_queries:
            tasks.append(self._yandex.search_tracks(client, query))

        for artist_name in profile.reference_artists:
            tasks.append(self._fetch_artist_tracks(client, artist_name))

        if reference_track_id is not None:
            tasks.append(self._yandex.tracks_similar_list(client, reference_track_id))

        raw_tracks = await _gather_tracks(tasks)
        return normalize_pool(tracks_to_candidates(raw_tracks))

    async def _gather_search_queries(
        self,
        client: ClientAsync,
        queries: list[str],
    ) -> list[TrackCandidate]:
        tasks = [self._yandex.search_tracks(client, query) for query in queries]
        raw_tracks = await _gather_tracks(tasks)
        return normalize_pool(tracks_to_candidates(raw_tracks))

    async def _fetch_artist_tracks(self, client: ClientAsync, artist_name: str) -> list[Track]:
        artist_id = await self._yandex.search_artist_id(client, artist_name)
        if artist_id is None:
            logger.debug("Artist not found: %s", artist_name)
            return []
        return await self._yandex.artists_top_tracks(client, artist_id)

    async def _enrich_with_cache(
        self,
        client: ClientAsync,
        candidates: list[TrackCandidate],
    ) -> list[TrackCandidate]:
        if not candidates:
            return []

        unique_ids = list(dict.fromkeys(track.id for track in candidates))
        cached = await self._cache.get_many(unique_ids)
        missing_ids = [track_id for track_id in unique_ids if track_id not in cached]

        if missing_ids:
            fetched = await self._yandex.fetch_tracks(client, missing_ids)
            fresh = tracks_to_candidates(fetched)
            if fresh:
                await self._cache.set_many(fresh)
                for track in fresh:
                    cached[track.id] = track

        enriched: list[TrackCandidate] = []
        for track in candidates:
            enriched.append(cached.get(track.id, track))
        return normalize_pool(enriched)


async def _gather_tracks(tasks: list[Awaitable[list[Track]]]) -> list[Track]:
    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    tracks: list[Track] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Retrieval task failed: %s", result)
            continue
        tracks.extend(result)
    return tracks
