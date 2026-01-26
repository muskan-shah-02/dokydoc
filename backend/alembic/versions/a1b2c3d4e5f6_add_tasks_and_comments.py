"""Add tasks and task_comments tables

Sprint 2 Extended - Phase 10: Tasks Feature

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-01-25 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'  # Previous migration (composite indexes)
branch_labels = None
depends_on = None


def upgrade():
    """Create tasks and task_comments tables."""

    # Create TaskStatus enum
    task_status_enum = postgresql.ENUM(
        'backlog', 'todo', 'in_progress', 'in_review', 'done', 'blocked', 'cancelled',
        name='taskstatus',
        create_type=False
    )
    task_status_enum.create(op.get_bind(), checkfirst=True)

    # Create TaskPriority enum
    task_priority_enum = postgresql.ENUM(
        'critical', 'high', 'medium', 'low',
        name='taskpriority',
        create_type=False
    )
    task_priority_enum.create(op.get_bind(), checkfirst=True)

    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM(
            'backlog', 'todo', 'in_progress', 'in_review', 'done', 'blocked', 'cancelled',
            name='taskstatus',
            create_type=False
        ), nullable=False, server_default='todo'),
        sa.Column('priority', postgresql.ENUM(
            'critical', 'high', 'medium', 'low',
            name='taskpriority',
            create_type=False
        ), nullable=False, server_default='medium'),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('assigned_to_id', sa.Integer(), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('code_component_id', sa.Integer(), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('estimated_hours', sa.Integer(), nullable=True),
        sa.Column('actual_hours', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['code_component_id'], ['code_components.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for tasks table
    op.create_index('ix_tasks_id', 'tasks', ['id'], unique=False)
    op.create_index('ix_tasks_tenant_id', 'tasks', ['tenant_id'], unique=False)
    op.create_index('ix_tasks_title', 'tasks', ['title'], unique=False)
    op.create_index('ix_tasks_status', 'tasks', ['status'], unique=False)
    op.create_index('ix_tasks_priority', 'tasks', ['priority'], unique=False)
    op.create_index('ix_tasks_assigned_to_id', 'tasks', ['assigned_to_id'], unique=False)
    op.create_index('ix_tasks_document_id', 'tasks', ['document_id'], unique=False)
    op.create_index('ix_tasks_code_component_id', 'tasks', ['code_component_id'], unique=False)
    op.create_index('ix_tasks_due_date', 'tasks', ['due_date'], unique=False)

    # Create composite index for tenant-scoped queries (security + performance)
    op.create_index('idx_tasks_tenant_id_id', 'tasks', ['tenant_id', 'id'], unique=False)

    # Create task_comments table
    op.create_table(
        'task_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('is_edited', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for task_comments table
    op.create_index('ix_task_comments_id', 'task_comments', ['id'], unique=False)
    op.create_index('ix_task_comments_task_id', 'task_comments', ['task_id'], unique=False)
    op.create_index('ix_task_comments_tenant_id', 'task_comments', ['tenant_id'], unique=False)

    # Create composite index for tenant-scoped queries
    op.create_index('idx_task_comments_tenant_id_id', 'task_comments', ['tenant_id', 'id'], unique=False)


def downgrade():
    """Drop tasks and task_comments tables."""

    # Drop task_comments table and indexes
    op.drop_index('idx_task_comments_tenant_id_id', table_name='task_comments')
    op.drop_index('ix_task_comments_tenant_id', table_name='task_comments')
    op.drop_index('ix_task_comments_task_id', table_name='task_comments')
    op.drop_index('ix_task_comments_id', table_name='task_comments')
    op.drop_table('task_comments')

    # Drop tasks table and indexes
    op.drop_index('idx_tasks_tenant_id_id', table_name='tasks')
    op.drop_index('ix_tasks_due_date', table_name='tasks')
    op.drop_index('ix_tasks_code_component_id', table_name='tasks')
    op.drop_index('ix_tasks_document_id', table_name='tasks')
    op.drop_index('ix_tasks_assigned_to_id', table_name='tasks')
    op.drop_index('ix_tasks_priority', table_name='tasks')
    op.drop_index('ix_tasks_status', table_name='tasks')
    op.drop_index('ix_tasks_title', table_name='tasks')
    op.drop_index('ix_tasks_tenant_id', table_name='tasks')
    op.drop_index('ix_tasks_id', table_name='tasks')
    op.drop_table('tasks')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS taskpriority')
    op.execute('DROP TYPE IF EXISTS taskstatus')
