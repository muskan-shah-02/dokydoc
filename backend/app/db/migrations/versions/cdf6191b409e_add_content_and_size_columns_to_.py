"""Add content and size columns to documents

Revision ID: cdf6191b409e
Revises: 30a181807d1e
Create Date: 2025-07-02 17:11:32.518489

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'cdf6191b409e'
down_revision = '30a181807d1e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check if documents table exists
    if 'documents' in inspector.get_table_names():
        # Get existing columns
        existing_columns = [col['name'] for col in inspector.get_columns('documents')]
        
        # Add columns only if they don't exist
        if 'file_size_kb' not in existing_columns:
            op.add_column('documents', sa.Column('file_size_kb', sa.Integer(), nullable=True))
        
        if 'content' not in existing_columns:
            op.add_column('documents', sa.Column('content', sa.Text(), nullable=True))


def downgrade() -> None:
    # Get connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check if documents table exists
    if 'documents' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('documents')]
        
        # Drop columns only if they exist
        if 'content' in existing_columns:
            op.drop_column('documents', 'content')
        if 'file_size_kb' in existing_columns:
            op.drop_column('documents', 'file_size_kb')
