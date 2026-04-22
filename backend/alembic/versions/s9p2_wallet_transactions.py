"""Phase 9: Create wallet_transactions table for prepaid credit history.

Revision ID: s9p2
Revises: s9p1
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = 's9p2'
down_revision = 's9p1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'wallet_transactions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.Integer,
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                  nullable=False),
        # credit | debit | refund | signup_bonus
        sa.Column('txn_type', sa.String(30), nullable=False),
        sa.Column('amount_inr', sa.Numeric(12, 4), nullable=False),
        sa.Column('balance_after_inr', sa.Numeric(12, 4), nullable=False),
        # Linked usage_log entry for debit transactions
        sa.Column('usage_log_id', sa.Integer,
                  sa.ForeignKey('usage_logs.id', ondelete='SET NULL'),
                  nullable=True),
        # Payment gateway reference for credit/topup transactions
        sa.Column('razorpay_payment_id', sa.String(200), nullable=True),
        sa.Column('razorpay_order_id', sa.String(200), nullable=True),
        # Human-readable description
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_by_user_id', sa.Integer,
                  sa.ForeignKey('users.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_wallet_transactions_tenant_id', 'wallet_transactions', ['tenant_id'])
    op.create_index('ix_wallet_transactions_created_at', 'wallet_transactions', ['created_at'])
    op.create_check_constraint(
        'ck_wallet_txn_type',
        'wallet_transactions',
        "txn_type IN ('credit', 'debit', 'refund', 'signup_bonus')"
    )


def downgrade() -> None:
    op.drop_table('wallet_transactions')
