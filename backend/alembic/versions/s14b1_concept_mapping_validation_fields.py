"""P4-05: Add validation feedback fields to concept_mappings

Revision ID: s14b1
Revises: s14a1
Create Date: 2026-04-13

Purpose:
  Phase 4 Confidence Calibration Loop.

  After each validation run, the AI's verdict (MATCH / PARTIAL_MATCH / MISMATCH)
  is written back to the ConceptMapping that triggered it. This closes the
  feedback loop:

    Validation verdict → delta to confidence_score → BOE gets smarter over time
    High confidence → skips Gemini next run → lower cost per scan

  New columns:
    last_validated_at  — when this mapping was last observed in a validation result
    validation_verdict — last AI verdict: MATCH | PARTIAL_MATCH | MISMATCH
"""
from alembic import op
import sqlalchemy as sa

revision = 's14b1'
down_revision = 's14a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # last_validated_at: timestamp of most recent validation observation
    op.add_column(
        'concept_mappings',
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True)
    )
    # validation_verdict: MATCH | PARTIAL_MATCH | MISMATCH (or NULL = never validated)
    op.add_column(
        'concept_mappings',
        sa.Column('validation_verdict', sa.String(20), nullable=True)
    )
    # Index for queries like "show mappings validated in last 30 days"
    op.create_index(
        'ix_concept_mappings_last_validated_at',
        'concept_mappings',
        ['last_validated_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_concept_mappings_last_validated_at', table_name='concept_mappings')
    op.drop_column('concept_mappings', 'validation_verdict')
    op.drop_column('concept_mappings', 'last_validated_at')
