"""Add analysis_delta and previous_analysis_hash to code_components

Revision ID: s3d5_delta_analysis
Revises: s3b1_source_type
Create Date: 2026-02-10 10:00:00.000000

SPRINT 3 Day 5 (AI-02): Delta Analysis Foundation
Stores the diff between current and previous analysis for a code component,
enabling continuous validation and change tracking across re-analyses.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 's3d5_delta_analysis'
down_revision: Union[str, None] = 's3b1_source_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add delta analysis JSON field — stores added/removed/modified diff
    op.add_column(
        'code_components',
        sa.Column('analysis_delta', sa.JSON(), nullable=True)
    )
    # Add hash of previous analysis — used to detect whether re-analysis changed anything
    op.add_column(
        'code_components',
        sa.Column('previous_analysis_hash', sa.String(64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('code_components', 'previous_analysis_hash')
    op.drop_column('code_components', 'analysis_delta')
