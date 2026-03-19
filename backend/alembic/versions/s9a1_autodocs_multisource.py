"""Sprint 9a1: AutoDocs multi-source support — add source_ids and source_config columns.

Revision ID: s9a1
Revises: s8a7
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa

revision = "s9a1"
down_revision = "s8a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generated_docs",
        sa.Column("source_ids", sa.JSON(), nullable=True),
    )
    op.add_column(
        "generated_docs",
        sa.Column("source_config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generated_docs", "source_config")
    op.drop_column("generated_docs", "source_ids")
