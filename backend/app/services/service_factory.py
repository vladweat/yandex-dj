"""Сборка сервисов (общая для FastAPI deps и CLI)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.playlist_generation_repository import PlaylistGenerationRepository
from app.services.llm_service import LLMService
from app.services.playlist_service import PlaylistService
from app.services.retrieval_service import RetrievalService
from app.services.scoring_service import ScoringService
from app.services.track_cache import TrackCacheService
from app.services.yandex_music_service import YandexMusicService

_track_cache: TrackCacheService | None = None


def get_track_cache() -> TrackCacheService:
    global _track_cache
    if _track_cache is None:
        _track_cache = TrackCacheService()
    return _track_cache


def build_yandex_music_service() -> YandexMusicService:
    return YandexMusicService()


def build_llm_service() -> LLMService:
    return LLMService()


def build_scoring_service() -> ScoringService:
    return ScoringService()


def build_retrieval_service(
    *,
    yandex: YandexMusicService | None = None,
    cache: TrackCacheService | None = None,
) -> RetrievalService:
    return RetrievalService(
        yandex=yandex or build_yandex_music_service(),
        cache=cache or get_track_cache(),
    )


def build_playlist_service(db: AsyncSession) -> PlaylistService:
    yandex = build_yandex_music_service()
    return PlaylistService(
        llm=build_llm_service(),
        retrieval=build_retrieval_service(yandex=yandex, cache=get_track_cache()),
        scoring=build_scoring_service(),
        yandex=yandex,
        repo=PlaylistGenerationRepository(db),
    )
