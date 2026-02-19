"""Add synthesis columns to repositories table

Revision ID: s3a7_repo_synthesis
Revises: s3a6_analysis_timing
Create Date: 2026-02-19 10:00:00.000000

Adds synthesis_data (JSONB) and synthesis_status (String) to repositories
for storing the "Reduce Phase" system architecture synthesis output.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "s3a7_repo_synthesis"
down_revision: Union[str, None] = "s3a6_analysis_timing"
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
