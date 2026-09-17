import logging
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
from app.services.retrieval.helpers import gather_tracks
from app.services.track_cache import TrackCacheService
from app.services.yandex_music_service import YandexMusicService
from app.utils.tracks import normalize_pool, tracks_to_candidates, with_retrieval_tier

logger = logging.getLogger(__name__)


def artists_for_tops(profile: MusicProfile) -> list[str]:
    """Hard-якоря первыми, затем soft — не больше reference_artists_tops_limit."""
    limit = max(1, settings.retrieval.reference_artists_tops_limit)
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


async def fetch_artist_tracks(
    yandex: YandexMusicService,
    client: ClientAsync,
    artist_name: str,
) -> list[Track]:
    artist_id = await yandex.search_artist_id(client, artist_name)
    if artist_id is None:
        logger.debug("Artist not found: %s", artist_name)
        return []
    return await yandex.artists_top_tracks(client, artist_id)


async def gather_from_profile(
    yandex: YandexMusicService,
    client: ClientAsync,
    profile: MusicProfile,
    reference_track_id: str | int | None,
) -> list[TrackCandidate]:
    search_tasks: list[Awaitable[list[Track]]] = [
        yandex.search_tracks(client, query) for query in profile.search_queries
    ]
    anchor_tasks: list[Awaitable[list[Track]]] = [
        fetch_artist_tracks(yandex, client, artist_name)
        for artist_name in artists_for_tops(profile)
    ]
    similar_tasks: list[Awaitable[list[Track]]] = []
    if reference_track_id is not None:
        similar_tasks.append(yandex.tracks_similar_list(client, reference_track_id))

    search_raw = await gather_tracks(search_tasks)
    anchor_raw = await gather_tracks(anchor_tasks)
    similar_raw = await gather_tracks(similar_tasks)
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


async def gather_search_queries(
    yandex: YandexMusicService,
    client: ClientAsync,
    queries: list[str],
) -> list[TrackCandidate]:
    tasks = [yandex.search_tracks(client, query) for query in queries]
    raw_tracks = await gather_tracks(tasks)
    return normalize_pool(
        with_retrieval_tier(
            tracks_to_candidates(raw_tracks),
            RETRIEVAL_TIER_SEARCH,
        )
    )


async def enrich_with_cache(
    yandex: YandexMusicService,
    cache: TrackCacheService,
    client: ClientAsync,
    candidates: list[TrackCandidate],
) -> list[TrackCandidate]:
    if not candidates:
        return []

    unique_ids = list(dict.fromkeys(track.id for track in candidates))
    cached = await cache.get_many(unique_ids)
    missing_ids = [track_id for track_id in unique_ids if track_id not in cached]

    if missing_ids:
        fetched = await yandex.fetch_tracks(client, missing_ids)
        fresh = tracks_to_candidates(fetched)
        if fresh:
            await cache.set_many(fresh)
            for track in fresh:
                cached[track.id] = track

    enriched: list[TrackCandidate] = []
    for track in candidates:
        enriched.append(cached.get(track.id, track))
    return normalize_pool(enriched)
