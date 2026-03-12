"""Add model_preference column to conversations table

Revision ID: s7a2_model_preference
Revises: s7a1_conversations
Create Date: 2026-03-12 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "s7a2_model_preference"
down_revision: Union[str, None] = "s7a1_conversations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("model_preference", sa.String(50), nullable=False, server_default="gemini"),
    )


def downgrade() -> None:
    op.drop_column("conversations", "model_preference")
