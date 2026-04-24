"""Merge all heads into a single linear head

Revision ID: s20a1
Revises: s19a1, s9p4, fc8619cf3d6f
Create Date: 2026-04-24

Merges:
  - s19a1  (Phase 3 data-flow edge columns)
  - s9p4   (Phase 9 enterprise contact requests)
  - fc8619cf3d6f (no-op initial_schema placeholder)
"""
from alembic import op

revision = 's20a1'
down_revision = ('s19a1', 's9p4', 'fc8619cf3d6f')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
