"""telegram client channel and user id

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-09-18 08:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        op.f("ix_users_telegram_user_id"),
        "users",
        ["telegram_user_id"],
        unique=True,
    )
    op.add_column(
        "playlist_generations",
        sa.Column("client_channel", sa.String(length=32), nullable=False, server_default="web"),
    )


def downgrade() -> None:
    op.drop_column("playlist_generations", "client_channel")
    op.drop_index(op.f("ix_users_telegram_user_id"), table_name="users")
    op.drop_column("users", "telegram_user_id")
