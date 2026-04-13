"""P5-01: Add GIN index on tenants.settings JSONB for industry-aware prompt injection

Revision ID: s15a1
Revises: s14b1
Create Date: 2026-04-13

Purpose:
  Phase 5 — Industry-Aware Prompt Injection.

  The prompt injection system reads tenant.settings frequently to determine:
    - settings["industry"]          → which context library to load
    - settings["glossary"]          → custom term overrides
    - settings["regulatory_context"] → applicable regulations

  Without an index, every Gemini call that reads tenant context does a full
  table scan on `tenants`. The GIN index makes JSONB path lookups O(log n).

  Also documents the Phase 5 settings schema as a comment — the JSON column
  is schema-free, so the constraint lives here for reference.

Phase 5 settings schema:
  {
    "industry": "fintech/payments",      # industry slug
    "sub_domain": "lending",             # optional sub-specialization
    "company_website": "https://...",    # for auto-detection
    "glossary": {"term": "definition"},  # tenant overrides
    "regulatory_context": ["PCI-DSS"],   # applicable regs
    "onboarding_complete": false,        # wizard completion flag
    "pending_glossary_confirmations": [] # terms awaiting review
  }
"""
from alembic import op
import sqlalchemy as sa

revision = 's15a1'
down_revision = 's14b1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # GIN index on tenants.settings using jsonb_path_ops operator class.
    # jsonb_path_ops supports @>, @?, @@ operators — fastest for key existence checks.
    # CONCURRENTLY means no table lock during index build (safe on live DB).
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_tenants_settings_gin
        ON tenants
        USING GIN (settings jsonb_path_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tenants_settings_gin")
