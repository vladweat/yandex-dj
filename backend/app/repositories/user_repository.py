from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_yandex_uid(self, yandex_uid: int) -> User | None:
        result = await self._db.execute(select(User).where(User.yandex_uid == yandex_uid))
        return result.scalar_one_or_none()

    async def upsert(self, yandex_uid: int, login: str) -> User:
        user = await self.get_by_yandex_uid(yandex_uid)
        if user is not None:
            user.login = login
            return user

        user = User(yandex_uid=yandex_uid, login=login)
        self._db.add(user)
        await self._db.flush()
        return user
