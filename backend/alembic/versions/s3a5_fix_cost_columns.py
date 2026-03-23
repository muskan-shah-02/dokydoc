"""Catch-up: ensure cost tracking columns exist on code_components

Revision ID: s3a5_fix_cost_cols
Revises: s3a4_code_cost
Create Date: 2026-02-17 15:00:00.000000

s3a4 was recorded as complete but the columns were never created.
This migration adds them if missing (idempotent).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 's3a5_fix_cost_cols'
down_revision: Union[str, None] = 's3a4_code_cost'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    for col_name, col_type, default in [
        ('ai_cost_inr', sa.Numeric(10, 4), '0'),
        ('token_count_input', sa.Integer(), '0'),
        ('token_count_output', sa.Integer(), '0'),
    ]:
        result = conn.execute(sa.text(
            f"SELECT EXISTS (SELECT FROM information_schema.columns "
            f"WHERE table_name = 'code_components' AND column_name = '{col_name}')"
        ))
        if not result.scalar():
            op.add_column('code_components', sa.Column(
                col_name, col_type, nullable=False, server_default=default
            ))

    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.columns "
        "WHERE table_name = 'code_components' AND column_name = 'cost_breakdown')"
    ))
    if not result.scalar():
        op.add_column('code_components', sa.Column('cost_breakdown', JSONB, nullable=True))


def downgrade() -> None:
    for col_name in ['cost_breakdown', 'token_count_output', 'token_count_input', 'ai_cost_inr']:
        op.drop_column('code_components', col_name)
