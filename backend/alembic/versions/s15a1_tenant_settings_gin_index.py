"""P5-01: Add GIN index on tenants.settings JSONB for industry-aware prompt injection

Revision ID: s15a1
Revises: s14b1
Create Date: 2026-04-13
"""
from alembic import op

revision = 's15a1'
down_revision = 's14b1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tenants_settings_gin "
        "ON tenants USING GIN (settings jsonb_path_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tenants_settings_gin")
