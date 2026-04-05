"""Create training_examples table for data flywheel

Revision ID: s12a1
Revises: s11b1
Create Date: 2026-04-05

Purpose: Captures every AI judgment + human correction for future fine-tuning.
This data is critical — it cannot be recovered retroactively.
"""
import sqlalchemy as sa
from alembic import op

revision = 's12a1'
down_revision = 's11b1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type first
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE feedback_source_enum AS ENUM ('accept', 'reject', 'edit', 'auto');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.create_table(
        'training_examples',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_type', sa.String(64), nullable=False),
        sa.Column('input_text', sa.Text(), nullable=False),
        sa.Column('ai_output', sa.Text(), nullable=False),
        sa.Column('ai_confidence', sa.Float(), nullable=True),
        sa.Column('model_name', sa.String(128), nullable=True),
        sa.Column('human_label', sa.Text(), nullable=True),
        sa.Column('feedback_source', sa.Enum('accept', 'reject', 'edit', 'auto', name='feedback_source_enum'), nullable=False, server_default='auto'),
        sa.Column('feedback_at', sa.DateTime(), nullable=True),
        sa.Column('reviewer_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_mismatch_id', sa.Integer(), sa.ForeignKey('mismatches.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('idx_training_examples_tenant_task', 'training_examples', ['tenant_id', 'task_type'])
    op.create_index('idx_training_examples_feedback_source', 'training_examples', ['feedback_source'])
    op.create_index('idx_training_examples_created_at', 'training_examples', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_training_examples_created_at', table_name='training_examples')
    op.drop_index('idx_training_examples_feedback_source', table_name='training_examples')
    op.drop_index('idx_training_examples_tenant_task', table_name='training_examples')
    op.drop_table('training_examples')
    op.execute("DROP TYPE IF EXISTS feedback_source_enum;")
