"""Add Phase 2 architecture: analysis_runs table and status fields

Revision ID: b342e208f554
Revises: 3d4d38b70252
Create Date: 2025-09-11 20:15:27.801157

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b342e208f554'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Strategy 1: Smart Default Migration ###
    
    # Step 1: Create enums if they don't exist
    connection = op.get_bind()
    
    # Check and create enums safely
    try:
        op.execute("CREATE TYPE analysisrunstatus AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')")
    except Exception:
        pass  # Enum already exists
    
    try:
        op.execute("CREATE TYPE analysisresultstatus AS ENUM ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'SKIPPED')")
    except Exception:
        pass  # Enum already exists
        
    try:
        op.execute("CREATE TYPE segmentstatus AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'SKIPPED')")
    except Exception:
        pass  # Enum already exists
    
    # Step 2: Create the analysis_runs table first
    op.create_table('analysis_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('triggered_by_user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='analysisrunstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('total_segments', sa.Integer(), nullable=True),
        sa.Column('completed_segments', sa.Integer(), nullable=False),
        sa.Column('failed_segments', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('learning_mode', sa.Boolean(), nullable=False),
        sa.Column('run_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Step 2: Add nullable columns to existing tables
    op.add_column('analysisresult', sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'SKIPPED', name='analysisresultstatus'), nullable=True))
    op.add_column('analysisresult', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('analysisresult', sa.Column('processing_time_ms', sa.Integer(), nullable=True))
    
    op.add_column('document_segments', sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'SKIPPED', name='segmentstatus'), nullable=True))
    op.add_column('document_segments', sa.Column('retry_count', sa.Integer(), nullable=True))
    op.add_column('document_segments', sa.Column('last_error', sa.String(), nullable=True))
    op.add_column('document_segments', sa.Column('analysis_run_id', sa.Integer(), nullable=True))
    
    # Step 3: Smart Data Analysis and Population
    
    # Create legacy analysis runs for existing documents
    op.execute("""
        INSERT INTO analysis_runs (
            document_id, triggered_by_user_id, status, created_at, 
            completed_at, completed_segments, failed_segments, learning_mode
        )
        SELECT DISTINCT 
            d.id as document_id,
            d.owner_id as triggered_by_user_id,
            'COMPLETED' as status,
            d.created_at as created_at,
            d.updated_at as completed_at,
            COALESCE(segment_counts.completed, 0) as completed_segments,
            COALESCE(segment_counts.failed, 0) as failed_segments,
            false as learning_mode
        FROM documents d
        LEFT JOIN (
            SELECT 
                ds.document_id,
                COUNT(CASE WHEN ar.id IS NOT NULL THEN 1 END) as completed,
                COUNT(CASE WHEN ar.id IS NULL THEN 1 END) as failed
            FROM document_segments ds
            LEFT JOIN analysisresult ar ON ds.id = ar.segment_id
            GROUP BY ds.document_id
        ) segment_counts ON d.id = segment_counts.document_id
        WHERE EXISTS (SELECT 1 FROM document_segments ds WHERE ds.document_id = d.id)
    """)
    
    # Step 4: Apply intelligent defaults based on data relationships
    
    # AnalysisResult: All existing results are successful (they exist, so they succeeded)
    op.execute("UPDATE analysisresult SET status = 'SUCCESS' WHERE status IS NULL")
    op.execute("UPDATE analysisresult SET processing_time_ms = 0 WHERE processing_time_ms IS NULL")
    
    # DocumentSegment: Smart status inference
    # Segments with results → 'COMPLETED'
    op.execute("""
        UPDATE document_segments 
        SET status = 'COMPLETED', retry_count = 0
        WHERE status IS NULL 
        AND id IN (SELECT DISTINCT segment_id FROM analysisresult)
    """)
    
    # Segments without results → 'PENDING' (incomplete processing)
    op.execute("""
        UPDATE document_segments 
        SET status = 'PENDING', retry_count = 0
        WHERE status IS NULL 
        AND id NOT IN (SELECT DISTINCT segment_id FROM analysisresult WHERE segment_id IS NOT NULL)
    """)
    
    # Link segments to their legacy analysis runs
    op.execute("""
        UPDATE document_segments 
        SET analysis_run_id = ar.id
        FROM analysis_runs ar
        WHERE document_segments.document_id = ar.document_id
        AND ar.status = 'COMPLETED'
    """)
    
    # Step 5: Make columns NOT NULL after data population
    op.alter_column('analysisresult', 'status', nullable=False)
    op.alter_column('document_segments', 'status', nullable=False)
    op.alter_column('document_segments', 'retry_count', nullable=False)
    
    # Step 6: Make structured_data nullable (failed results won't have data)
    op.alter_column('analysisresult', 'structured_data',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               nullable=True)
    
    # Step 7: Add foreign key constraint
    op.create_foreign_key(None, 'document_segments', 'analysis_runs', ['analysis_run_id'], ['id'])
    
    # Step 8: Add indexes for performance
    op.create_index('ix_analysis_runs_document_id', 'analysis_runs', ['document_id'])
    op.create_index('ix_analysis_runs_status', 'analysis_runs', ['status'])
    op.create_index('ix_document_segments_analysis_run_id', 'document_segments', ['analysis_run_id'])
    op.create_index('ix_document_segments_status', 'document_segments', ['status'])


def downgrade() -> None:
    # ### Rollback Strategy ###
    op.drop_index('ix_document_segments_status', 'document_segments')
    op.drop_index('ix_document_segments_analysis_run_id', 'document_segments')
    op.drop_index('ix_analysis_runs_status', 'analysis_runs')
    op.drop_index('ix_analysis_runs_document_id', 'analysis_runs')
    
    op.drop_constraint(None, 'document_segments', type_='foreignkey')
    op.drop_column('document_segments', 'analysis_run_id')
    op.drop_column('document_segments', 'last_error')
    op.drop_column('document_segments', 'retry_count')
    op.drop_column('document_segments', 'status')
    
    op.alter_column('analysisresult', 'structured_data',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               nullable=False)
    op.drop_column('analysisresult', 'processing_time_ms')
    op.drop_column('analysisresult', 'error_message')
    op.drop_column('analysisresult', 'status')
    
    op.drop_table('analysis_runs')
    
    # Drop the enums
    postgresql.ENUM(name='analysisrunstatus').drop(op.get_bind())
    postgresql.ENUM(name='segmentstatus').drop(op.get_bind())
    postgresql.ENUM(name='analysisresultstatus').drop(op.get_bind())