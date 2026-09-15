"""Оркестрация пайплайна: LLM → retrieval → scoring → export → persist."""

from __future__ import annotations

import logging
import re
import time
import uuid

from yandex_music import ClientAsync

from app.core.config import settings
from app.core.exceptions import (
    ExportError,
    LLMError,
    NotFoundError,
    RetrievalError,
    ScoringError,
    YandexMusicError,
)
from app.db.models.playlist_generation import PlaylistGeneration
from app.repositories.playlist_generation_repository import PlaylistGenerationRepository
from app.schemas.llm import MusicProfile
from app.schemas.playlist import (
    DiversityMode,
    PlaylistGenerateResponse,
    PlaylistHistoryItem,
    PlaylistHistoryResponse,
    PlaylistPoolStats,
    PlaylistTrackResponse,
)
from app.schemas.scoring import ScoredTrack
from app.schemas.track import TrackCandidate
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService, non_anchor_artists_from_ranked
from app.services.scoring_service import ScoringService
from app.services.yandex_music_service import YandexMusicService
from app.utils.quality import artist_matches_reference, artist_tokens, is_spurious_track

logger = logging.getLogger(__name__)

_KIND_FROM_URL = re.compile(r"/playlists/(\d+)/?$")


def build_playlist_description(profile: MusicProfile, prompt: str) -> str:
    description = profile.playlist_description.strip()
    user_prompt = prompt.strip()
    if user_prompt and user_prompt.lower() not in description.lower():
        return f"{description}\n\nПромпт: {user_prompt}"
    return description


def _track_response(track: ScoredTrack) -> PlaylistTrackResponse:
    return PlaylistTrackResponse(
        id=track.id,
        title=track.title,
        artist=", ".join(track.artists),
        duration_ms=track.duration_ms,
        similarity_score=track.score,
    )


