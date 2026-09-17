"""add generation metrics and feedback

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-16 11:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "playlist_generations",
        sa.Column("latency_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "playlist_generations",
        sa.Column("latency_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "playlist_generations",
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "playlist_generations",
        sa.Column(
            "warnings_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "playlist_generations",
        sa.Column("feedback", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "playlist_generations",
        sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_playlist_generations_user_id_created_at",
        "playlist_generations",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_playlist_generations_user_id_created_at",
        table_name="playlist_generations",
    )
    op.drop_column("playlist_generations", "feedback_at")
    op.drop_column("playlist_generations", "feedback")
    op.drop_column("playlist_generations", "warnings_count")
    op.drop_column("playlist_generations", "warnings")
    op.drop_column("playlist_generations", "latency_breakdown")
    op.drop_column("playlist_generations", "latency_ms")
