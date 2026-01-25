"""Add composite indexes for security and performance

Revision ID: f1a2b3c4d5e6
Revises: b342e208f554
Create Date: 2026-01-25 18:30:00.000000

This migration adds composite indexes on (tenant_id, id) for key tables.
This prevents timing attacks and improves query performance for tenant-scoped lookups.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'b342e208f554'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add composite indexes for tenant-scoped queries.
    
    These indexes serve two purposes:
    1. Security: Prevent timing attacks by ensuring consistent query performance
    2. Performance: Speed up tenant-scoped lookups (tenant_id, id)
    """
    
    # Documents table
    op.create_index(
        'idx_documents_tenant_id_id',
        'documents',
        ['tenant_id', 'id'],
        unique=False
    )
    
    # Code components table
    op.create_index(
        'idx_code_components_tenant_id_id',
        'code_components',
        ['tenant_id', 'id'],
        unique=False
    )
    
    # Users table
    op.create_index(
        'idx_users_tenant_id_id',
        'users',
        ['tenant_id', 'id'],
        unique=False
    )
    
    # Analysis results table
    op.create_index(
        'idx_analysisresult_tenant_id_id',
        'analysisresult',
        ['tenant_id', 'id'],
        unique=False
    )
    
    # Document segments table
    op.create_index(
        'idx_document_segments_tenant_id_id',
        'document_segments',
        ['tenant_id', 'id'],
        unique=False
    )
    
    # Mismatches table
    op.create_index(
        'idx_mismatches_tenant_id_id',
        'mismatches',
        ['tenant_id', 'id'],
        unique=False
    )
    
    # Document code links table
    op.create_index(
        'idx_document_code_links_tenant_id_id',
        'document_code_links',
        ['tenant_id', 'id'],
        unique=False
    )


def downgrade() -> None:
    """Remove composite indexes."""
    
    op.drop_index('idx_document_code_links_tenant_id_id', table_name='document_code_links')
    op.drop_index('idx_mismatches_tenant_id_id', table_name='mismatches')
    op.drop_index('idx_document_segments_tenant_id_id', table_name='document_segments')
    op.drop_index('idx_analysisresult_tenant_id_id', table_name='analysisresult')
    op.drop_index('idx_users_tenant_id_id', table_name='users')
    op.drop_index('idx_code_components_tenant_id_id', table_name='code_components')
    op.drop_index('idx_documents_tenant_id_id', table_name='documents')
