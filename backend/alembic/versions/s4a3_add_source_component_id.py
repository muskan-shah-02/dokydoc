"""Add source_component_id to ontology_concepts for per-file subgraph linkage

Revision ID: s4a3_source_component
Revises: s4a2_cross_project_mappings
Create Date: 2026-02-28 10:00:00.000000

Links each ontology concept back to the code component (file) that
generated it. Enables per-file subgraph queries and the "brain"
architecture where individual file graphs connect into the master graph.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = 's4a3_source_component'
down_revision: Union[str, None] = 's4a2_cross_project_mappings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("ontology_concepts")]

    if "source_component_id" not in columns:
        op.add_column(
            "ontology_concepts",
            sa.Column("source_component_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_ontology_concept_source_component",
            "ontology_concepts",
            "code_components",
            ["source_component_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_ontology_concepts_source_component_id",
            "ontology_concepts",
            ["source_component_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_ontology_concepts_source_component_id", table_name="ontology_concepts")
    op.drop_constraint("fk_ontology_concept_source_component", "ontology_concepts", type_="foreignkey")
    op.drop_column("ontology_concepts", "source_component_id")
