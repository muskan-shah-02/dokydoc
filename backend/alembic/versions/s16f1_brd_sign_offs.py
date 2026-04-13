"""
P5B-12: Create brd_sign_offs table for BA sign-off workflow + compliance certificate.

Revision ID: s16f1
Revises: s16b1
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 's16f1'
down_revision = 's16b1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'brd_sign_offs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('document_version_id', sa.Integer(), nullable=True),
        sa.Column('repository_id', sa.Integer(), nullable=True),
        sa.Column('signed_by_user_id', sa.Integer(), nullable=False),
        sa.Column('signed_at', sa.DateTime(), nullable=False),
        sa.Column('compliance_score_at_signoff', sa.Float(), nullable=True),
        sa.Column('open_mismatches_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('critical_mismatches_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('acknowledged_mismatch_ids', postgresql.JSONB(), nullable=True),
        sa.Column('sign_off_notes', sa.Text(), nullable=True),
        sa.Column('has_unresolved_critical', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('certificate_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['signed_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_brd_sign_offs_tenant_id', 'brd_sign_offs', ['tenant_id'])
    op.create_index('ix_brd_sign_offs_document_id', 'brd_sign_offs', ['document_id'])


def downgrade():
    op.drop_index('ix_brd_sign_offs_document_id')
    op.drop_index('ix_brd_sign_offs_tenant_id')
    op.drop_table('brd_sign_offs')
