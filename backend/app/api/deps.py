import secrets
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.session import Session
from app.db.session import get_db
from app.repositories.playlist_generation_repository import PlaylistGenerationRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.health_service import HealthService
from app.services.llm_service import LLMService
from app.services.metrics_service import MetricsService
from app.services.playlist_service import PlaylistService
from app.services.retrieval_service import RetrievalService
from app.services.scoring_service import ScoringService
from app.services.service_factory import (
    build_llm_service,
    build_playlist_service,
    build_retrieval_service,
    build_scoring_service,
    build_yandex_music_service,
    get_track_cache,
)
from app.services.track_cache import TrackCacheService
from app.services.yandex_account_service import YandexAccountService
from app.services.yandex_music_service import YandexMusicService


def get_health_service() -> HealthService:
    return HealthService()


def get_yandex_music_service() -> YandexMusicService:
    return build_yandex_music_service()


def get_yandex_account_service(
    yandex: YandexMusicService = Depends(get_yandex_music_service),
) -> YandexAccountService:
    return YandexAccountService(yandex)


def get_llm_service() -> LLMService:
    return build_llm_service()


def get_track_cache_service() -> TrackCacheService:
    return get_track_cache()


def get_retrieval_service(
    yandex: YandexMusicService = Depends(get_yandex_music_service),
    cache: TrackCacheService = Depends(get_track_cache_service),
) -> RetrievalService:
    return build_retrieval_service(yandex=yandex, cache=cache)


def get_scoring_service() -> ScoringService:
    return build_scoring_service()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


def get_metrics_service(
    db: AsyncSession = Depends(get_db_session),
) -> MetricsService:
    return MetricsService(repo=PlaylistGenerationRepository(db))


async def require_metrics_token(
    x_metrics_token: str | None = Header(None, alias="X-Metrics-Token"),
) -> None:
    expected = settings.metrics_token.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Metrics endpoint is not configured (METRICS_TOKEN)",
        )
    if not x_metrics_token or not secrets.compare_digest(x_metrics_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Metrics-Token",
        )


def get_playlist_service(
    db: AsyncSession = Depends(get_db_session),
) -> PlaylistService:
    return build_playlist_service(db)


async def get_auth_service(
    db: AsyncSession = Depends(get_db_session),
    yandex: YandexMusicService = Depends(get_yandex_music_service),
) -> AuthService:
    return AuthService(
        db=db,
        yandex=yandex,
        user_repo=UserRepository(db),
        session_repo=SessionRepository(db),
    )


async def get_current_session(
    authorization: str | None = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db_session),
) -> Session:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )
    raw = authorization.removeprefix("Bearer ").strip()
    try:
        session_id = uuid.UUID(raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session id",
        ) from None

    session = await SessionRepository(db).get_valid(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    return session


DbSession = Depends(get_db_session)
CurrentSession = Depends(get_current_session)
