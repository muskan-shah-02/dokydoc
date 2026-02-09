"""Sprint 3: Add repositories table and code_component.repository_id FK

Revision ID: s3a1_repositories
Revises: f1a2b3c4d5e6
Create Date: 2026-02-07 10:00:00.000000

SPRINT 3 (ARCH-04): Creates the Repository model for scalable code analysis.
Adds a nullable repository_id FK to code_components to link files to repos.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 's3a1_repositories'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guard against table already existing
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'repositories')"
    ))
    if result.scalar():
        return

    # Create repositories table
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

    # Add composite index for tenant isolation
    op.create_index('ix_repositories_tenant_id_id', 'repositories', ['tenant_id', 'id'])

    # Add repository_id FK to code_components (nullable — existing components have no repo)
    op.add_column('code_components', sa.Column('repository_id', sa.Integer(), nullable=True))
    op.create_index('ix_code_components_repository_id', 'code_components', ['repository_id'])
    op.create_foreign_key(
        'fk_code_components_repository_id',
        'code_components', 'repositories',
        ['repository_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_code_components_repository_id', 'code_components', type_='foreignkey')
    op.drop_index('ix_code_components_repository_id', table_name='code_components')
    op.drop_column('code_components', 'repository_id')
    op.drop_index('ix_repositories_tenant_id_id', table_name='repositories')
    op.drop_table('repositories')
