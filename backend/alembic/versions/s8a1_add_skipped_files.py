"""Add skipped_files column to repositories table

Revision ID: s8a1_add_skipped_files
Revises: s3a1_repositories
Create Date: 2026-03-16 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "s8a1_add_skipped_files"
down_revision: Union[str, None] = "s3a1_repositories"
branch_labels: Union[str, Sequence[str], None] = ("skipped_files",)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE repositories
        ADD COLUMN IF NOT EXISTS skipped_files JSONB
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE repositories
        DROP COLUMN IF EXISTS skipped_files
    """)
