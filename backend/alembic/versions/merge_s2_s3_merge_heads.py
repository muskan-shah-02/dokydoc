"""Merge all Sprint 2 + Sprint 3 migration branches

Revision ID: merge_s2_s3
Revises: a1b2c3d4e5f6, s3a1_repositories, g2b3c4d5e6f7
Create Date: 2026-02-08 15:00:00.000000

Merge three migration branches that all diverged from f1a2b3c4d5e6:
- a1b2c3d4e5f6: Sprint 2 tasks & comments tables
- s3a1_repositories: Sprint 3 repositories table + code_components FK
- g2b3c4d5e6f7: Sprint 2 usage_logs for billing analytics
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'merge_s2_s3'
down_revision: Union[str, Sequence[str]] = ('a1b2c3d4e5f6', 's3a1_repositories', 'g2b3c4d5e6f7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
