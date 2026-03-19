"""Sprint 9b1: Add sync_config column to integration_configs for deep JIRA sync.

Revision ID: s9b1
Revises: s9a1
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa

revision = "s9b1"
down_revision = "s9a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "integration_configs",
        sa.Column("sync_config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("integration_configs", "sync_config")
