import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.session import Session


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        user_id: uuid.UUID,
        encrypted_token: str,
        expires_at: datetime,
    ) -> Session:
        session = Session(
            user_id=user_id,
            encrypted_token=encrypted_token,
            expires_at=expires_at,
        )
        self._db.add(session)
        await self._db.flush()
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        result = await self._db.execute(
            select(Session).options(selectinload(Session.user)).where(Session.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_valid(self, session_id: uuid.UUID) -> Session | None:
        session = await self.get_by_id(session_id)
        if session is None:
            return None
        if session.expires_at <= datetime.now(UTC):
            return None
        return session
