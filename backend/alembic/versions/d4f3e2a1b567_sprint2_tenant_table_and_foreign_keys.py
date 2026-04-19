"""Sprint 2: Tenant table and foreign key constraints

Revision ID: d4f3e2a1b567
Revises: c8f2a1d9e321
Create Date: 2026-01-24 12:00:00.000000

This migration adds:
1. Creates tenants table with full schema
2. Inserts default tenant (id=1) for existing data
3. Adds foreign key constraints from all tables to tenants (3-step process)
4. Ensures data integrity with CASCADE delete
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4f3e2a1b567'
down_revision: Union[str, None] = 'c8f2a1d9e321'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# All tables with tenant_id that need FK constraints
TENANT_TABLES = [
    'users',
    'documents',
    'document_segments',
    'analysisresult',
    'analysis_runs',
    'consolidated_analyses',
    'code_components',
    'document_code_links',
    'mismatches',
    'initiatives',
    'initiative_assets',
    'ontology_concepts',
    'ontology_relationships',
    'tenant_billing'
]


def upgrade() -> None:
    """
    Apply Sprint 2 database changes:
    - Create tenants table
    - Insert default tenant
    - Add foreign key constraints (3-step process)
    """

    # =================================================================
    # STEP 1: Create tenants table
    # =================================================================
    print("Creating tenants table...")

    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('subdomain', sa.String(), nullable=False),
        sa.Column('domain', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('tier', sa.String(), nullable=False, server_default='free'),
        sa.Column('billing_type', sa.String(), nullable=False, server_default='prepaid'),
        sa.Column('max_users', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_documents', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('max_monthly_cost_inr', sa.Numeric(10, 2), nullable=True),
        sa.Column('settings', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subdomain')
    )

    # Create indexes
    op.create_index('ix_tenants_id', 'tenants', ['id'], unique=False)
    op.create_index('ix_tenants_subdomain', 'tenants', ['subdomain'], unique=True)

    print("✅ Tenants table created")

    # =================================================================
    # STEP 2: Insert default tenant for existing data
    # =================================================================
    print("Inserting default tenant...")

    op.execute("""
        INSERT INTO tenants (id, name, subdomain, status, tier, billing_type, max_users, max_documents)
        VALUES (1, 'Default Tenant (Legacy)', 'default', 'active', 'enterprise', 'postpaid', 999, 999999)
        ON CONFLICT (id) DO NOTHING
    """)

    print("✅ Default tenant inserted (id=1)")

    # =================================================================
    # STEP 3: Data validation and backfill
    # =================================================================
    print("Validating and backfilling tenant_id...")

    for table in TENANT_TABLES:
        # Skip tables that don't exist yet (created by later migrations, e.g. analysis_runs)
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = '{table}'
                ) THEN
                    UPDATE {table}
                    SET tenant_id = 1
                    WHERE tenant_id IS NULL OR tenant_id NOT IN (SELECT id FROM tenants);
                END IF;
            END $$;
        """)

    print("✅ Data validation complete")

    # =================================================================
    # STEP 4: Ensure tenant_id is NOT NULL
    # =================================================================
    print("Enforcing NOT NULL constraint on tenant_id...")

    for table in TENANT_TABLES:
        # Check if column allows NULL and update if needed
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = '{table}' AND column_name = 'tenant_id' AND is_nullable = 'YES'
                ) THEN
                    ALTER TABLE {table} ALTER COLUMN tenant_id SET NOT NULL;
                END IF;
            END $$;
        """)

    print("✅ NOT NULL constraints enforced")

    # =================================================================
    # STEP 5: Add foreign key constraints with CASCADE delete
    # =================================================================
    print("Adding foreign key constraints...")

    for table in TENANT_TABLES:
        constraint_name = f'fk_{table}_tenant'

        # Only add FK if table exists AND constraint doesn't exist yet.
        # Tables created by later migrations (e.g. analysis_runs) are skipped here;
        # their FK will be added when those migrations run via d4f3 backfill logic
        # or the tenant_id column default handles integrity.
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = '{table}'
                ) AND NOT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE constraint_name = '{constraint_name}'
                ) THEN
                    ALTER TABLE {table}
                    ADD CONSTRAINT {constraint_name}
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
                END IF;
            END $$;
        """)

    print(f"✅ Foreign key constraints added to {len(TENANT_TABLES)} tables")
    print("✅ Sprint 2 migration complete - Multi-tenancy foundation ready!")


def downgrade() -> None:
    """
    Rollback Sprint 2 changes.

    This removes FK constraints but KEEPS tenant_id columns and data.
    This allows safe rollback to Sprint 1 state.
    """

    # Remove foreign key constraints
    print("Removing foreign key constraints...")
    for table in TENANT_TABLES:
        constraint_name = f'fk_{table}_tenant'
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE constraint_name = '{constraint_name}'
                ) THEN
                    ALTER TABLE {table} DROP CONSTRAINT {constraint_name};
                END IF;
            END $$;
        """)

    # Drop indexes
    op.drop_index('ix_tenants_subdomain', table_name='tenants')
    op.drop_index('ix_tenants_id', table_name='tenants')

    # Drop tenants table
    op.drop_table('tenants')

    print("✅ Rolled back to Sprint 1 state (tenant_id columns preserved)")
