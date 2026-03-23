"""Add integration_configs table

Revision ID: s8a7_add_integration_configs
Revises: s8a6_add_generated_docs
Create Date: 2026-03-17

"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "s8a7_add_integration_configs"
down_revision: Union[str, tuple] = "s8a6_add_generated_docs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("workspace_name", sa.String(200), nullable=True),
        sa.Column("workspace_id", sa.String(200), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_integration_configs_tenant_id", "integration_configs", ["tenant_id"])
    op.create_index("ix_integration_configs_provider", "integration_configs", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_integration_configs_provider", table_name="integration_configs")
    op.drop_index("ix_integration_configs_tenant_id", table_name="integration_configs")
    op.drop_table("integration_configs")
