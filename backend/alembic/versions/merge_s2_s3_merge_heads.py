"""Merge Sprint 2 tasks and Sprint 3 repositories heads

Revision ID: merge_s2_s3
Revises: a1b2c3d4e5f6, s3a1_repositories
Create Date: 2026-02-08 15:00:00.000000

Merge two migration branches:
- a1b2c3d4e5f6: Sprint 2 tasks & comments tables
- s3a1_repositories: Sprint 3 repositories table + code_components FK
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'merge_s2_s3'
down_revision: Union[str, Sequence[str]] = ('a1b2c3d4e5f6', 's3a1_repositories')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
