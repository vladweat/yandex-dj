import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class PlaylistGeneration(Base):
    __tablename__ = "playlist_generations"
    __table_args__ = (Index("ix_playlist_generations_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    playlist_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    yandex_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    tracks: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    pool_stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("playlist_generations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    generation_cost: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    warnings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    feedback: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    client_channel: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
    cover_storage_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="playlist_generations")
