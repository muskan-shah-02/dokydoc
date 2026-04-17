"""P5C-06: Add ci_webhook_configs table for CI test result webhook integration.

Revision ID: s17f1
Revises: s17e1
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa

revision = 's17f1'
down_revision = 's17e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ci_webhook_configs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.Integer,
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                  nullable=False, unique=True),
        sa.Column('webhook_secret', sa.String(64), nullable=False),
        sa.Column('document_id', sa.Integer,
                  sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_ci_webhook_tenant', 'ci_webhook_configs', ['tenant_id'])


def downgrade():
    op.drop_index('ix_ci_webhook_tenant', table_name='ci_webhook_configs')
    op.drop_table('ci_webhook_configs')
