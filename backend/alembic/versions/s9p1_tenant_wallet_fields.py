"""Phase 9: Add wallet fields and preferred_model to tenants table.

Revision ID: s9p1
Revises: s9d1
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = 's9p1'
down_revision = 's9d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Wallet balance (prepaid credit remaining)
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS wallet_balance_inr NUMERIC(12,4) NOT NULL DEFAULT 0.0")
    # Signup free credit (₹100) — tracked separately so we know when it's exhausted
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS wallet_free_credit_inr NUMERIC(12,4) NOT NULL DEFAULT 0.0")
    # Tenant-level preferred model (can be overridden per-document)
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS preferred_model VARCHAR(100) NULL")
    # Razorpay customer ID for Track B payments
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS razorpay_customer_id VARCHAR(200) NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS razorpay_customer_id")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS preferred_model")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS wallet_free_credit_inr")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS wallet_balance_inr")
