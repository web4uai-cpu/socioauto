"""allow youtube and youtube_shorts social accounts

Revision ID: c41a7f2b9e10
Revises: 0d35d88ebd83
Create Date: 2026-07-26 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = 'c41a7f2b9e10'
down_revision: str | Sequence[str] | None = '0d35d88ebd83'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = 'ck_social_accounts_platform'
_BASE_PLATFORMS = "'x','instagram','linkedin','tiktok','facebook'"
_WITH_YOUTUBE = f"{_BASE_PLATFORMS},'youtube','youtube_shorts'"


def _swap(platforms: str) -> None:
    # batch_alter_table recreates the table on SQLite, which cannot DROP a CHECK constraint.
    with op.batch_alter_table('social_accounts') as batch:
        batch.drop_constraint(_CONSTRAINT, type_='check')
        batch.create_check_constraint(_CONSTRAINT, f"platform IN ({platforms})")


def upgrade() -> None:
    _swap(_WITH_YOUTUBE)


def downgrade() -> None:
    _swap(_BASE_PLATFORMS)
