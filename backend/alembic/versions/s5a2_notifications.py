"""Create notifications table for in-app notifications

Revision ID: s5a2_notifications
Revises: s5a1_audit_logs
Create Date: 2026-03-09 10:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "s5a2_notifications"
down_revision: Union[str, None] = "s5a1_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "notifications" not in existing_tables:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("notification_type", sa.String(50), nullable=False, index=True),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("resource_type", sa.String(50), nullable=True),
            sa.Column("resource_id", sa.Integer(), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("email_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("read_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_notifications_user_unread",
            "notifications",
            ["user_id", "is_read"],
        )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_table("notifications")
