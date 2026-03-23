"""Add source_type column to ontology_concepts for dual-source BOE

Revision ID: s3b1_source_type
Revises: merge_s2_s3
Create Date: 2026-02-09 10:00:00.000000

SPRINT 3: Dual-Source Business Ontology Engine
Tracks whether a concept was extracted from:
- "document" (BRD/SRS analysis)
- "code" (repository code analysis)
- "both" (cross-validated by both sources — highest confidence)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 's3b1_source_type'
down_revision: Union[str, None] = 'merge_s2_s3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source_type column with default "document" for existing rows
    op.add_column(
        'ontology_concepts',
        sa.Column('source_type', sa.String(20), nullable=False, server_default='document')
    )
    op.create_index('ix_ontology_concepts_source_type', 'ontology_concepts', ['source_type'])


def downgrade() -> None:
    op.drop_index('ix_ontology_concepts_source_type', table_name='ontology_concepts')
    op.drop_column('ontology_concepts', 'source_type')
