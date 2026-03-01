"""Create knowledge_graph_versions table for graph storage and versioning

Revision ID: s4b1_knowledge_graph_versions
Revises: s4a4_add_source_document_id
Create Date: 2026-03-01 10:00:00.000000

Stores pre-built graph snapshots (nodes + edges as JSON) with versioning.
Enables fast graph loading, change tracking, and branch comparison.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 's4b1_knowledge_graph_versions'
down_revision: Union[str, None] = 's4a4_add_source_document_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if "knowledge_graph_versions" not in tables:
        op.create_table(
            "knowledge_graph_versions",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("source_type", sa.String(20), nullable=False, index=True),
            sa.Column("source_id", sa.Integer(), nullable=False, index=True),
            sa.Column("version", sa.Integer(), nullable=False, default=1),
            sa.Column("is_current", sa.Boolean(), nullable=False, default=True, index=True),
            sa.Column("graph_data", JSONB(), nullable=False),
            sa.Column("graph_hash", sa.String(64), nullable=False),
            sa.Column("graph_delta", JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        # Composite index for fast lookups: get current graph for a source
        op.create_index(
            "ix_kgv_source_current",
            "knowledge_graph_versions",
            ["tenant_id", "source_type", "source_id", "is_current"],
        )


def downgrade() -> None:
    op.drop_index("ix_kgv_source_current", table_name="knowledge_graph_versions")
    op.drop_table("knowledge_graph_versions")
