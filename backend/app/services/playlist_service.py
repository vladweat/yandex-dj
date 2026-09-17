"""Оркестрация пайплайна: LLM → retrieval → scoring → export → persist."""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import UTC, datetime, timedelta

from yandex_music import ClientAsync

from app.core.config import settings
from app.core.exceptions import (
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
)
from app.schemas.scoring import ScoredTrack
from app.schemas.track import TrackCandidate
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService, non_anchor_artists_from_ranked
from app.services.scoring_service import ScoringService
from app.services.yandex_music_service import YandexMusicService
from app.utils.quality import artist_matches_reference, artist_tokens, is_spurious_track
from app.utils.prompt_constraints import (
    ensure_hard_reference_artists,
    extract_prompt_constraints,
    filter_excluded_languages,
)
from app.utils.scoring import apply_library_artist_boost

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


def apply_exclude_artists(
    profile: MusicProfile,
    exclude_artists: list[str],
) -> tuple[MusicProfile, list[str]]:
    """
    Убирает excludes из reference_artists, если останется ≥4 якоря.

    Возвращает (profile, warnings). Кандидаты фильтруются отдельно —
    даже если якоря не трогали.
    """
    excludes = _normalize_excludes(exclude_artists)
    if not excludes:
        return profile, []
    remaining = [
        artist
        for artist in profile.reference_artists
        if not any(artist_matches_reference(artist, excluded) for excluded in excludes)
    ]
    if len(remaining) < 4:
        kept = [
            artist
            for artist in profile.reference_artists
            if any(artist_matches_reference(artist, excluded) for excluded in excludes)
        ]
        names = ", ".join(kept) if kept else ", ".join(excludes)
        warning = (
            f"exclude_artists не сняты с якорей (нужно ≥4 reference_artists): {names}. "
            "Из пула кандидатов они всё равно исключены."
        )
        logger.warning(warning)
        return profile, [warning]
    hard_remaining = [
        artist
        for artist in profile.hard_reference_artists
        if any(artist_matches_reference(artist, ref) for ref in remaining)
        and not any(artist_matches_reference(artist, excluded) for excluded in excludes)
    ]
    return (
        profile.model_copy(
            update={
                "reference_artists": remaining,
                "hard_reference_artists": hard_remaining,
            }
        ),
        [],
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
    ) -> PlaylistGenerateResponse:
        await self._ensure_quota_available(user_id, source_id=source_id)
        excludes = _normalize_excludes(exclude_artists or [])
        pipeline_started = time.perf_counter()
        warnings: list[str] = []

        constraints = extract_prompt_constraints(prompt)
        languages = _normalize_excludes(list(exclude_languages or []))
        for lang in constraints.exclude_languages:
            if lang not in {item.casefold() for item in languages}:
                languages.append(lang)
        if constraints.prefer_high_diversity and diversity == "normal":
            diversity = "high"
            warnings.append("diversity=high по промпту («разнообразн…»).")
        if "ru" in {item.casefold() for item in languages}:
            warnings.append("Исключены треки с кириллицей в названии/исполнителях.")

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
        if use_library:
            try:
                library_artists = await self._yandex.fetch_library_artist_names(
                    access_token,
                    limit=settings.library_artist_limit,
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
                seed_artists = library_artists[: settings.library_seed_artists]
                candidates = await self._retrieval.expand_from_artists(
                    profile,
                    access_token,
                    candidates,
                    seed_artists,
                    similar_seeds=settings.library_similar_seeds,
                )
        except YandexMusicError:
            raise
        except Exception as exc:
            raise RetrievalError(f"Retrieval failed: {exc}") from exc
        retrieval_ms = int((time.perf_counter() - retrieval_started) * 1000)

        candidates = filter_excluded_candidates(candidates, excludes)
        before_lang = len(candidates)
        candidates = filter_excluded_languages(candidates, languages)
        if before_lang and not candidates:
            raise RetrievalError("No candidates left after language filters")
        if not candidates:
            raise RetrievalError("No candidates found for the prompt")
        scoring_started = time.perf_counter()
        try:
            selected, candidates, method = await self._score_with_feedback(
                profile,
                candidates,
                prompt=prompt,
                access_token=access_token,
                excludes=excludes,
                exclude_languages=languages,
                diversity=diversity,
                library_artists=library_artists,
            )
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
        }
        warnings_count = len(warnings)
        full_n = pool_stats.selected == track_count
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
            options=generation_options.model_dump(),
            source_id=source_id,
            latency_ms=total_ms,
            latency_breakdown=latency_breakdown,
            warnings=warnings or None,
            warnings_count=warnings_count,
        )

        logger.info(
            "Playlist pipeline: llm=%dms retrieval=%dms scoring=%dms export=%dms "
            "total=%dms tracks=%d method=%s raw=%d clean=%d selected=%d track_count=%d "
            "full_n=%s warnings_count=%d diversity=%s use_library=%s "
            "library_artists=%d source_id=%s id=%s",
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
            row.id,
        )

        return generation_to_response(row)

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

    async def _score_with_feedback(
        self,
        profile: MusicProfile,
        candidates: list[TrackCandidate],
        *,
        prompt: str,
        access_token: str,
        excludes: list[str],
        diversity: DiversityMode,
        library_artists: list[str] | None = None,
        exclude_languages: list[str] | None = None,
    ) -> tuple[list[ScoredTrack], list[TrackCandidate], str]:
        library = library_artists or []
        languages = list(exclude_languages or [])
        ranked_pool, method = await self._scoring.rank_pool(
            profile,
            candidates,
            user_prompt=prompt,
        )
        if library:
            ranked_pool = apply_library_artist_boost(
                ranked_pool,
                library,
                boost=settings.library_artist_boost,
            )
        selected = self._scoring.select(ranked_pool, profile, diversity=diversity)
        selected = filter_excluded_scored(selected, excludes)
        selected = filter_excluded_languages(selected, languages)

        if len(selected) >= profile.target_track_count:
            return selected[: profile.target_track_count], candidates, method

        feedback_artists = non_anchor_artists_from_ranked(
            ranked_pool,
            profile,
            limit=settings.feedback_artists_limit,
        )
        feedback_artists = [
            artist
            for artist in feedback_artists
            if not any(artist_matches_reference(artist, excluded) for excluded in excludes)
        ]
        if not feedback_artists:
            return selected, candidates, method

        known_ids = {track.id for track, _ in ranked_pool}
        candidates = await self._retrieval.expand_from_artists(
            profile,
            access_token,
            candidates,
            feedback_artists,
            similar_seeds=settings.feedback_similar_seeds,
        )
        candidates = filter_excluded_candidates(candidates, excludes)
        candidates = filter_excluded_languages(candidates, languages)
        new_candidates = [track for track in candidates if track.id not in known_ids]
        if not new_candidates:
            return selected, candidates, method

        ranked_pool, method = await self._scoring.rank_pool_merge(
            profile,
            ranked_pool,
            new_candidates,
            user_prompt=prompt,
        )
        if library:
            ranked_pool = apply_library_artist_boost(
                ranked_pool,
                library,
                boost=settings.library_artist_boost,
            )
        selected = self._scoring.select(ranked_pool, profile, diversity=diversity)
        selected = filter_excluded_scored(selected, excludes)
        selected = filter_excluded_languages(selected, languages)
        return selected[: profile.target_track_count], candidates, method

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
