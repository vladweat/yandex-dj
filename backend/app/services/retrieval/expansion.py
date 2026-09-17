import logging

from yandex_music import ClientAsync

from app.core.config import settings
from app.schemas.llm import MusicProfile
from app.schemas.track import RETRIEVAL_TIER_ANCHOR, RETRIEVAL_TIER_SIMILAR, TrackCandidate
from app.services.retrieval.discovered import rank_discovered_artists
from app.services.retrieval.gather import artists_for_tops, fetch_artist_tracks
from app.services.retrieval.helpers import gather_tracks
from app.services.yandex_music_service import YandexMusicService
from app.utils.quality import artist_matches_reference, is_spurious_track
from app.utils.tracks import normalize_pool, tracks_to_candidates, with_retrieval_tier

logger = logging.getLogger(__name__)


async def expand_with_anchor_similar(
    yandex: YandexMusicService,
    client: ClientAsync,
    profile: MusicProfile,
    candidates: list[TrackCandidate],
    *,
    seeds_per_artist: int | None = None,
    max_requests: int | None = None,
    used_seed_ids: set[str] | None = None,
) -> list[TrackCandidate]:
    """Similar-треки от хитов якорных артистов — расширяет пул без SEO-поиска."""
    retrieval = settings.retrieval
    per_artist = seeds_per_artist or retrieval.similar_seeds_per_artist
    request_limit = max_requests or retrieval.max_similar_requests
    seen_seeds = used_seed_ids if used_seed_ids is not None else set()

    seed_ids: list[str] = []
    for ref in artists_for_tops(profile):
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
    tasks = [yandex.tracks_similar_list(client, track_id) for track_id in seed_ids[:request_limit]]
    raw_tracks = await gather_tracks(tasks)
    similar = with_retrieval_tier(
        tracks_to_candidates(raw_tracks),
        RETRIEVAL_TIER_SIMILAR,
    )
    merged = normalize_pool(candidates + similar)
    added = len(merged) - len(candidates)
    if added:
        logger.info("Added %d similar tracks from %d anchor seeds", added, len(seed_ids))
    return merged


async def expand_similar_for_artists(
    yandex: YandexMusicService,
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
    tasks = [yandex.tracks_similar_list(client, track_id) for track_id in seed_ids]
    raw_tracks = await gather_tracks(tasks)
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


async def expand_by_artist_names(
    yandex: YandexMusicService,
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

    tasks = [fetch_artist_tracks(yandex, client, name) for name in names]
    raw_tracks = await gather_tracks(tasks)
    tops = with_retrieval_tier(
        tracks_to_candidates(raw_tracks),
        RETRIEVAL_TIER_ANCHOR,
    )
    merged = normalize_pool(candidates + tops)
    added_tops = len(merged) - len(candidates)

    artist_keys = {name.lower() for name in names}
    merged = await expand_similar_for_artists(
        yandex,
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


async def expand_discovered_artists(
    yandex: YandexMusicService,
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
    retrieval = settings.retrieval
    limit = max_artists or retrieval.discovered_artists_limit
    discovered = rank_discovered_artists(
        candidates,
        profile,
        seen_artists=seen_artists,
        max_artists=limit,
    )
    if not discovered:
        return candidates

    for name in discovered:
        seen_artists.add(name.lower().strip())

    return await expand_by_artist_names(
        yandex,
        client,
        profile,
        candidates,
        discovered,
        used_seed_ids=used_seed_ids if used_seed_ids is not None else set(),
        similar_seeds=similar_seeds or retrieval.discovered_similar_seeds,
        log_label="Discovered expand",
    )
