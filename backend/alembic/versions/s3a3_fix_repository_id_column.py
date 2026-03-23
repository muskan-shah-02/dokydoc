"""Fix: ensure repository_id column exists on code_components

Revision ID: s3a3_fix_repo_id
Revises: s3a2_concept_mapping
Create Date: 2026-02-11 21:30:00.000000

The s3a1_repositories migration had a guard that skipped adding repository_id
if the repositories table already existed. This migration fixes that gap by
adding the column if it's still missing.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 's3a3_fix_repo_id'
down_revision: Union[str, None] = 's3a2_concept_mapping'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check if repositories table exists, create if not
    tbl_result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'repositories')"
    ))
    if not tbl_result.scalar():
        op.create_table(
            'repositories',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(), nullable=False, index=True),
            sa.Column('name', sa.String(255), nullable=False, index=True),
            sa.Column('url', sa.String(1024), nullable=False),
            sa.Column('default_branch', sa.String(100), nullable=False, server_default='main'),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('analysis_status', sa.String(50), nullable=False, server_default='pending', index=True),
            sa.Column('last_analyzed_commit', sa.String(100), nullable=True),
            sa.Column('total_files', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('analyzed_files', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_repositories_tenant_id_id', 'repositories', ['tenant_id', 'id'])

    # Add repository_id column if it doesn't exist
    col_result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.columns "
        "WHERE table_name = 'code_components' AND column_name = 'repository_id')"
    ))
    if not col_result.scalar():
        op.add_column('code_components', sa.Column('repository_id', sa.Integer(), nullable=True))
        op.create_index('ix_code_components_repository_id', 'code_components', ['repository_id'])
        op.create_foreign_key(
            'fk_code_components_repository_id',
            'code_components', 'repositories',
            ['repository_id'], ['id'],
            ondelete='SET NULL'
        )


def downgrade() -> None:
    conn = op.get_bind()
    col_result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.columns "
        "WHERE table_name = 'code_components' AND column_name = 'repository_id')"
    ))
    if col_result.scalar():
        op.drop_constraint('fk_code_components_repository_id', 'code_components', type_='foreignkey')
        op.drop_index('ix_code_components_repository_id', table_name='code_components')
        op.drop_column('code_components', 'repository_id')
