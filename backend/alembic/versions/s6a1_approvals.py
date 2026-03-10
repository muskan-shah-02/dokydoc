"""Create approvals table

Revision ID: s6a1_approvals
Revises: s5b1_mapping_feedback
Create Date: 2026-03-10 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "s6a1_approvals"
down_revision: Union[str, None] = "s5b1_mapping_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("entity_type", sa.String(50), nullable=False, index=True),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("entity_name", sa.String(500), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending", index=True),
        sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requested_by_email", sa.String(255), nullable=True),
        sa.Column("resolved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_by_email", sa.String(255), nullable=True),
        sa.Column("approval_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("request_notes", sa.Text(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    # Composite index for common queries
    op.create_index(
        "ix_approvals_tenant_status",
        "approvals",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_approvals_entity",
        "approvals",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_approvals_entity", table_name="approvals")
    op.drop_index("ix_approvals_tenant_status", table_name="approvals")
    op.drop_table("approvals")
