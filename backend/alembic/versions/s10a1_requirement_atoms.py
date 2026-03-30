"""s10a1: add requirement_atoms table and mismatch direction/atom fields

Revision ID: s10a1_requirement_atoms
Revises: s9d1_repo_language_breakdown
Create Date: 2026-03-29

"""
from alembic import op
import sqlalchemy as sa

revision = 's10a1_requirement_atoms'
down_revision = 's9d1_repo_language_breakdown'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create requirement_atoms table
    op.create_table(
        'requirement_atoms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('atom_id', sa.String(length=20), nullable=False),
        sa.Column('atom_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('criticality', sa.String(length=20), nullable=False, server_default='standard'),
        sa.Column('document_version', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_requirement_atoms_id', 'requirement_atoms', ['id'])
    op.create_index('ix_requirement_atoms_tenant_id', 'requirement_atoms', ['tenant_id'])
    op.create_index('ix_requirement_atoms_document_id', 'requirement_atoms', ['document_id'])
    op.create_index('ix_requirement_atoms_atom_type', 'requirement_atoms', ['atom_type'])

    # 2. Add direction field to mismatches (forward = doc→code, reverse = code→doc)
    op.add_column('mismatches',
        sa.Column('direction', sa.String(length=20), nullable=True, server_default='forward')
    )

    # 3. Add requirement_atom_id FK to mismatches (nullable — old mismatches won't have it)
    op.add_column('mismatches',
        sa.Column('requirement_atom_id', sa.Integer(), sa.ForeignKey('requirement_atoms.id'), nullable=True)
    )


def downgrade():
    op.drop_column('mismatches', 'requirement_atom_id')
    op.drop_column('mismatches', 'direction')
    op.drop_index('ix_requirement_atoms_atom_type', table_name='requirement_atoms')
    op.drop_index('ix_requirement_atoms_document_id', table_name='requirement_atoms')
    op.drop_index('ix_requirement_atoms_tenant_id', table_name='requirement_atoms')
    op.drop_index('ix_requirement_atoms_id', table_name='requirement_atoms')
    op.drop_table('requirement_atoms')
