# This is the updated content for your generated migration file, e.g.:
# backend/app/db/migrations/versions/a68757e06e53_add_analysis_fields_to_code_components.py

"""Add analysis fields to code_components

Revision ID: a68757e06e53
Revises: 50587544109e
Create Date: 2025-07-21 15:07:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a68757e06e53'
down_revision = '50587544109e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### Two-Stage Migration to preserve existing data ###
    
    # Step 1: Add the new columns, but make them nullable initially to avoid errors on existing rows.
    op.add_column('code_components', sa.Column('summary', sa.Text(), nullable=True))
    # The 'astext_for_null' argument has been removed from JSONB as it's deprecated.
    op.add_column('code_components', sa.Column('structured_analysis', postgresql.JSONB(), nullable=True))
    op.add_column('code_components', sa.Column('analysis_status', sa.String(), nullable=True)) # Nullable=True for now
    op.add_column('code_components', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    # Step 2: Backfill the new 'analysis_status' column for all existing rows with a default value.
    # This ensures no rows are left with a null value before we enforce the NOT NULL constraint.
    op.execute("UPDATE code_components SET analysis_status = 'pending' WHERE analysis_status IS NULL")

    # Step 3: Now that all rows have a valid value, alter the column to be NOT NULL as intended.
    op.alter_column('code_components', 'analysis_status', nullable=False)
    
    # Finally, create the index on the now-populated column.
    op.create_index(op.f('ix_code_components_analysis_status'), 'code_components', ['analysis_status'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### The downgrade path simply removes the new columns and index ###
    op.drop_index(op.f('ix_code_components_analysis_status'), table_name='code_components')
    op.drop_column('code_components', 'updated_at')
    op.drop_column('code_components', 'summary')
    op.drop_column('code_components', 'structured_analysis')
    op.drop_column('code_components', 'analysis_status')
    # ### end Alembic commands ###
