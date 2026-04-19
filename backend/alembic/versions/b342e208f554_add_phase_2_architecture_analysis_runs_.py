
"""Add Phase 2 architecture: analysis_runs table and status fields

Revision ID: b342e208f554
Revises: d4f3e2a1b567
Create Date: 2025-09-11 20:15:27.801157

SPRINT 2 Phase 8: Fixed down_revision to point to Sprint 2 tenant migration
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b342e208f554'
down_revision: Union[str, None] = 'd4f3e2a1b567'  # SPRINT 2 Phase 8: Fixed to depend on tenant migration
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Strategy 1: Smart Default Migration ###

    # Step 1: Create enums if they don't exist
    connection = op.get_bind()

    # Check and create enums safely using PostgreSQL IF NOT EXISTS
    # Note: DO $$ blocks allow us to check for existence without causing transaction errors
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE analysisrunstatus AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE analysisresultstatus AS ENUM ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'SKIPPED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE segmentstatus AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'SKIPPED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Step 2: Create the analysis_runs table.
    # tenant_id is included here because c8f2a1d9e321 skipped analysis_runs
    # (the table didn't exist yet when that migration ran on a fresh DB).
    op.execute("""
        CREATE TABLE IF NOT EXISTS analysis_runs (
            id                   SERIAL NOT NULL,
            document_id          INTEGER NOT NULL,
            triggered_by_user_id INTEGER NOT NULL,
            status               analysisrunstatus NOT NULL,
            created_at           TIMESTAMP NOT NULL,
            started_at           TIMESTAMP,
            completed_at         TIMESTAMP,
            total_segments       INTEGER,
            completed_segments   INTEGER NOT NULL DEFAULT 0,
            failed_segments      INTEGER NOT NULL DEFAULT 0,
            error_message        TEXT,
            error_details        JSONB,
            learning_mode        BOOLEAN NOT NULL DEFAULT false,
            run_metadata         JSONB,
            tenant_id            INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (id),
            FOREIGN KEY(document_id) REFERENCES documents (id),
            FOREIGN KEY(triggered_by_user_id) REFERENCES users (id)
        )
    """)
    op.execute("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS tenant_id INTEGER NOT NULL DEFAULT 1")
    op.execute("CREATE INDEX IF NOT EXISTS ix_analysis_runs_tenant_id ON analysis_runs (tenant_id)")

    # Step 3: Add nullable columns to existing tables (IF NOT EXISTS for idempotency).
    op.execute("ALTER TABLE analysisresult ADD COLUMN IF NOT EXISTS status analysisresultstatus")
    op.execute("ALTER TABLE analysisresult ADD COLUMN IF NOT EXISTS error_message TEXT")
    op.execute("ALTER TABLE analysisresult ADD COLUMN IF NOT EXISTS processing_time_ms INTEGER")

    op.execute("ALTER TABLE document_segments ADD COLUMN IF NOT EXISTS status segmentstatus")
    op.execute("ALTER TABLE document_segments ADD COLUMN IF NOT EXISTS retry_count INTEGER")
    op.execute("ALTER TABLE document_segments ADD COLUMN IF NOT EXISTS last_error VARCHAR")
    op.execute("ALTER TABLE document_segments ADD COLUMN IF NOT EXISTS analysis_run_id INTEGER")
    
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