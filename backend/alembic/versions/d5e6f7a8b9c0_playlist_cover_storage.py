"""playlist cover storage key

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-18 10:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "playlist_generations",
        sa.Column("cover_storage_key", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("playlist_generations", "cover_storage_key")
