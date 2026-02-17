"""Add analysis timing columns to code_components

Revision ID: s3a6_analysis_timing
Revises: s3a5_fix_cost_cols
Create Date: 2026-02-17 20:00:00.000000

Adds analysis_started_at and analysis_completed_at for tracking
how long code analysis takes.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "s3a6_analysis_timing"
down_revision: Union[str, None] = "s3a5_fix_cost_cols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check and add analysis_started_at
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='code_components' AND column_name='analysis_started_at'"
    ))
    if result.fetchone() is None:
        op.add_column("code_components", sa.Column("analysis_started_at", sa.DateTime(), nullable=True))

    # Check and add analysis_completed_at
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='code_components' AND column_name='analysis_completed_at'"
    ))
    if result.fetchone() is None:
        op.add_column("code_components", sa.Column("analysis_completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("code_components", "analysis_completed_at")
    op.drop_column("code_components", "analysis_started_at")
