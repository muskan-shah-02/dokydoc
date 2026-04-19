"""Add document_versions table

Revision ID: s8a3_add_document_versions
Revises: s8a2_merge_heads
Create Date: 2026-03-17

"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "s8a3_add_document_versions"
down_revision: Union[str, tuple] = "s8a2_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("original_filename", sa.String(512), nullable=True),
        sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_index("ix_document_versions_tenant_id", "document_versions", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_document_versions_tenant_id", table_name="document_versions")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
