"""Add mapping feedback fields to concept_mappings

Revision ID: s5b1_mapping_feedback
Revises: s4c1_pgvector_embeddings
Create Date: 2026-03-09 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision: str = "s5b1_mapping_feedback"
down_revision: Union[str, None] = "s4c1_pgvector_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("concept_mappings")]

    if "feedback_by_id" not in columns:
        op.add_column("concept_mappings", sa.Column("feedback_by_id", sa.Integer(), nullable=True))
    if "feedback_comment" not in columns:
        op.add_column("concept_mappings", sa.Column("feedback_comment", sa.Text(), nullable=True))
    if "feedback_at" not in columns:
        op.add_column("concept_mappings", sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("concept_mappings", "feedback_at")
    op.drop_column("concept_mappings", "feedback_comment")
    op.drop_column("concept_mappings", "feedback_by_id")
