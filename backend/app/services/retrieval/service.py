"""Сбор пула кандидатов из каталога Яндекс Музыки."""

import logging
import time

from yandex_music import ClientAsync

from app.core.config import settings
from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.services.retrieval.discovered import rank_discovered_artists
from app.services.retrieval.helpers import clean_count
from app.services.track_cache import TrackCacheService
from app.services.yandex_music_service import YandexMusicService
from app.utils.search_queries import expand_search_queries
from app.utils.tracks import normalize_pool

from . import expansion, gather

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
        retrieval = settings.retrieval
        started = time.perf_counter()
        client = await self._yandex.init_client(access_token)

        used_queries = {query.lower() for query in profile.search_queries}
        used_seed_ids: set[str] = set()
        candidates = await gather.gather_from_profile(
            self._yandex,
            client,
            profile,
            reference_track_id,
        )
        candidates = await gather.enrich_with_cache(
            self._yandex,
            self._cache,
            client,
            candidates,
        )

        expand_pass = 0
        while (
            len(candidates) < retrieval.target_candidates_pool
            and expand_pass < retrieval.retrieval_expand_passes
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
                retrieval.target_candidates_pool,
                expand_pass + 1,
                len(extra_queries),
            )
            extra = await gather.gather_search_queries(self._yandex, client, extra_queries)
            extra = await gather.enrich_with_cache(
                self._yandex,
                self._cache,
                client,
                extra,
            )
            candidates = normalize_pool(candidates + extra)
            expand_pass += 1

        candidates = await expansion.expand_with_anchor_similar(
            self._yandex,
            client,
            profile,
            candidates,
            used_seed_ids=used_seed_ids,
        )

        used_discovered_artists: set[str] = set()
        candidates = await expansion.expand_discovered_artists(
            self._yandex,
            client,
            profile,
            candidates,
            seen_artists=used_discovered_artists,
            used_seed_ids=used_seed_ids,
        )
        quality_pass = 0
        while (
            clean_count(candidates, profile) < retrieval.min_clean_candidates and quality_pass < 5
        ):
            before_clean = clean_count(candidates, profile)
            candidates = await expansion.expand_with_anchor_similar(
                self._yandex,
                client,
                profile,
                candidates,
                seeds_per_artist=retrieval.similar_seeds_per_artist + quality_pass,
                max_requests=retrieval.max_similar_requests,
                used_seed_ids=used_seed_ids,
            )
            candidates = await expansion.expand_discovered_artists(
                self._yandex,
                client,
                profile,
                candidates,
                seen_artists=used_discovered_artists,
                used_seed_ids=used_seed_ids,
                max_artists=retrieval.discovered_artists_limit + quality_pass * 2,
                similar_seeds=retrieval.discovered_similar_seeds,
            )
            extra_queries = expand_search_queries(
                profile,
                used=used_queries,
                pass_num=expand_pass + quality_pass,
            )
            if extra_queries:
                extra = await gather.gather_search_queries(self._yandex, client, extra_queries)
                extra = await gather.enrich_with_cache(
                    self._yandex,
                    self._cache,
                    client,
                    extra,
                )
                candidates = normalize_pool(candidates + extra)
            if clean_count(candidates, profile) <= before_clean:
                quality_pass += 1
                if quality_pass >= 5:
                    break
                continue
            quality_pass += 1

        candidates = candidates[: retrieval.max_candidates]
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        clean = clean_count(candidates, profile)
        logger.info(
            "Retrieved %d candidates (%d clean) in %d ms",
            len(candidates),
            clean,
            elapsed_ms,
        )
        return candidates

    async def expand_from_artists(
        self,
        profile: MusicProfile,
        access_token: str,
        candidates: list[TrackCandidate],
        artist_names: list[str],
        *,
        used_seed_ids: set[str] | None = None,
        similar_seeds: int | None = None,
        client: ClientAsync | None = None,
    ) -> list[TrackCandidate]:
        """Добор топов + similar по списку артистов (scoring feedback)."""
        if not artist_names:
            return candidates

        retrieval = settings.retrieval
        yandex_client = client or await self._yandex.init_client(access_token)
        seed_ids = used_seed_ids if used_seed_ids is not None else set()
        merged = await expansion.expand_by_artist_names(
            self._yandex,
            yandex_client,
            profile,
            candidates,
            artist_names,
            used_seed_ids=seed_ids,
            similar_seeds=similar_seeds or retrieval.feedback_similar_seeds,
            log_label="Feedback expand",
        )
        return await gather.enrich_with_cache(
            self._yandex,
            self._cache,
            yandex_client,
            merged,
        )

    @staticmethod
    def _rank_discovered_artists(
        candidates: list[TrackCandidate],
        profile: MusicProfile,
        *,
        seen_artists: set[str],
        max_artists: int,
    ) -> list[str]:
        return rank_discovered_artists(
            candidates,
            profile,
            seen_artists=seen_artists,
            max_artists=max_artists,
        )

    async def _expand_discovered_artists(
        self,
        client: ClientAsync,
        profile: MusicProfile,
        candidates: list[TrackCandidate],
        *,
        seen_artists: set[str],
        used_seed_ids: set[str] | None = None,
        max_artists: int | None = None,
        similar_seeds: int | None = None,
    ) -> list[TrackCandidate]:
        return await expansion.expand_discovered_artists(
            self._yandex,
            client,
            profile,
            candidates,
            seen_artists=seen_artists,
            used_seed_ids=used_seed_ids,
            max_artists=max_artists,
            similar_seeds=similar_seeds,
        )
