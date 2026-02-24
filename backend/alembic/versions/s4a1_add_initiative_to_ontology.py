"""Add initiative_id to ontology_concepts for project-scoped ontology

Revision ID: s4a1_initiative_ontology
Revises: s3a8_fix_synthesis
Create Date: 2026-02-24 10:00:00.000000

SPRINT 4 Phase 2: Project-Scoped Ontology
Adds initiative_id FK to ontology_concepts so each project can have its own
knowledge graph. NULL = org-wide/unscoped (backward-compatible).
Adds composite index (tenant_id, initiative_id) for fast project filtering.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = 's4a1_initiative_ontology'
down_revision: Union[str, None] = 's3a8_fix_synthesis'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = [col['name'] for col in inspector.get_columns('ontology_concepts')]

    # Add initiative_id column (nullable — existing concepts remain unscoped)
    if 'initiative_id' not in existing_columns:
        op.add_column(
            'ontology_concepts',
            sa.Column('initiative_id', sa.Integer(), sa.ForeignKey('initiatives.id'), nullable=True)
        )

    existing_indexes = [idx['name'] for idx in inspector.get_indexes('ontology_concepts')]
    # Index for fast per-project lookups
    if 'ix_ontology_concepts_initiative_id' not in existing_indexes:
        op.create_index(
            'ix_ontology_concepts_initiative_id',
            'ontology_concepts', ['initiative_id']
        )
    # Composite index for tenant + project filtered queries
    if 'ix_ontology_concepts_tenant_initiative' not in existing_indexes:
        op.create_index(
            'ix_ontology_concepts_tenant_initiative',
            'ontology_concepts', ['tenant_id', 'initiative_id']
        )


def downgrade() -> None:
    op.drop_index('ix_ontology_concepts_tenant_initiative', table_name='ontology_concepts')
    op.drop_index('ix_ontology_concepts_initiative_id', table_name='ontology_concepts')
    op.drop_column('ontology_concepts', 'initiative_id')
