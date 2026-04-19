"""Phase 3 — P3.2: code_data_flow_edges table for request/data flow graph.

Revision ID: s18a1
Revises: s17g1
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 's18a1'
down_revision = 's17g1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'code_data_flow_edges',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.Integer, nullable=False, index=True),
        sa.Column(
            'repository_id', sa.Integer,
            sa.ForeignKey('repositories.id', ondelete='CASCADE'),
            nullable=True, index=True,
        ),
        sa.Column(
            'source_component_id', sa.Integer,
            sa.ForeignKey('code_components.id', ondelete='CASCADE'),
            nullable=False, index=True,
        ),
        sa.Column(
            'target_component_id', sa.Integer,
            sa.ForeignKey('code_components.id', ondelete='SET NULL'),
            nullable=True, index=True,
        ),
        sa.Column('edge_type', sa.String(32), nullable=False, index=True),
        sa.Column('data_summary', sa.String(255), nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('target_ref', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "edge_type IN ('HTTP_TRIGGER','SERVICE_CALL','SCHEMA_VALIDATION',"
            "'DB_READ','DB_WRITE','EXTERNAL_API','CACHE_READ','CACHE_WRITE',"
            "'EVENT_PUBLISH','EVENT_CONSUME')",
            name='ck_data_flow_edge_type',
        ),
    )
    op.create_index(
        'ix_data_flow_edges_tenant_repo',
        'code_data_flow_edges', ['tenant_id', 'repository_id'],
    )
    op.create_index(
        'ix_data_flow_edges_source_type',
        'code_data_flow_edges', ['source_component_id', 'edge_type'],
    )


def downgrade():
    op.drop_index('ix_data_flow_edges_source_type', table_name='code_data_flow_edges')
    op.drop_index('ix_data_flow_edges_tenant_repo', table_name='code_data_flow_edges')
    op.drop_table('code_data_flow_edges')
