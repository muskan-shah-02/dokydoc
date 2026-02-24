"""Create cross_project_mappings table for inter-project concept linking

Revision ID: s4a2_cross_project_mappings
Revises: s4a1_initiative_ontology
Create Date: 2026-02-24 12:00:00.000000

SPRINT 4 Phase 3: Cross-Project Mapping
Links concepts between different projects to show how an organization's
projects relate. Separate from concept_mappings (which is doc↔code only).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 's4a2_cross_project_mappings'
down_revision: Union[str, None] = 's4a1_initiative_ontology'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cross_project_mappings',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False, index=True),
        sa.Column('concept_a_id', sa.Integer(), sa.ForeignKey('ontology_concepts.id'), nullable=False, index=True),
        sa.Column('concept_b_id', sa.Integer(), sa.ForeignKey('ontology_concepts.id'), nullable=False, index=True),
        sa.Column('initiative_a_id', sa.Integer(), sa.ForeignKey('initiatives.id'), nullable=False, index=True),
        sa.Column('initiative_b_id', sa.Integer(), sa.ForeignKey('initiatives.id'), nullable=False, index=True),
        sa.Column('mapping_method', sa.String(20), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False, default=0.0),
        sa.Column('status', sa.String(20), nullable=False, default='candidate', index=True),
        sa.Column('relationship_type', sa.String(50), nullable=False, default='shares_concept'),
        sa.Column('ai_reasoning', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    # Composite index for fast cross-project queries
    op.create_index(
        'ix_cross_project_mappings_initiatives',
        'cross_project_mappings', ['initiative_a_id', 'initiative_b_id']
    )


def downgrade() -> None:
    op.drop_index('ix_cross_project_mappings_initiatives', table_name='cross_project_mappings')
    op.drop_table('cross_project_mappings')
