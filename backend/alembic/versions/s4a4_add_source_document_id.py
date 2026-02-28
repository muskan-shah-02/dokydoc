"""Add source_document_id to ontology_concepts for per-document subgraph linkage

Revision ID: s4a4_source_document
Revises: s4a3_source_component
Create Date: 2026-02-28 14:00:00.000000

Links each ontology concept back to the document that generated it.
Enables per-document subgraph queries — Level 1 of the Brain Architecture.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = 's4a4_source_document'
down_revision: Union[str, None] = 's4a3_source_component'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("ontology_concepts")]

    if "source_document_id" not in columns:
        op.add_column(
            "ontology_concepts",
            sa.Column("source_document_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_ontology_concept_source_document",
            "ontology_concepts",
            "documents",
            ["source_document_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_ontology_concepts_source_document_id",
            "ontology_concepts",
            ["source_document_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_ontology_concepts_source_document_id", table_name="ontology_concepts")
    op.drop_constraint("fk_ontology_concept_source_document", "ontology_concepts", type_="foreignkey")
    op.drop_column("ontology_concepts", "source_document_id")
