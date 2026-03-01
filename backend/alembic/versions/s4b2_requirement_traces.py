"""Create requirement_traces table for BRD-to-Code traceability

Revision ID: s4b2_requirement_traces
Revises: s4b1_knowledge_graph_versions
Create Date: 2026-03-01 10:30:00.000000

Links individual BRD requirements to their implementing code concepts.
Part of the 3-layer hybrid validation system (Layer 2).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 's4b2_requirement_traces'
down_revision: Union[str, None] = 's4b1_knowledge_graph_versions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if "requirement_traces" not in tables:
        op.create_table(
            "requirement_traces",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("initiative_id", sa.Integer(), sa.ForeignKey("initiatives.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("requirement_key", sa.String(100), nullable=False),
            sa.Column("requirement_text", sa.Text(), nullable=False),
            sa.Column("code_concept_ids", JSONB(), default=list),
            sa.Column("code_component_ids", JSONB(), default=list),
            sa.Column("coverage_status", sa.String(30), nullable=False, default="not_covered"),
            sa.Column("validation_status", sa.String(20), nullable=False, default="pending"),
            sa.Column("validation_details", JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index(
            "ix_rt_doc_tenant",
            "requirement_traces",
            ["tenant_id", "document_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_rt_doc_tenant", table_name="requirement_traces")
    op.drop_table("requirement_traces")
