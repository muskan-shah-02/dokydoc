"""Add concept_mappings table for cross-graph linking

Revision ID: s3a2_concept_mapping
Revises: s3d5_delta_analysis
Create Date: 2026-02-10 14:00:00.000000

ADHOC-04: ConceptMapping — replaces expensive AI reconciliation with
explicit, auditable cross-graph mappings between document and code concepts.
Uses 3-tier algorithmic matching (exact, fuzzy, AI fallback).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 's3a2_concept_mapping'
down_revision: Union[str, None] = 's3d5_delta_analysis'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'concept_mappings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False, index=True),
        sa.Column('document_concept_id', sa.Integer(),
                   sa.ForeignKey('ontology_concepts.id'), nullable=False, index=True),
        sa.Column('code_concept_id', sa.Integer(),
                   sa.ForeignKey('ontology_concepts.id'), nullable=False, index=True),
        sa.Column('mapping_method', sa.String(20), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='candidate', index=True),
        sa.Column('relationship_type', sa.String(50), nullable=False, server_default='implements'),
        sa.Column('ai_reasoning', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Unique constraint: one mapping per doc+code pair per tenant
    op.create_unique_constraint(
        'uq_concept_mapping_pair',
        'concept_mappings',
        ['tenant_id', 'document_concept_id', 'code_concept_id']
    )


def downgrade() -> None:
    op.drop_constraint('uq_concept_mapping_pair', 'concept_mappings', type_='unique')
    op.drop_table('concept_mappings')
