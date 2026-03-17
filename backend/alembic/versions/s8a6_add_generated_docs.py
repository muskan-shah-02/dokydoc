"""Add generated_docs table

Revision ID: s8a6_add_generated_docs
Revises: s8a5_add_api_keys
Create Date: 2026-03-17

"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "s8a6_add_generated_docs"
down_revision: Union[str, tuple] = "s8a5_add_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generated_docs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(500), nullable=True),
        sa.Column("doc_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_generated_docs_tenant_id", "generated_docs", ["tenant_id"])
    op.create_index("ix_generated_docs_doc_type", "generated_docs", ["doc_type"])


def downgrade() -> None:
    op.drop_index("ix_generated_docs_doc_type", table_name="generated_docs")
    op.drop_index("ix_generated_docs_tenant_id", table_name="generated_docs")
    op.drop_table("generated_docs")
