"""Phase 9: Add markup transparency columns to usage_logs.

Revision ID: s9p3
Revises: s9p2
Create Date: 2026-04-22
"""
from alembic import op

revision = 's9p3'
down_revision = 's9p2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Raw cost before markup (what Google/Anthropic charged)
    op.execute("ALTER TABLE usage_logs ADD COLUMN IF NOT EXISTS raw_cost_inr NUMERIC(12,4) NULL")
    # Markup amount (15% of raw_cost_inr)
    op.execute("ALTER TABLE usage_logs ADD COLUMN IF NOT EXISTS markup_inr NUMERIC(12,4) NULL")
    # Markup percentage applied (stored for auditability — rate may change over time)
    op.execute("ALTER TABLE usage_logs ADD COLUMN IF NOT EXISTS markup_percent NUMERIC(5,2) NULL")
    # Thinking tokens (separate from output for accurate billing)
    op.execute("ALTER TABLE usage_logs ADD COLUMN IF NOT EXISTS thinking_tokens INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE usage_logs DROP COLUMN IF EXISTS thinking_tokens")
    op.execute("ALTER TABLE usage_logs DROP COLUMN IF EXISTS markup_percent")
    op.execute("ALTER TABLE usage_logs DROP COLUMN IF EXISTS markup_inr")
    op.execute("ALTER TABLE usage_logs DROP COLUMN IF EXISTS raw_cost_inr")
