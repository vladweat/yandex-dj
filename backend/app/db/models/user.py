import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.playlist_generation import PlaylistGeneration
    from app.db.models.session import Session


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    yandex_uid: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    login: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    playlist_generations: Mapped[list["PlaylistGeneration"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
