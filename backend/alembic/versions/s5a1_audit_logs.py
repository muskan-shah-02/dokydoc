"""Create audit_logs table for activity tracking

Revision ID: s5a1_audit_logs
Revises: s4b2_requirement_traces
Create Date: 2026-03-09 10:00:00.000000

Adds audit_logs table for tracking all user and system actions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "s5a1_audit_logs"
down_revision: Union[str, None] = "s4b2_requirement_traces"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "audit_logs" not in existing_tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
            sa.Column("user_email", sa.String(255), nullable=True),
            sa.Column("action", sa.String(50), nullable=False, index=True),
            sa.Column("resource_type", sa.String(50), nullable=False, index=True),
            sa.Column("resource_id", sa.Integer(), nullable=True),
            sa.Column("resource_name", sa.String(500), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="success"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        # Composite index for common queries
        op.create_index(
            "ix_audit_logs_tenant_created",
            "audit_logs",
            ["tenant_id", "created_at"],
        )
        op.create_index(
            "ix_audit_logs_tenant_resource",
            "audit_logs",
            ["tenant_id", "resource_type", "action"],
        )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_tenant_resource", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_created", table_name="audit_logs")
    op.drop_table("audit_logs")
