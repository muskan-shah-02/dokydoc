"""Reset tenants_id_seq after explicit id=1 insert in Sprint 2 migration

Revision ID: s21a1
Revises: s20a1
Create Date: 2026-04-29

The Sprint 2 migration inserted a default tenant row with explicit id=1 but
never called setval, leaving the tenants_id_seq at 1. Every subsequent
tenant registration failed with "duplicate key value violates unique constraint
tenants_pkey" because nextval still returned 1.
"""
from alembic import op

revision = 's21a1'
down_revision = 's20a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "SELECT setval('tenants_id_seq', COALESCE((SELECT MAX(id) FROM tenants), 1))"
    )


def downgrade() -> None:
    pass
