"""Add feedback_rating column to chat_messages table

Revision ID: s7a3_message_feedback
Revises: s7a2_model_preference
Create Date: 2026-03-12 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "s7a3_message_feedback"
down_revision: Union[str, None] = "s7a2_model_preference"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("feedback_rating", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "feedback_rating")
