"""Merge sprint7 chain and skipped_files branch into single head

Revision ID: s8a2_merge_heads
Revises: s7a3_message_feedback, s8a1_add_skipped_files
Create Date: 2026-03-16 10:30:00.000000

This merge migration unifies the two parallel Alembic heads:
  - s7a3_message_feedback  (end of sprint 7 chain)
  - s8a1_add_skipped_files (standalone skipped_files column)

After applying this migration, 'alembic upgrade head' works normally.
"""
from typing import Sequence, Union

revision: str = "s8a2_merge_heads"
down_revision: Union[str, tuple] = ("s7a3_message_feedback", "s8a1_add_skipped_files")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