def _normalize_excludes(exclude_artists: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for name in exclude_artists:
        cleaned = name.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def apply_exclude_artists(profile: MusicProfile, exclude_artists: list[str]) -> MusicProfile:
    excludes = _normalize_excludes(exclude_artists)
    if not excludes:
        return profile
    remaining = [
        artist
        for artist in profile.reference_artists
        if not any(artist_matches_reference(artist, excluded) for excluded in excludes)
    ]
    # MusicProfile требует ≥4 якоря; при сильном exclude якоря не трогаем.
    if len(remaining) < 4:
        return profile
    return profile.model_copy(update={"reference_artists": remaining})


def filter_excluded_candidates(
    candidates: list[TrackCandidate],
    exclude_artists: list[str],
) -> list[TrackCandidate]:
    excludes = _normalize_excludes(exclude_artists)
    if not excludes:
        return candidates
    kept: list[TrackCandidate] = []
    for track in candidates:
        tokens = artist_tokens(track)
        if any(
            artist_matches_reference(token, excluded)
            for token in tokens
            for excluded in excludes
        ):
            continue
        kept.append(track)
    return kept


def filter_excluded_scored(
    selected: list[ScoredTrack],
    exclude_artists: list[str],
) -> list[ScoredTrack]:
    excludes = _normalize_excludes(exclude_artists)
    if not excludes:
        return selected
    kept: list[ScoredTrack] = []
    for track in selected:
        if any(
            artist_matches_reference(artist, excluded)
            for artist in track.artists
            for excluded in excludes
        ):
            continue
        kept.append(track)
    return kept


def yandex_kind_from_url(playlist_url: str) -> str | None:
    match = _KIND_FROM_URL.search(playlist_url)
    return match.group(1) if match else None


def generation_to_response(row: PlaylistGeneration) -> PlaylistGenerateResponse:
    pool_stats = None
    if row.pool_stats is not None:
        pool_stats = PlaylistPoolStats.model_validate(row.pool_stats)
    return PlaylistGenerateResponse(
        id=row.id,
        prompt=row.prompt,
        title=row.title,
        description=row.description,
        playlist_url=row.playlist_url,
        tracks=[PlaylistTrackResponse.model_validate(track) for track in row.tracks],
        pool_stats=pool_stats,
        profile=MusicProfile.model_validate(row.profile),
    )


class PlaylistService:
    def __init__(
        self,
        llm: LLMService,
        retrieval: RetrievalService,
        scoring: ScoringService,
        yandex: YandexMusicService,
        repo: PlaylistGenerationRepository,
    ) -> None:
        self._llm = llm
        self._retrieval = retrieval
        self._scoring = scoring
        self._yandex = yandex
        self._repo = repo

    async def generate(
        self,
        *,
        prompt: str,
        track_count: int,
        instrumental_only: bool,
        access_token: str,
        login: str,
        user_id: uuid.UUID,
        exclude_artists: list[str] | None = None,
        diversity: DiversityMode = "normal",
        source_id: uuid.UUID | None = None,
    ) -> PlaylistGenerateResponse:
        excludes = _normalize_excludes(exclude_artists or [])
        pipeline_started = time.perf_counter()

        llm_started = time.perf_counter()
        if source_id is not None:
            source = await self._repo.get_by_id_for_user(source_id, user_id)
            if source is None:
                raise NotFoundError("Source generation not found")
            profile = MusicProfile.model_validate(source.profile)
            profile = profile.model_copy(update={"target_track_count": track_count})
            if instrumental_only:
                profile = profile.model_copy(update={"vocal_type": "instrumental_only"})
            llm_ms = 0
        else:
            try:
                profile = await self._llm.parse_prompt(
                    prompt,
                    track_count=track_count,
                    instrumental_only=instrumental_only,
                )
            except LLMError:
                raise
            llm_ms = int((time.perf_counter() - llm_started) * 1000)

        profile = apply_exclude_artists(profile, excludes)

        retrieval_started = time.perf_counter()
        try:
            candidates = await self._retrieval.collect_candidates(profile, access_token)
        except YandexMusicError:
            raise
        except Exception as exc:
            raise RetrievalError(f"Retrieval failed: {exc}") from exc
        retrieval_ms = int((time.perf_counter() - retrieval_started) * 1000)

        candidates = filter_excluded_candidates(candidates, excludes)
        if not candidates:
            raise RetrievalError("No candidates found for the prompt")

        scoring_started = time.perf_counter()
        try:
            ranked_pool, method = await self._scoring.rank_pool(
                profile,
                candidates,
                user_prompt=prompt,
            )
            selected = self._scoring.select(ranked_pool, profile, diversity=diversity)
            selected = filter_excluded_scored(selected, excludes)

            if len(selected) < profile.target_track_count:
                feedback_artists = non_anchor_artists_from_ranked(
                    ranked_pool,
                    profile,
                    limit=settings.feedback_artists_limit,
                )
                feedback_artists = [
                    artist
                    for artist in feedback_artists
                    if not any(
                        artist_matches_reference(artist, excluded) for excluded in excludes
                    )
                ]
                if feedback_artists:
                    before = len(candidates)
                    candidates = await self._retrieval.expand_from_artists(
                        profile,
                        access_token,
                        candidates,
                        feedback_artists,
                        similar_seeds=settings.feedback_similar_seeds,
                    )
                    candidates = filter_excluded_candidates(candidates, excludes)
                    if len(candidates) > before:
                        ranked_pool, method = await self._scoring.rank_pool(
                            profile,
                            candidates,
                            user_prompt=prompt,
                        )
                        selected = self._scoring.select(
                            ranked_pool, profile, diversity=diversity
                        )
                        selected = filter_excluded_scored(selected, excludes)
        except Exception as exc:
            raise ScoringError(f"Scoring failed: {exc}") from exc
        scoring_ms = int((time.perf_counter() - scoring_started) * 1000)

        if not selected:
            raise ScoringError("Scoring returned no tracks")

        clean_count = sum(1 for track in candidates if not is_spurious_track(track, profile))
        pool_stats = PlaylistPoolStats(
            raw=len(candidates),
            clean=clean_count,
            selected=len(selected),
        )

        export_started = time.perf_counter()
        client = await self._yandex.init_client(access_token)
        description = build_playlist_description(profile, prompt)
        try:
            playlist_url = await self._export(client, profile, selected, description, login)
        except YandexMusicError as exc:
            raise ExportError(str(exc)) from exc
        export_ms = int((time.perf_counter() - export_started) * 1000)

        tracks = [_track_response(track) for track in selected]
        options = {
            "track_count": track_count,
            "instrumental_only": instrumental_only,
            "exclude_artists": excludes,
            "diversity": diversity,
        }
        row = await self._repo.create(
            user_id=user_id,
            prompt=prompt,
            title=profile.playlist_title,
            description=description,
            playlist_url=playlist_url,
            yandex_kind=yandex_kind_from_url(playlist_url),
            profile=profile.model_dump(),
            tracks=[track.model_dump() for track in tracks],
            pool_stats=pool_stats.model_dump(),
            options=options,
            source_id=source_id,
        )

        total_ms = int((time.perf_counter() - pipeline_started) * 1000)
        logger.info(
            "Playlist pipeline: llm=%dms retrieval=%dms scoring=%dms export=%dms "
            "total=%dms tracks=%d method=%s raw=%d clean=%d id=%s",
            llm_ms,
            retrieval_ms,
            scoring_ms,
            export_ms,
            total_ms,
            len(selected),
            method,
            pool_stats.raw,
            pool_stats.clean,
            row.id,
        )

        return PlaylistGenerateResponse(
            id=row.id,
            prompt=prompt,
            title=profile.playlist_title,
            description=description,
            playlist_url=playlist_url,
            tracks=tracks,
            pool_stats=pool_stats,
            profile=profile,
        )

    async def list_history(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> PlaylistHistoryResponse:
        rows = await self._repo.list_by_user(user_id, limit=limit, offset=offset)
        items: list[PlaylistHistoryItem] = []
        for row in rows:
            pool_stats = None
            if row.pool_stats is not None:
                pool_stats = PlaylistPoolStats.model_validate(row.pool_stats)
            items.append(
                PlaylistHistoryItem(
                    id=row.id,
                    prompt=row.prompt,
                    title=row.title,
                    playlist_url=row.playlist_url,
                    pool_stats=pool_stats,
                    created_at=row.created_at,
                )
            )
        return PlaylistHistoryResponse(items=items, limit=limit, offset=offset)

    async def get_generation(
        self,
        generation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PlaylistGenerateResponse:
        row = await self._repo.get_by_id_for_user(generation_id, user_id)
        if row is None:
            raise NotFoundError("Playlist generation not found")
        return generation_to_response(row)

    async def _export(
        self,
        client: ClientAsync,
        profile: MusicProfile,
        ranked: list[ScoredTrack],
        description: str,
        login: str,
    ) -> str:
        track_ids = [track.id for track in ranked]
        return await self._yandex.export_playlist(
            client,
            title=profile.playlist_title,
            description=description,
            track_ids=track_ids,
            login=login,
        )
