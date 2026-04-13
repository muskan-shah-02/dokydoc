"""P4-01: Add atomized_at_upload flag to requirement_atoms

Revision ID: s14a1
Revises: s12a1
Create Date: 2026-04-13

Purpose:
  Phase 4 BOE-Aware Validation Engine.
  Adds `atomized_at_upload` boolean column to track which atoms were
  extracted eagerly at document upload time (vs lazily at first validation).

  This flag enables:
    - Analytics: measure pre-atomization hit rates
    - Debugging: distinguish upload-time vs validation-time atoms
    - Future: skip re-atomization if document hasn't changed since upload
"""
from alembic import op
import sqlalchemy as sa

revision = 's14a1'
down_revision = 's12a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add atomized_at_upload column to requirement_atoms
    op.add_column(
        'requirement_atoms',
        sa.Column(
            'atomized_at_upload',
            sa.Boolean(),
            nullable=False,
            server_default='false',
        )
    )
    # Index for analytics queries (e.g. "how many atoms came from upload-time atomization?")
    op.create_index(
        'ix_requirement_atoms_atomized_at_upload',
        'requirement_atoms',
        ['atomized_at_upload'],
    )


def downgrade() -> None:
    op.drop_index('ix_requirement_atoms_atomized_at_upload', table_name='requirement_atoms')
    op.drop_column('requirement_atoms', 'atomized_at_upload')
