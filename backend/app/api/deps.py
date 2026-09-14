import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session import Session
from app.db.session import get_db
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.health_service import HealthService
from app.services.llm_service import LLMService
from app.services.playlist_service import PlaylistService
from app.services.yandex_account_service import YandexAccountService
from app.services.yandex_music_service import YandexMusicService


def get_health_service() -> HealthService:
    return HealthService()


def get_yandex_music_service() -> YandexMusicService:
    return YandexMusicService()


def get_yandex_account_service(
    yandex: YandexMusicService = Depends(get_yandex_music_service),
) -> YandexAccountService:
    return YandexAccountService(yandex)


def get_playlist_service() -> PlaylistService:
    return PlaylistService()


def get_llm_service() -> LLMService:
    return LLMService()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


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
