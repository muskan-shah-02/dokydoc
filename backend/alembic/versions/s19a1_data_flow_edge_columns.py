"""GAP-3 fix: Add 7 individual spec columns to code_data_flow_edges.

Revision ID: s19a1
Revises: s18a1
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa

revision = 's19a1'
down_revision = 's18a1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('code_data_flow_edges',
        sa.Column('source_function', sa.String(200), nullable=True))
    op.add_column('code_data_flow_edges',
        sa.Column('target_function', sa.String(200), nullable=True))
    op.add_column('code_data_flow_edges',
        sa.Column('data_in_description', sa.Text, nullable=True))
    op.add_column('code_data_flow_edges',
        sa.Column('data_out_description', sa.Text, nullable=True))
    op.add_column('code_data_flow_edges',
        sa.Column('human_label', sa.String(500), nullable=True))
    op.add_column('code_data_flow_edges',
        sa.Column('external_target_name', sa.String(200), nullable=True))
    op.add_column('code_data_flow_edges',
        sa.Column('step_index', sa.Integer, nullable=True))

    op.create_index(
        'ix_data_flow_edges_step',
        'code_data_flow_edges', ['source_component_id', 'step_index'],
    )


def downgrade():
    op.drop_index('ix_data_flow_edges_step', table_name='code_data_flow_edges')
    for col in ('step_index', 'external_target_name', 'human_label',
                'data_out_description', 'data_in_description',
                'target_function', 'source_function'):
        op.drop_column('code_data_flow_edges', col)
