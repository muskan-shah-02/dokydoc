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
    op.execute("ALTER TABLE code_components ADD COLUMN IF NOT EXISTS analysis_delta JSONB")
    op.execute("ALTER TABLE code_components ADD COLUMN IF NOT EXISTS previous_analysis_hash VARCHAR(64)")


def downgrade() -> None:
    op.execute("ALTER TABLE code_components DROP COLUMN IF EXISTS previous_analysis_hash")
    op.execute("ALTER TABLE code_components DROP COLUMN IF EXISTS analysis_delta")
