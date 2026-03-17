"""Add notification_preferences table

Revision ID: s8a4_add_notification_preferences
Revises: s8a3_add_document_versions
Create Date: 2026-03-17

"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "s8a4_add_notification_preferences"
down_revision: Union[str, tuple] = "s8a3_add_document_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("analysis_complete", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("analysis_failed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("validation_alert", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("mention", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("system", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])
    op.create_index("ix_notification_preferences_tenant_id", "notification_preferences", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_preferences_tenant_id", table_name="notification_preferences")
    op.drop_index("ix_notification_preferences_user_id", table_name="notification_preferences")
    op.drop_table("notification_preferences")
