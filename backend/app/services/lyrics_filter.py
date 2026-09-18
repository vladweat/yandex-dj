"""Soft-фильтр «без слов» через tracks_lyrics (только instrumental_only)."""

from __future__ import annotations

import asyncio
import logging

from yandex_music import ClientAsync

from app.core.config import settings
from app.schemas.llm import MusicProfile
from app.schemas.scoring import ScoredTrack
from app.schemas.track import TrackCandidate
from app.services.track_cache import TrackCacheService
from app.services.yandex_music_service import YandexMusicService

logger = logging.getLogger(__name__)


def instrumental_lyrics_filter_needed(profile: MusicProfile) -> bool:
    return profile.vocal_type == "instrumental_only"


async def resolve_synced_lyrics_presence(
    yandex: YandexMusicService,
    cache: TrackCacheService,
    client: ClientAsync,
    track_ids: list[str],
) -> dict[str, bool]:
    """track_id → True если в Яндексе есть synced lyrics."""
    unique = list(dict.fromkeys(track_ids))
    if not unique:
        return {}

    cached = await cache.get_lyrics_presence_many(unique)
    missing = [track_id for track_id in unique if track_id not in cached]
    if not missing:
        return cached

    fetched: dict[str, bool] = {}

    async def _check(track_id: str) -> None:
        try:
            fetched[track_id] = await yandex.track_has_synced_lyrics(client, track_id)
        except Exception as exc:
            logger.debug("tracks_lyrics failed for %s: %s", track_id, exc)

    await asyncio.gather(*(_check(track_id) for track_id in missing))
    if fetched:
        await cache.set_lyrics_presence_many(fetched)
    return {**cached, **fetched}


def _lyrics_check_limit(profile: MusicProfile, ranked_len: int) -> int:
    return min(
        settings.lyrics_check_limit,
        max(profile.target_track_count * 3, 40),
        ranked_len,
    )


def apply_vocal_score_penalty(
    ranked: list[tuple[TrackCandidate, float]],
    has_lyrics: dict[str, bool],
) -> list[tuple[TrackCandidate, float]]:
    penalty = settings.lyrics_vocal_score_penalty
    adjusted: list[tuple[TrackCandidate, float]] = []
    for track, score in ranked:
        if has_lyrics.get(track.id):
            score -= penalty
        adjusted.append((track, score))
    adjusted.sort(key=lambda item: item[1], reverse=True)
    return adjusted


def swap_vocal_tracks_in_selection(
    selected: list[ScoredTrack],
    ranked: list[tuple[TrackCandidate, float]],
    has_lyrics: dict[str, bool],
) -> tuple[list[ScoredTrack], int]:
    """
    Меняет треки с synced lyrics на лучших кандидатов без текста из ranked pool.
    Возвращает (новый список, число замен).
    """
    if not has_lyrics:
        return selected, 0

    selected_ids = {track.id for track in selected}
    alternates = [
        track
        for track, _score in ranked
        if track.id not in selected_ids and not has_lyrics.get(track.id, False)
    ]
    if not alternates:
        return selected, 0

    result = list(selected)
    alt_index = 0
    swaps = 0
    for index, track in enumerate(result):
        if not has_lyrics.get(track.id):
            continue
        while alt_index < len(alternates):
            replacement = alternates[alt_index]
            alt_index += 1
            if replacement.id in selected_ids:
                continue
            result[index] = ScoredTrack.from_candidate(replacement, track.score)
            selected_ids.add(replacement.id)
            swaps += 1
            break
    return result, swaps


async def prepare_instrumental_ranked_pool(
    *,
    yandex: YandexMusicService,
    cache: TrackCacheService,
    client: ClientAsync,
    profile: MusicProfile,
    ranked: list[tuple[TrackCandidate, float]],
) -> tuple[list[tuple[TrackCandidate, float]], dict[str, bool], list[str]]:
    if not instrumental_lyrics_filter_needed(profile):
        return ranked, {}, []

    limit = _lyrics_check_limit(profile, len(ranked))
    track_ids = [track.id for track, _ in ranked[:limit]]
    has_lyrics = await resolve_synced_lyrics_presence(yandex, cache, client, track_ids)
    if not has_lyrics:
        return ranked, {}, [
            "Фильтр «без слов»: не удалось проверить тексты — оставили семантический отбор."
        ]

    penalized = apply_vocal_score_penalty(ranked, has_lyrics)
    return penalized, has_lyrics, []


def refine_instrumental_selection(
    selected: list[ScoredTrack],
    ranked: list[tuple[TrackCandidate, float]],
    has_lyrics: dict[str, bool],
) -> tuple[list[ScoredTrack], list[str]]:
    if not has_lyrics:
        return selected, []

    refined, swaps = swap_vocal_tracks_in_selection(selected, ranked, has_lyrics)
    warnings: list[str] = []
    vocal_in_playlist = sum(1 for track in refined if has_lyrics.get(track.id))
    if swaps:
        warnings.append(f"Фильтр «без слов»: заменено {swaps} треков с текстом в каталоге.")
    if vocal_in_playlist:
        warnings.append(
            f"Фильтр «без слов»: в плейлисте осталось {vocal_in_playlist} треков "
            "со synced lyrics (мягкий режим)."
        )
    return refined, warnings


async def instrumental_lyrics_pass(
    *,
    yandex: YandexMusicService,
    cache: TrackCacheService,
    client: ClientAsync,
    profile: MusicProfile,
    ranked: list[tuple[TrackCandidate, float]],
    selected: list[ScoredTrack],
) -> tuple[list[tuple[TrackCandidate, float]], list[ScoredTrack], list[str]]:
    ranked, has_lyrics, warnings = await prepare_instrumental_ranked_pool(
        yandex=yandex,
        cache=cache,
        client=client,
        profile=profile,
        ranked=ranked,
    )
    if not has_lyrics:
        return ranked, selected, warnings

    selected, refine_warnings = refine_instrumental_selection(selected, ranked, has_lyrics)
    warnings.extend(refine_warnings)
    return ranked, selected, warnings
