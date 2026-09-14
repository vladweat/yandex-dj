from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.health_service import HealthService
from app.services.playlist_service import PlaylistService
from app.services.yandex_music_service import YandexMusicService


def get_health_service() -> HealthService:
    return HealthService()


def get_yandex_music_service() -> YandexMusicService:
    return YandexMusicService()


def get_playlist_service() -> PlaylistService:
    return PlaylistService()


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


DbSession = Depends(get_db_session)
