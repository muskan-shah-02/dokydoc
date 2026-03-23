"""Sprint 1: Multi-tenancy and cost tracking

Revision ID: c8f2a1d9e321
Revises: None
Create Date: 2026-01-14 10:00:00.000000

This migration adds:
1. tenant_id to all tables for multi-tenancy support
2. Cost tracking fields to documents table
3. New tenant_billing table for per-tenant billing

SPRINT 2 Phase 8: Fixed down_revision to None (this is the base migration)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c8f2a1d9e321'
down_revision: Union[str, None] = None  # SPRINT 2 Phase 8: This is the base migration
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Apply Sprint 1 database changes:
    - Add tenant_id to all tables with default value 1
    - Add cost tracking fields to documents
    - Create tenant_billing table
    """

    # =================================================================
    # PHASE 1: Add tenant_id column to ALL tables
    # =================================================================

    tables_to_update = [
        'users',
        'documents',
        'code_components',
        'mismatches',
        'document_segments',
        'analysisresult',
        'document_code_links',
        'initiatives',
        'initiative_assets',
        'ontology_concepts',
        'ontology_relationships',
        'analysis_runs',
        'consolidated_analyses'  # Fixed: was 'consolidated_analysis'
    ]

    for table in tables_to_update:
        # Add tenant_id column with default value 1 (nullable first)
        op.add_column(table, sa.Column('tenant_id', sa.Integer(), nullable=True))

        # Set default value for existing rows
        op.execute(f"UPDATE {table} SET tenant_id = 1 WHERE tenant_id IS NULL")

        # Make column NOT NULL after population
        op.alter_column(table, 'tenant_id', nullable=False)

        # Add index for query performance
        op.create_index(f'ix_{table}_tenant_id', table, ['tenant_id'])

    # =================================================================
    # PHASE 2: Add cost tracking fields to documents table
    # =================================================================

    # Add cost tracking columns (nullable first)
    op.add_column('documents', sa.Column('ai_cost_inr', sa.Numeric(precision=10, scale=4), nullable=True))
    op.add_column('documents', sa.Column('token_count_input', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('token_count_output', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('cost_breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Set default values for existing documents
    op.execute("UPDATE documents SET ai_cost_inr = 0.0 WHERE ai_cost_inr IS NULL")
    op.execute("UPDATE documents SET token_count_input = 0 WHERE token_count_input IS NULL")
    op.execute("UPDATE documents SET token_count_output = 0 WHERE token_count_output IS NULL")

    # Make required columns NOT NULL after population
    op.alter_column('documents', 'ai_cost_inr', nullable=False)
    op.alter_column('documents', 'token_count_input', nullable=False)
    op.alter_column('documents', 'token_count_output', nullable=False)

    # =================================================================
    # PHASE 3: Create tenant_billing table
    # =================================================================

    op.create_table('tenant_billing',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('billing_type', sa.String(), nullable=False),
        sa.Column('balance_inr', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('low_balance_threshold', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('current_month_cost', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('last_30_days_cost', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('monthly_limit_inr', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_billing_reset', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Add unique constraint on tenant_id
    op.create_unique_constraint('uq_tenant_billing_tenant_id', 'tenant_billing', ['tenant_id'])

    # Add index for fast lookups
    op.create_index('ix_tenant_billing_tenant_id', 'tenant_billing', ['tenant_id'])

    # Create default tenant billing record for tenant_id = 1
    op.execute("""
        INSERT INTO tenant_billing (
            tenant_id, billing_type, balance_inr, low_balance_threshold,
            current_month_cost, last_30_days_cost, created_at, updated_at
        )
        VALUES (
            1, 'postpaid', 0.0, 100.0, 0.0, 0.0, NOW(), NOW()
        )
    """)


def downgrade() -> None:
    """
    Rollback Sprint 1 changes
    """

    # Drop tenant_billing table
    op.drop_index('ix_tenant_billing_tenant_id', 'tenant_billing')
    op.drop_constraint('uq_tenant_billing_tenant_id', 'tenant_billing', type_='unique')
    op.drop_table('tenant_billing')

    # Remove cost tracking fields from documents
    op.drop_column('documents', 'cost_breakdown')
    op.drop_column('documents', 'token_count_output')
    op.drop_column('documents', 'token_count_input')
    op.drop_column('documents', 'ai_cost_inr')

    # Remove tenant_id from all tables
    tables_to_revert = [
        'consolidated_analyses',  # Fixed: was 'consolidated_analysis'
        'analysis_runs',
        'ontology_relationships',
        'ontology_concepts',
        'initiative_assets',
        'initiatives',
        'document_code_links',
        'analysisresult',
        'document_segments',
        'mismatches',
        'code_components',
        'documents',
        'users'
    ]

    for table in tables_to_revert:
        op.drop_index(f'ix_{table}_tenant_id', table)
        op.drop_column(table, 'tenant_id')
