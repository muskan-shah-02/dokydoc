"""P5C-03: Add mismatch_clarifications table for BA ↔ Developer clarification workflow.

Revision ID: s17d1
Revises: s17c1
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa

revision = 's17d1'
down_revision = 's17c1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'mismatch_clarifications',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.Integer, nullable=False, index=True),
        sa.Column('mismatch_id', sa.Integer,
                  sa.ForeignKey('mismatches.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('requested_by_user_id', sa.Integer,
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('assignee_user_id', sa.Integer,
                  sa.ForeignKey('users.id'), nullable=True),
        sa.Column('question', sa.Text, nullable=False),
        sa.Column('answer', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('answered_at', sa.DateTime, nullable=True),
        sa.Column('closed_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_mismatch_clarifications_mismatch_id', 'mismatch_clarifications', ['mismatch_id'])
    op.create_check_constraint(
        'ck_clarification_status',
        'mismatch_clarifications',
        "status IN ('open', 'answered', 'closed')"
    )


def downgrade():
    op.drop_table('mismatch_clarifications')
