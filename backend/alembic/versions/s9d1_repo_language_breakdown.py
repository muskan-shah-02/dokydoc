"""Add analyze_language_breakdown to repositories

Revision ID: s9d1
Revises: s9c1
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 's9d1'
down_revision = 's9c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'repositories',
        sa.Column('analyze_language_breakdown', JSONB, nullable=True)
    )


def downgrade() -> None:
    op.drop_column('repositories', 'analyze_language_breakdown')
