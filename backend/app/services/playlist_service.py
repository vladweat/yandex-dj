"""Оркестрация пайплайна: LLM → retrieval → scoring → export → persist."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from datetime import UTC, datetime, timedelta

from yandex_music import ClientAsync

from app.core.config import settings
from app.core.exceptions import (
    CoverArtError,
    ExportError,
    LLMError,
    NotFoundError,
    QuotaExceededError,
    RetrievalError,
    ScoringError,
    YandexMusicError,
)
from app.db.models.playlist_generation import PlaylistGeneration
from app.repositories.playlist_generation_repository import PlaylistGenerationRepository
from app.schemas.llm import MusicProfile
from app.schemas.playlist import (
    DiversityMode,
    FeedbackValue,
    PlaylistFeedbackResponse,
    PlaylistGenerateResponse,
    PlaylistGenerationOptions,
    PlaylistHistoryItem,
    PlaylistHistoryResponse,
    PlaylistPoolStats,
    PlaylistQuotaResponse,
    PlaylistTrackResponse,
    TrackEditAction,
)
from app.schemas.scoring import ScoredTrack
from app.services.cover_art_service import CoverArtService
from app.services.llm_service import LLMService
from app.services.playlist_scoring import score_with_feedback
from app.services.retrieval_service import RetrievalService
from app.services.scoring_service import ScoringService
from app.services.yandex_music_service import YandexMusicService
from app.utils.playlist_filters import (
    apply_exclude_artists,
    filter_excluded_candidates,
    filter_explicit_candidates,
    normalize_excludes,
)
from app.utils.prompt_constraints import (
    ensure_hard_reference_artists,
    extract_prompt_constraints,
    filter_excluded_languages,
)
from app.utils.quality import is_spurious_track
from app.utils.tracks import tracks_to_candidates

# Re-export для тестов и внешних импортов
__all__ = [
    "PlaylistService",
    "apply_exclude_artists",
    "build_playlist_description",
    "filter_excluded_candidates",
    "generation_to_response",
    "yandex_kind_from_url",
]

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


def _options_from_row(raw: dict | None) -> PlaylistGenerationOptions | None:
    if not raw:
        return None
    try:
        return PlaylistGenerationOptions.model_validate(raw)
    except Exception:
        return None


def _feedback_from_row(value: int | None) -> FeedbackValue | None:
    if value == 1:
        return "like"
    if value == -1:
        return "dislike"
    return None


def _feedback_to_int(value: FeedbackValue | None) -> int | None:
    if value == "like":
        return 1
    if value == "dislike":
        return -1
    return None


def yandex_kind_from_url(playlist_url: str) -> str | None:
    match = _KIND_FROM_URL.search(playlist_url)
    return match.group(1) if match else None


def generation_to_response(
    row: PlaylistGeneration,
    *,
    warnings: list[str] | None = None,
) -> PlaylistGenerateResponse:
    pool_stats = None
    if row.pool_stats is not None:
        pool_stats = PlaylistPoolStats.model_validate(row.pool_stats)
    stored_warnings = row.warnings if isinstance(row.warnings, list) else []
    return PlaylistGenerateResponse(
        id=row.id,
        prompt=row.prompt,
        title=row.title,
        description=row.description,
        playlist_url=row.playlist_url,
        tracks=[PlaylistTrackResponse.model_validate(track) for track in row.tracks],
        pool_stats=pool_stats,
        profile=MusicProfile.model_validate(row.profile),
        options=_options_from_row(row.options),
        warnings=list(warnings if warnings is not None else stored_warnings),
        source_id=row.source_id,
        latency_ms=row.latency_ms,
        feedback=_feedback_from_row(row.feedback),
        has_cover=bool(row.cover_storage_key),
    )


class PlaylistService:
    def __init__(
        self,
        llm: LLMService,
        retrieval: RetrievalService,
        scoring: ScoringService,
        yandex: YandexMusicService,
        repo: PlaylistGenerationRepository,
        cover: CoverArtService | None = None,
    ) -> None:
        self._llm = llm
        self._retrieval = retrieval
        self._scoring = scoring
        self._yandex = yandex
        self._repo = repo
        self._cover = cover or CoverArtService()

    @staticmethod
    def _utc_day_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        else:
            current = current.astimezone(UTC)
        start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        resets_at = start + timedelta(days=1)
        return start, resets_at

    async def get_quota(self, user_id: uuid.UUID) -> PlaylistQuotaResponse:
        limit = settings.daily_generation_limit
        start, resets_at = self._utc_day_bounds()
        if limit <= 0:
            return PlaylistQuotaResponse(
                limit=0,
                used=0,
                remaining=0,
                unlimited=True,
                resets_at=resets_at,
            )
        used = await self._repo.count_new_generations_since(user_id, since=start)
        remaining = max(0, limit - used)
        return PlaylistQuotaResponse(
            limit=limit,
            used=used,
            remaining=remaining,
            unlimited=False,
            resets_at=resets_at,
        )

    async def _ensure_quota_available(
        self,
        user_id: uuid.UUID,
        *,
        source_id: uuid.UUID | None,
    ) -> None:
        # «Ещё вариант» не расходует soft-квоту (freemium-friendly).
        if source_id is not None:
            return
        quota = await self.get_quota(user_id)
        if quota.unlimited or quota.remaining > 0:
            return
        raise QuotaExceededError(
            (
                f"Дневной лимит генераций исчерпан ({quota.limit}/сутки). "
                "«Ещё вариант» из истории всё ещё доступен."
            ),
            limit=quota.limit,
            used=quota.used,
            remaining=quota.remaining,
            resets_at=quota.resets_at.isoformat(),
        )

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
        exclude_languages: list[str] | None = None,
        diversity: DiversityMode = "normal",
        use_library: bool = False,
        source_id: uuid.UUID | None = None,
        client_channel: str = "web",
    ) -> PlaylistGenerateResponse:
        await self._ensure_quota_available(user_id, source_id=source_id)
        excludes = normalize_excludes(exclude_artists or [])
        pipeline_started = time.perf_counter()
        warnings: list[str] = []

        constraints = extract_prompt_constraints(prompt)
        languages = normalize_excludes(list(exclude_languages or []))
        for lang in constraints.exclude_languages:
            if lang not in {item.casefold() for item in languages}:
                languages.append(lang)
        if constraints.prefer_high_diversity and diversity == "normal":
            diversity = "high"
            warnings.append("diversity=high по промпту («разнообразн…»).")
        if "ru" in {item.casefold() for item in languages}:
            warnings.append("Исключены треки с кириллицей в названии/исполнителях.")
        exclude_explicit = constraints.exclude_explicit
        if exclude_explicit:
            warnings.append("Исключены треки с пометкой explicit (E) по промпту.")

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

        profile = ensure_hard_reference_artists(profile, prompt)
        profile, exclude_warnings = apply_exclude_artists(profile, excludes)
        warnings.extend(exclude_warnings)
        # После exclude якорей — пересчитать hard, если опустели.
        profile = ensure_hard_reference_artists(profile, prompt)
        library_artists: list[str] = []

        generation_id = uuid.uuid4()
        cover_task: asyncio.Task[str] | None = None
        if self._cover.is_enabled():
            cover_task = asyncio.create_task(
                self._cover.generate(generation_id, profile, prompt),
            )

        if use_library:
            try:
                library_artists = await self._yandex.fetch_library_artist_names(
                    access_token,
                    limit=settings.library.artist_limit,
                )
                if not library_artists:
                    warnings.append(
                        "Библиотека пуста или недоступна — генерируем без персонализации."
                    )
            except Exception as exc:
                logger.warning("Library taste fetch failed: %s", exc)
                warnings.append(
                    "Не удалось загрузить лайки/недавнее — генерируем без персонализации."
                )
                library_artists = []

        retrieval_started = time.perf_counter()
        try:
            candidates = await self._retrieval.collect_candidates(profile, access_token)
            if library_artists:
                seed_artists = library_artists[: settings.library.seed_artists]
                candidates = await self._retrieval.expand_from_artists(
                    profile,
                    access_token,
                    candidates,
                    seed_artists,
                    similar_seeds=settings.library.similar_seeds,
                )
        except YandexMusicError:
            raise
        except Exception as exc:
            raise RetrievalError(f"Retrieval failed: {exc}") from exc
        retrieval_ms = int((time.perf_counter() - retrieval_started) * 1000)

        candidates = filter_excluded_candidates(candidates, excludes)
        before_lang = len(candidates)
        candidates = filter_excluded_languages(candidates, languages)
        if exclude_explicit:
            candidates = filter_explicit_candidates(candidates)
        if before_lang and not candidates:
            raise RetrievalError("No candidates left after language filters")
        if not candidates:
            raise RetrievalError("No candidates found for the prompt")
        scoring_started = time.perf_counter()
        from app.services.service_factory import get_track_cache

        try:
            selected, candidates, method, shortfall, lyrics_warnings = await score_with_feedback(
                profile,
                candidates,
                prompt=prompt,
                access_token=access_token,
                excludes=excludes,
                exclude_languages=languages,
                exclude_explicit=exclude_explicit,
                diversity=diversity,
                scoring=self._scoring,
                retrieval=self._retrieval,
                library_artists=library_artists,
                yandex=self._yandex,
                track_cache=get_track_cache(),
            )
        except Exception as exc:
            raise ScoringError(f"Scoring failed: {exc}") from exc
        scoring_ms = int((time.perf_counter() - scoring_started) * 1000)
        warnings.extend(lyrics_warnings)

        if not selected:
            raise ScoringError("Scoring returned no tracks")

        if shortfall:
            warnings.append(
                f"shortfall: в плейлисте {len(selected)} из {track_count} треков "
                "(не добирали слабый хвост)."
            )

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

        cover_storage_key: str | None = None
        cover_ms = 0
        if cover_task is not None:
            cover_started = time.perf_counter()
            try:
                cover_storage_key = await asyncio.wait_for(
                    cover_task,
                    timeout=settings.playlist_cover_timeout_sec,
                )
            except TimeoutError:
                cover_task.cancel()
                warnings.append("AI-обложка не успела сгенерироваться.")
            except CoverArtError:
                warnings.append("Не удалось сгенерировать AI-обложку.")
            except Exception as exc:
                logger.warning("Cover generation failed for %s: %s", generation_id, exc)
                warnings.append("Не удалось сгенерировать AI-обложку.")
            finally:
                cover_ms = int((time.perf_counter() - cover_started) * 1000)

        tracks = [_track_response(track) for track in selected]
        generation_options = PlaylistGenerationOptions(
            track_count=track_count,
            instrumental_only=instrumental_only,
            exclude_artists=excludes,
            exclude_languages=languages,
            diversity=diversity,
            use_library=use_library,
        )
        total_ms = int((time.perf_counter() - pipeline_started) * 1000)
        latency_breakdown = {
            "llm": llm_ms,
            "retrieval": retrieval_ms,
            "scoring": scoring_ms,
            "export": export_ms,
            "cover": cover_ms,
        }
        warnings_count = len(warnings)
        full_n = pool_stats.selected == track_count
        row = await self._repo.create(
            id=generation_id,
            user_id=user_id,
            prompt=prompt,
            title=profile.playlist_title,
            description=description,
            playlist_url=playlist_url,
            yandex_kind=yandex_kind_from_url(playlist_url),
            profile=profile.model_dump(),
            tracks=[track.model_dump() for track in tracks],
            pool_stats=pool_stats.model_dump(),
            options=generation_options.model_dump(),
            source_id=source_id,
            latency_ms=total_ms,
            latency_breakdown=latency_breakdown,
            warnings=warnings or None,
            warnings_count=warnings_count,
            client_channel=client_channel,
            cover_storage_key=cover_storage_key,
        )

        logger.info(
            "Playlist pipeline: llm=%dms retrieval=%dms scoring=%dms export=%dms "
            "total=%dms tracks=%d method=%s raw=%d clean=%d selected=%d track_count=%d "
            "full_n=%s warnings_count=%d diversity=%s use_library=%s "
            "library_artists=%d source_id=%s client_channel=%s id=%s",
            llm_ms,
            retrieval_ms,
            scoring_ms,
            export_ms,
            total_ms,
            len(selected),
            method,
            pool_stats.raw,
            pool_stats.clean,
            pool_stats.selected,
            track_count,
            full_n,
            warnings_count,
            diversity,
            use_library,
            len(library_artists),
            source_id,
            client_channel,
            row.id,
        )

        return generation_to_response(row)

    async def get_cover_bytes(
        self,
        generation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[bytes, str] | None:
        row = await self._repo.get_by_id_for_user(generation_id, user_id)
        if row is None or not row.cover_storage_key:
            return None
        data = self._cover.read_bytes(row.cover_storage_key)
        if data is None:
            return None
        return data, "image/png"

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
                    options=_options_from_row(row.options),
                    created_at=row.created_at,
                    source_id=row.source_id,
                    latency_ms=row.latency_ms,
                    feedback=_feedback_from_row(row.feedback),
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

    async def edit_track(
        self,
        generation_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        track_id: str,
        action: TrackEditAction,
        access_token: str,
    ) -> PlaylistGenerateResponse:
        row = await self._repo.get_by_id_for_user(generation_id, user_id)
        if row is None:
            raise NotFoundError("Playlist generation not found")

        stored_tracks = [PlaylistTrackResponse.model_validate(item) for item in row.tracks]
        index = next((i for i, track in enumerate(stored_tracks) if track.id == track_id), None)
        if index is None:
            raise NotFoundError("Track not found in playlist")

        current_ids = {track.id for track in stored_tracks}
        profile = MusicProfile.model_validate(row.profile)
        options = _options_from_row(row.options)
        excludes = normalize_excludes((options.exclude_artists if options else None) or [])

        kind = row.yandex_kind or yandex_kind_from_url(row.playlist_url)
        if kind is None:
            raise ExportError("Playlist kind is missing")

        client = await self._yandex.init_client(access_token)

        if action == "remove":
            if len(stored_tracks) <= 1:
                raise ScoringError("Нельзя удалить последний трек в плейлисте")
            try:
                await self._yandex.delete_playlist_track_at(client, kind, index)
            except YandexMusicError as exc:
                raise ExportError(str(exc)) from exc
            stored_tracks.pop(index)
        else:
            similar_raw = await self._yandex.tracks_similar_list(client, track_id)
            candidates = tracks_to_candidates(similar_raw)
            candidates = [
                item
                for item in candidates
                if item.id not in current_ids and item.id != track_id
            ]
            candidates = filter_excluded_candidates(candidates, excludes)
            if not candidates and profile.search_queries:
                for query in profile.search_queries[:2]:
                    found = await self._yandex.search_tracks(client, query, limit=15, pages=1)
                    extra = tracks_to_candidates(found)
                    for item in extra:
                        if item.id not in current_ids and item.id != track_id:
                            candidates.append(item)
                    if candidates:
                        break
            if not candidates:
                raise ScoringError("Не нашли замену для этого трека")
            ranked, _method = await self._scoring.rank_pool(
                profile,
                candidates,
                user_prompt=row.prompt,
            )
            replacement: ScoredTrack | None = None
            for candidate, score in ranked:
                if candidate.id in current_ids:
                    continue
                replacement = ScoredTrack.from_candidate(candidate, score)
                break
            if replacement is None:
                raise ScoringError("Не нашли замену для этого трека")
            try:
                await self._yandex.replace_playlist_track_at(
                    client,
                    kind,
                    index,
                    replacement.id,
                )
            except YandexMusicError as exc:
                raise ExportError(str(exc)) from exc
            stored_tracks[index] = _track_response(replacement)

        pool_stats = None
        if row.pool_stats is not None:
            pool_stats = PlaylistPoolStats.model_validate(row.pool_stats)
            pool_stats = pool_stats.model_copy(update={"selected": len(stored_tracks)})

        updated = await self._repo.update_tracks(
            generation_id,
            user_id,
            tracks=[track.model_dump() for track in stored_tracks],
            pool_stats=pool_stats.model_dump() if pool_stats else None,
        )
        if updated is None:
            raise NotFoundError("Playlist generation not found")
        return generation_to_response(updated)

    async def set_feedback(
        self,
        generation_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        value: FeedbackValue | None,
    ) -> PlaylistFeedbackResponse:
        row = await self._repo.update_feedback(
            generation_id,
            user_id,
            feedback=_feedback_to_int(value),
        )
        if row is None:
            raise NotFoundError("Playlist generation not found")
        return PlaylistFeedbackResponse(
            id=row.id,
            feedback=_feedback_from_row(row.feedback),
            feedback_at=row.feedback_at,
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
