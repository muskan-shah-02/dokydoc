"""P5C-08: Add compliance_score_snapshots table for trend tracking.

Revision ID: s17g1
Revises: s17f1
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa

revision = 's17g1'
down_revision = 's17f1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'compliance_score_snapshots',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.Integer, nullable=False, index=True),
        sa.Column('document_id', sa.Integer,
                  sa.ForeignKey('documents.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('score_percentage', sa.Float, nullable=False),
        sa.Column('total_atoms', sa.Integer, nullable=False, default=0),
        sa.Column('covered_atoms', sa.Integer, nullable=False, default=0),
        sa.Column('open_mismatches', sa.Integer, nullable=False, default=0),
        sa.Column('critical_mismatches', sa.Integer, nullable=False, default=0),
        sa.Column('snapshot_date', sa.Date, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        'ix_compliance_snapshots_document_date',
        'compliance_score_snapshots', ['document_id', 'snapshot_date'],
        unique=True,
    )
    op.create_index(
        'ix_compliance_snapshots_tenant',
        'compliance_score_snapshots', ['tenant_id', 'snapshot_date'],
    )


def downgrade():
    op.drop_index('ix_compliance_snapshots_tenant', table_name='compliance_score_snapshots')
    op.drop_index('ix_compliance_snapshots_document_date', table_name='compliance_score_snapshots')
    op.drop_table('compliance_score_snapshots')
