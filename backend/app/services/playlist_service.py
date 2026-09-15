"""Оркестрация пайплайна: LLM → retrieval → scoring → export."""

import logging
import time

from yandex_music import ClientAsync

from app.core.config import settings
from app.core.exceptions import (
    ExportError,
    LLMError,
    RetrievalError,
    ScoringError,
    YandexMusicError,
)
from app.schemas.llm import MusicProfile
from app.schemas.playlist import (
    PlaylistGenerateResponse,
    PlaylistPoolStats,
    PlaylistTrackResponse,
)
from app.schemas.scoring import ScoredTrack
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService, non_anchor_artists_from_ranked
from app.services.scoring_service import ScoringService
from app.services.yandex_music_service import YandexMusicService
from app.utils.quality import is_spurious_track

logger = logging.getLogger(__name__)


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


class PlaylistService:
    def __init__(
        self,
        llm: LLMService,
        retrieval: RetrievalService,
        scoring: ScoringService,
        yandex: YandexMusicService,
    ) -> None:
        self._llm = llm
        self._retrieval = retrieval
        self._scoring = scoring
        self._yandex = yandex

    async def generate(
        self,
        prompt: str,
        track_count: int,
        instrumental_only: bool,
        access_token: str,
        login: str,
    ) -> PlaylistGenerateResponse:
        pipeline_started = time.perf_counter()

        llm_started = time.perf_counter()
        try:
            profile = await self._llm.parse_prompt(
                prompt,
                track_count=track_count,
                instrumental_only=instrumental_only,
            )
        except LLMError:
            raise
        llm_ms = int((time.perf_counter() - llm_started) * 1000)

        retrieval_started = time.perf_counter()
        try:
            candidates = await self._retrieval.collect_candidates(profile, access_token)
        except YandexMusicError:
            raise
        except Exception as exc:
            raise RetrievalError(f"Retrieval failed: {exc}") from exc
        retrieval_ms = int((time.perf_counter() - retrieval_started) * 1000)

        if not candidates:
            raise RetrievalError("No candidates found for the prompt")

        scoring_started = time.perf_counter()
        try:
            ranked_pool, method = await self._scoring.rank_pool(
                profile,
                candidates,
                user_prompt=prompt,
            )
            selected = self._scoring.select(ranked_pool, profile)

            # Feedback: топы + similar лучших не-якорных, если недобрали N
            if len(selected) < profile.target_track_count:
                feedback_artists = non_anchor_artists_from_ranked(
                    ranked_pool,
                    profile,
                    limit=settings.feedback_artists_limit,
                )
                if feedback_artists:
                    before = len(candidates)
                    candidates = await self._retrieval.expand_from_artists(
                        profile,
                        access_token,
                        candidates,
                        feedback_artists,
                        similar_seeds=settings.feedback_similar_seeds,
                    )
                    if len(candidates) > before:
                        ranked_pool, method = await self._scoring.rank_pool(
                            profile,
                            candidates,
                            user_prompt=prompt,
                        )
                        selected = self._scoring.select(ranked_pool, profile)
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

        total_ms = int((time.perf_counter() - pipeline_started) * 1000)
        logger.info(
            "Playlist pipeline: llm=%dms retrieval=%dms scoring=%dms export=%dms "
            "total=%dms tracks=%d method=%s raw=%d clean=%d",
            llm_ms,
            retrieval_ms,
            scoring_ms,
            export_ms,
            total_ms,
            len(selected),
            method,
            pool_stats.raw,
            pool_stats.clean,
        )

        return PlaylistGenerateResponse(
            title=profile.playlist_title,
            description=description,
            playlist_url=playlist_url,
            tracks=[_track_response(track) for track in selected],
            pool_stats=pool_stats,
        )

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
