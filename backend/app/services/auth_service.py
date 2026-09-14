"""OAuth Device Flow."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from yandex_music.exceptions import DeviceAuthError

from app.core.config import settings
from app.core.exceptions import AuthError
from app.core.security import encrypt_token
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import DeviceFlowPollResponse, DeviceFlowStartResponse
from app.services.yandex_music_service import YandexMusicService


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        yandex: YandexMusicService,
        user_repo: UserRepository,
        session_repo: SessionRepository,
    ) -> None:
        self._db = db
        self._yandex = yandex
        self._user_repo = user_repo
        self._session_repo = session_repo

    async def start_device_flow(self) -> DeviceFlowStartResponse:
        code = await self._yandex.request_device_code()
        return DeviceFlowStartResponse(
            device_code=code.device_code,
            user_code=code.user_code,
            verification_url=code.verification_url,
            expires_in=code.expires_in,
            interval=code.interval,
        )

    async def poll_device_flow(self, device_code: str) -> DeviceFlowPollResponse:
        try:
            token = await self._yandex.poll_device_token(device_code)
        except DeviceAuthError as exc:
            raise AuthError(str(exc)) from exc

        if token is None:
            return DeviceFlowPollResponse(status="pending")

        return await self.create_session_from_token(token.access_token)

    async def create_session_from_token(
        self,
        access_token: str,
        *,
        yandex_uid: int | None = None,
        login: str | None = None,
    ) -> DeviceFlowPollResponse:
        """Сохранить OAuth-токен в БД.

        Если переданы yandex_uid и login — запросов к API Яндекса нет (только БД).
        """
        if yandex_uid is None or login is None:
            yandex_uid, login = await self._yandex.resolve_account(access_token)

        user = await self._user_repo.upsert(yandex_uid=yandex_uid, login=login)

        expires_at = datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours)
        session = await self._session_repo.create(
            user_id=user.id,
            encrypted_token=encrypt_token(access_token),
            expires_at=expires_at,
        )
        await self._db.commit()

        return DeviceFlowPollResponse(
            status="authenticated",
            session_id=str(session.id),
        )
