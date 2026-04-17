"""P5C-04: Add uat_checklist_items table for manual UAT tracking.

Revision ID: s17e1
Revises: s17d1
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa

revision = 's17e1'
down_revision = 's17d1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'uat_checklist_items',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.Integer, nullable=False, index=True),
        sa.Column('document_id', sa.Integer,
                  sa.ForeignKey('documents.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('atom_id', sa.Integer,
                  sa.ForeignKey('requirement_atoms.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('checked_by_user_id', sa.Integer,
                  sa.ForeignKey('users.id'), nullable=True),
        sa.Column('checked_at', sa.DateTime, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('result', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_uat_checklist_document_id', 'uat_checklist_items', ['document_id'])
    op.create_check_constraint(
        'ck_uat_result',
        'uat_checklist_items',
        "result IS NULL OR result IN ('pass', 'fail', 'blocked')"
    )


def downgrade():
    op.drop_table('uat_checklist_items')
