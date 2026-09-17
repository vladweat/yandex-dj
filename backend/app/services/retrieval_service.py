"""Сбор пула кандидатов из каталога Яндекс Музыки."""

import asyncio
import logging
import time
from collections.abc import Awaitable

from yandex_music import ClientAsync, Track

from app.core.config import settings
from app.schemas.llm import MusicProfile
from app.schemas.track import (
    RETRIEVAL_TIER_ANCHOR,
    RETRIEVAL_TIER_SEARCH,
    RETRIEVAL_TIER_SIMILAR,
    TrackCandidate,
)
from app.services.track_cache import TrackCacheService
from app.services.yandex_music_service import YandexMusicService
from app.utils.quality import (
    artist_matches_reference,
    is_genre_suffix_artist,
    is_mood_keyword_artist,
    is_spurious_track,
    looks_like_seo_artist,
    references_in_artists,
)
from app.utils.search_queries import expand_search_queries
from app.utils.tracks import normalize_pool, tracks_to_candidates, with_retrieval_tier

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
        used_seed_ids: set[str] = set()
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

        candidates = await self._expand_with_anchor_similar(
            client,
            profile,
            candidates,
            used_seed_ids=used_seed_ids,
        )

        used_discovered_artists: set[str] = set()
        candidates = await self._expand_discovered_artists(
            client,
            profile,
            candidates,
            seen_artists=used_discovered_artists,
            used_seed_ids=used_seed_ids,
        )
        quality_pass = 0
        while (
            self._clean_count(candidates, profile) < settings.min_clean_candidates
            and quality_pass < 5
        ):
            before_clean = self._clean_count(candidates, profile)
            candidates = await self._expand_with_anchor_similar(
                client,
                profile,
                candidates,
                seeds_per_artist=settings.similar_seeds_per_artist + quality_pass,
                max_requests=settings.max_similar_requests,
                used_seed_ids=used_seed_ids,
            )
            candidates = await self._expand_discovered_artists(
                client,
                profile,
                candidates,
                seen_artists=used_discovered_artists,
                used_seed_ids=used_seed_ids,
                max_artists=settings.discovered_artists_limit + quality_pass * 2,
                similar_seeds=settings.discovered_similar_seeds,
            )
            extra_queries = expand_search_queries(
                profile,
                used=used_queries,
                pass_num=expand_pass + quality_pass,
            )
            if extra_queries:
                extra = await self._gather_search_queries(client, extra_queries)
                extra = await self._enrich_with_cache(client, extra)
                candidates = normalize_pool(candidates + extra)
            if self._clean_count(candidates, profile) <= before_clean:
                quality_pass += 1
                if quality_pass >= 5:
                    break
                continue
            quality_pass += 1

        candidates = candidates[: settings.max_candidates]
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        clean = self._clean_count(candidates, profile)
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

        yandex_client = client or await self._yandex.init_client(access_token)
        seed_ids = used_seed_ids if used_seed_ids is not None else set()
        merged = await self._expand_by_artist_names(
            yandex_client,
            profile,
            candidates,
            artist_names,
            used_seed_ids=seed_ids,
            similar_seeds=similar_seeds or settings.feedback_similar_seeds,
            log_label="Feedback expand",
        )
        return await self._enrich_with_cache(yandex_client, merged)

    @staticmethod
    def _clean_count(candidates: list[TrackCandidate], profile: MusicProfile) -> int:
        return sum(1 for track in candidates if not is_spurious_track(track, profile))

    @staticmethod
    def _rank_discovered_artists(
        candidates: list[TrackCandidate],
        profile: MusicProfile,
        *,
        seen_artists: set[str],
        max_artists: int,
    ) -> list[str]:
        """Частые clean не-якорные артисты — лучшие seeds для ширины пула."""
        counts: dict[str, int] = {}
        display: dict[str, str] = {}
        for track in candidates:
            if is_spurious_track(track, profile):
                continue
            for name in track.artists:
                key = name.lower().strip()
                if not key or key in seen_artists:
                    continue
                if any(artist_matches_reference(name, ref) for ref in profile.reference_artists):
                    continue
                if is_mood_keyword_artist(name) or is_genre_suffix_artist(name):
                    continue
                if looks_like_seo_artist(name):
                    continue
                counts[key] = counts.get(key, 0) + 1
                display.setdefault(key, name.strip())

        ranked_keys = sorted(counts, key=lambda key: (-counts[key], key))
        return [display[key] for key in ranked_keys[:max_artists]]

    async def _expand_with_anchor_similar(
        self,
        client: ClientAsync,
        profile: MusicProfile,
        candidates: list[TrackCandidate],
        *,
        seeds_per_artist: int | None = None,
        max_requests: int | None = None,
        used_seed_ids: set[str] | None = None,
    ) -> list[TrackCandidate]:
        """Similar-треки от хитов якорных артистов — расширяет пул без SEO-поиска."""
        per_artist = seeds_per_artist or settings.similar_seeds_per_artist
        request_limit = max_requests or settings.max_similar_requests
        seen_seeds = used_seed_ids if used_seed_ids is not None else set()

        seed_ids: list[str] = []
        for ref in self._artists_for_tops(profile):
            added = 0
            for track in candidates:
                if track.id in seen_seeds or track.id in seed_ids:
                    continue
                if any(artist_matches_reference(artist, ref) for artist in track.artists):
                    seed_ids.append(track.id)
                    added += 1
                if added >= per_artist:
                    break

        if not seed_ids:
            return candidates

        seen_seeds.update(seed_ids)
        tasks = [
            self._yandex.tracks_similar_list(client, track_id)
            for track_id in seed_ids[:request_limit]
        ]
        raw_tracks = await _gather_tracks(tasks)
        similar = with_retrieval_tier(
            tracks_to_candidates(raw_tracks),
            RETRIEVAL_TIER_SIMILAR,
        )
        merged = normalize_pool(candidates + similar)
        added = len(merged) - len(candidates)
        if added:
            logger.info("Added %d similar tracks from %d anchor seeds", added, len(seed_ids))
        return merged

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
        """Топы + similar по частым не-якорным артистам — ширина clean-пула."""
        limit = max_artists or settings.discovered_artists_limit
        discovered = self._rank_discovered_artists(
            candidates,
            profile,
            seen_artists=seen_artists,
            max_artists=limit,
        )
        if not discovered:
            return candidates

        for name in discovered:
            seen_artists.add(name.lower().strip())

        return await self._expand_by_artist_names(
            client,
            profile,
            candidates,
            discovered,
            used_seed_ids=used_seed_ids if used_seed_ids is not None else set(),
            similar_seeds=similar_seeds or settings.discovered_similar_seeds,
            log_label="Discovered expand",
        )

    async def _expand_by_artist_names(
        self,
        client: ClientAsync,
        profile: MusicProfile,
        candidates: list[TrackCandidate],
        artist_names: list[str],
        *,
        used_seed_ids: set[str],
        similar_seeds: int,
        log_label: str,
    ) -> list[TrackCandidate]:
        """Общий путь: топы артистов → similar от их треков → merge в пул."""
        names = [name.strip() for name in artist_names if name.strip()]
        if not names:
            return candidates

        tasks = [self._fetch_artist_tracks(client, name) for name in names]
        raw_tracks = await _gather_tracks(tasks)
        tops = with_retrieval_tier(
            tracks_to_candidates(raw_tracks),
            RETRIEVAL_TIER_ANCHOR,
        )
        merged = normalize_pool(candidates + tops)
        added_tops = len(merged) - len(candidates)

        artist_keys = {name.lower() for name in names}
        merged = await self._expand_similar_for_artists(
            client,
            profile,
            merged,
            artist_keys=artist_keys,
            used_seed_ids=used_seed_ids,
            similar_seeds=similar_seeds,
        )
        added = len(merged) - len(candidates)
        if added:
            logger.info(
                "%s: +%d tracks (%d tops) from %d artists (%s)",
                log_label,
                added,
                added_tops,
                len(names),
                ", ".join(names[:3]),
            )
        return merged

    async def _expand_similar_for_artists(
        self,
        client: ClientAsync,
        profile: MusicProfile,
        candidates: list[TrackCandidate],
        *,
        artist_keys: set[str],
        used_seed_ids: set[str],
        similar_seeds: int,
    ) -> list[TrackCandidate]:
        """Similar от треков указанных артистов — приносит новых исполнителей в пул."""
        if similar_seeds <= 0 or not artist_keys:
            return candidates

        seed_ids: list[str] = []
        for track in candidates:
            if track.id in used_seed_ids or track.id in seed_ids:
                continue
            if is_spurious_track(track, profile):
                continue
            if not any(name.lower().strip() in artist_keys for name in track.artists):
                continue
            seed_ids.append(track.id)
            if len(seed_ids) >= similar_seeds:
                break

        if not seed_ids:
            return candidates

        used_seed_ids.update(seed_ids)
        tasks = [self._yandex.tracks_similar_list(client, track_id) for track_id in seed_ids]
        raw_tracks = await _gather_tracks(tasks)
        similar = with_retrieval_tier(
            tracks_to_candidates(raw_tracks),
            RETRIEVAL_TIER_SIMILAR,
        )
        merged = normalize_pool(candidates + similar)
        added = len(merged) - len(candidates)
        if added:
            logger.info(
                "Added %d similar tracks from %d discovered seeds",
                added,
                len(seed_ids),
            )
        return merged

    async def _gather_from_profile(
        self,
        client: ClientAsync,
        profile: MusicProfile,
        reference_track_id: str | int | None,
    ) -> list[TrackCandidate]:
        search_tasks: list[Awaitable[list[Track]]] = [
            self._yandex.search_tracks(client, query) for query in profile.search_queries
        ]
        anchor_tasks: list[Awaitable[list[Track]]] = [
            self._fetch_artist_tracks(client, artist_name)
            for artist_name in self._artists_for_tops(profile)
        ]
        similar_tasks: list[Awaitable[list[Track]]] = []
        if reference_track_id is not None:
            similar_tasks.append(
                self._yandex.tracks_similar_list(client, reference_track_id)
            )

        search_raw = await _gather_tracks(search_tasks)
        anchor_raw = await _gather_tracks(anchor_tasks)
        similar_raw = await _gather_tracks(similar_tasks)
        search_candidates = with_retrieval_tier(
            tracks_to_candidates(search_raw),
            RETRIEVAL_TIER_SEARCH,
        )
        anchor_candidates = with_retrieval_tier(
            tracks_to_candidates(anchor_raw),
            RETRIEVAL_TIER_ANCHOR,
        )
        similar_candidates = with_retrieval_tier(
            tracks_to_candidates(similar_raw),
            RETRIEVAL_TIER_SIMILAR,
        )
        return normalize_pool(search_candidates + anchor_candidates + similar_candidates)

    @staticmethod
    def _artists_for_tops(profile: MusicProfile) -> list[str]:
        """Hard-якоря первыми, затем soft — не больше reference_artists_tops_limit."""
        limit = max(1, settings.reference_artists_tops_limit)
        hard = [name.strip() for name in profile.hard_reference_artists if name.strip()]
        refs = [name.strip() for name in profile.reference_artists if name.strip()]
        ordered: list[str] = []
        seen: set[str] = set()
        for name in hard + refs:
            key = name.lower()
            if not name or key in seen:
                continue
            seen.add(key)
            ordered.append(name)
            if len(ordered) >= limit:
                break
        return ordered

    async def _gather_search_queries(
        self,
        client: ClientAsync,
        queries: list[str],
    ) -> list[TrackCandidate]:
        tasks = [self._yandex.search_tracks(client, query) for query in queries]
        raw_tracks = await _gather_tracks(tasks)
        return normalize_pool(
            with_retrieval_tier(
                tracks_to_candidates(raw_tracks),
                RETRIEVAL_TIER_SEARCH,
            )
        )

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


def non_anchor_artists_from_ranked(
    ranked: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
    *,
    limit: int,
    scan_top: int = 40,
) -> list[str]:
    """Лучшие не-якорные артисты по embedding-рангу — для feedback expand."""
    found: list[str] = []
    seen: set[str] = set()
    for track, _score in ranked[:scan_top]:
        if references_in_artists(track, profile):
            continue
        if is_spurious_track(track, profile):
            continue
        for name in track.artists:
            key = name.lower().strip()
            if not key or key in seen:
                continue
            if looks_like_seo_artist(name):
                continue
            if is_mood_keyword_artist(name) or is_genre_suffix_artist(name):
                continue
            seen.add(key)
            found.append(name.strip())
            if len(found) >= limit:
                return found
    return found


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
