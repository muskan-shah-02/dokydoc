"""Catch-up: ensure synthesis columns exist on repositories table

Revision ID: s3a8_fix_synthesis
Revises: s3a7_repo_synthesis
Create Date: 2026-02-20 06:00:00.000000

s3a7 was recorded as executed but the columns were never actually created
(Alembic version table persists across Docker rebuilds — see MEMORY.md).
This catch-up migration adds them if missing.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "s3a8_fix_synthesis"
down_revision: Union[str, None] = "s3a7_repo_synthesis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check and add synthesis_data
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='repositories' AND column_name='synthesis_data'"
    ))
    if result.fetchone() is None:
        op.add_column("repositories", sa.Column("synthesis_data", JSONB, nullable=True))

    # Check and add synthesis_status
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='repositories' AND column_name='synthesis_status'"
    ))
    if result.fetchone() is None:
        op.add_column("repositories", sa.Column("synthesis_status", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("repositories", "synthesis_status")
    op.drop_column("repositories", "synthesis_data")
