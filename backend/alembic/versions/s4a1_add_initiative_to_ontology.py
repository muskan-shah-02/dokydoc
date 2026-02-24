"""Add initiative_id to ontology_concepts for project-scoped ontology

Revision ID: s4a1_initiative_ontology
Revises: s3d5_delta_analysis
Create Date: 2026-02-24 10:00:00.000000

SPRINT 4 Phase 2: Project-Scoped Ontology
Adds initiative_id FK to ontology_concepts so each project can have its own
knowledge graph. NULL = org-wide/unscoped (backward-compatible).
Adds composite index (tenant_id, initiative_id) for fast project filtering.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 's4a1_initiative_ontology'
down_revision: Union[str, None] = 's3d5_delta_analysis'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add initiative_id column (nullable — existing concepts remain unscoped)
    op.add_column(
        'ontology_concepts',
        sa.Column('initiative_id', sa.Integer(), sa.ForeignKey('initiatives.id'), nullable=True)
    )
    # Index for fast per-project lookups
    op.create_index(
        'ix_ontology_concepts_initiative_id',
        'ontology_concepts', ['initiative_id']
    )
    # Composite index for tenant + project filtered queries
    op.create_index(
        'ix_ontology_concepts_tenant_initiative',
        'ontology_concepts', ['tenant_id', 'initiative_id']
    )


def downgrade() -> None:
    op.drop_index('ix_ontology_concepts_tenant_initiative', table_name='ontology_concepts')
    op.drop_index('ix_ontology_concepts_initiative_id', table_name='ontology_concepts')
    op.drop_column('ontology_concepts', 'initiative_id')
