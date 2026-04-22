"""Phase 9: Create enterprise_contact_requests table for enterprise sales pipeline.

Revision ID: s9p4
Revises: s9p3
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = 's9p4'
down_revision = 's9p3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'enterprise_contact_requests',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('company_name', sa.String(300), nullable=False),
        sa.Column('contact_name', sa.String(300), nullable=False),
        sa.Column('email', sa.String(300), nullable=False),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('team_size', sa.String(50), nullable=True),   # "1-10", "11-50", "51-200", "200+"
        sa.Column('use_case', sa.Text, nullable=True),
        sa.Column('message', sa.Text, nullable=True),
        # Link to existing tenant if the request came from a logged-in user
        sa.Column('tenant_id', sa.Integer,
                  sa.ForeignKey('tenants.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('submitted_by_user_id', sa.Integer,
                  sa.ForeignKey('users.id', ondelete='SET NULL'),
                  nullable=True),
        # CRM status
        sa.Column('status', sa.String(30), nullable=False, server_default='new'),
        sa.Column('assigned_to', sa.String(200), nullable=True),  # sales rep email
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_enterprise_contact_email', 'enterprise_contact_requests', ['email'])
    op.create_index('ix_enterprise_contact_status', 'enterprise_contact_requests', ['status'])
    op.create_check_constraint(
        'ck_enterprise_contact_status',
        'enterprise_contact_requests',
        "status IN ('new', 'contacted', 'qualified', 'demo_scheduled', 'closed_won', 'closed_lost')"
    )


def downgrade() -> None:
    op.drop_table('enterprise_contact_requests')
