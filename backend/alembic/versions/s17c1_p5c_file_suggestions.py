"""P5C-01: Add file_suggestions table, testability col on atoms, file_suggestion_summary on documents.

Revision ID: s17c1
Revises: s17b1
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = 's17c1'
down_revision = 's17b1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'file_suggestions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.Integer, nullable=False, index=True),
        sa.Column('document_id', sa.Integer,
                  sa.ForeignKey('documents.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('suggested_filename', sa.String(500), nullable=False),
        sa.Column('reason', sa.Text, nullable=False),
        sa.Column('atom_ids', ARRAY(sa.Integer), nullable=False, server_default='{}'),
        sa.Column('atom_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('fulfilled_by_component_id', sa.Integer,
                  sa.ForeignKey('code_components.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_file_suggestions_document_id', 'file_suggestions', ['document_id'])

    # testability: "static" | "runtime" | "manual" — classified during atomization
    op.add_column('requirement_atoms',
        sa.Column('testability', sa.String(20), nullable=True))

    # Summary JSONB cached on document for fast dashboard access
    op.add_column('documents',
        sa.Column('file_suggestion_summary', JSONB, nullable=True))


def downgrade():
    op.drop_column('documents', 'file_suggestion_summary')
    op.drop_column('requirement_atoms', 'testability')
    op.drop_index('ix_file_suggestions_document_id', table_name='file_suggestions')
    op.drop_table('file_suggestions')
