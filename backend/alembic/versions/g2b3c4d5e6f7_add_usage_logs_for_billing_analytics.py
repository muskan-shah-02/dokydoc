"""Add usage_logs table for billing analytics

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-02-06 10:00:00.000000

This migration adds the usage_logs table for comprehensive billing analytics.
Enables tracking of:
- AI API calls by feature type (document analysis, code analysis, validation, etc.)
- Token usage (input/output) per operation
- Cost breakdown by feature and time period
- Per-document and aggregate analytics
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'g2b3c4d5e6f7'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create usage_logs table for billing analytics."""

    op.create_table(
        'usage_logs',
        # Primary key
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),

        # Tenant isolation (required)
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False, index=True),

        # User who triggered the action (optional)
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),

        # Document reference (optional)
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id'), nullable=True, index=True),

        # Feature and operation classification
        sa.Column('feature_type', sa.String(50), nullable=False, index=True),
        sa.Column('operation', sa.String(50), nullable=False, index=True),

        # Model information
        sa.Column('model_used', sa.String(100), nullable=False, default='gemini-2.5-flash'),

        # Token counts
        sa.Column('input_tokens', sa.Integer(), nullable=False, default=0),
        sa.Column('output_tokens', sa.Integer(), nullable=False, default=0),
        sa.Column('cached_tokens', sa.Integer(), nullable=False, default=0),

        # Cost tracking (USD with 6 decimal places, INR with 4)
        sa.Column('cost_usd', sa.Numeric(12, 6), nullable=False, default=0.0),
        sa.Column('cost_inr', sa.Numeric(12, 4), nullable=False, default=0.0),

        # Processing time in seconds
        sa.Column('processing_time_seconds', sa.Numeric(10, 2), nullable=True),

        # Additional data (JSON) - named 'extra_data' since 'metadata' is reserved by SQLAlchemy
        sa.Column('extra_data', sa.JSON(), nullable=True),

        # Timestamp (indexed for time-based queries)
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True, server_default=sa.func.now()),
    )

    # Create composite indexes for common query patterns
    # 1. Tenant + time range queries (most common)
    op.create_index(
        'idx_usage_logs_tenant_created',
        'usage_logs',
        ['tenant_id', 'created_at'],
        unique=False
    )

    # 2. Feature-based analytics
    op.create_index(
        'idx_usage_logs_tenant_feature',
        'usage_logs',
        ['tenant_id', 'feature_type', 'created_at'],
        unique=False
    )

    # 3. Document-specific analytics
    op.create_index(
        'idx_usage_logs_document',
        'usage_logs',
        ['document_id', 'created_at'],
        unique=False
    )

    # 4. User activity tracking
    op.create_index(
        'idx_usage_logs_user',
        'usage_logs',
        ['user_id', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    """Drop usage_logs table and indexes."""

    # Drop indexes first
    op.drop_index('idx_usage_logs_user', table_name='usage_logs')
    op.drop_index('idx_usage_logs_document', table_name='usage_logs')
    op.drop_index('idx_usage_logs_tenant_feature', table_name='usage_logs')
    op.drop_index('idx_usage_logs_tenant_created', table_name='usage_logs')

    # Drop table
    op.drop_table('usage_logs')
