"""
P5B-01: Add content_hash, previous_atom_id, delta_status to requirement_atoms.
        Add last_atom_diff JSONB to documents.

Revision ID: s16a1
Revises: s15a1
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 's16a1'
down_revision = 's15a1'
branch_labels = None
depends_on = None


def upgrade():
    # --- requirement_atoms: delta diffing fields ---
    op.add_column('requirement_atoms',
        sa.Column('content_hash', sa.String(64), nullable=True))
    op.add_column('requirement_atoms',
        sa.Column('previous_atom_id', sa.Integer(), nullable=True))
    op.add_column('requirement_atoms',
        sa.Column('delta_status', sa.String(20), nullable=True))
    op.add_column('requirement_atoms',
        sa.Column('regulatory_tags', postgresql.ARRAY(sa.String()), nullable=True))

    # FK for self-referential previous_atom_id (non-concurrent, plain index)
    op.create_foreign_key(
        'fk_requirement_atoms_previous_atom_id',
        'requirement_atoms', 'requirement_atoms',
        ['previous_atom_id'], ['id'],
        ondelete='SET NULL'
    )

    op.create_index(
        'ix_requirement_atoms_content_hash',
        'requirement_atoms', ['content_hash'],
    )
    op.create_index(
        'ix_requirement_atoms_delta_status',
        'requirement_atoms', ['document_id', 'delta_status'],
    )
    # GIN index for regulatory_tags array searches
    op.create_index(
        'ix_requirement_atoms_regulatory_tags',
        'requirement_atoms', ['regulatory_tags'],
        postgresql_using='gin',
    )

    # --- documents: store last atom diff result ---
    op.add_column('documents',
        sa.Column('last_atom_diff', postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column('documents', 'last_atom_diff')
    op.drop_index('ix_requirement_atoms_regulatory_tags')
    op.drop_index('ix_requirement_atoms_delta_status')
    op.drop_index('ix_requirement_atoms_content_hash')
    op.drop_constraint('fk_requirement_atoms_previous_atom_id', 'requirement_atoms', type_='foreignkey')
    op.drop_column('requirement_atoms', 'regulatory_tags')
    op.drop_column('requirement_atoms', 'delta_status')
    op.drop_column('requirement_atoms', 'previous_atom_id')
    op.drop_column('requirement_atoms', 'content_hash')
