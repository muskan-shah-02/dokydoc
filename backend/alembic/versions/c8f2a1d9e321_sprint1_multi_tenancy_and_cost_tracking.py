"""Sprint 1: Multi-tenancy and cost tracking

Revision ID: c8f2a1d9e321
Revises: None
Create Date: 2026-01-14 10:00:00.000000

Creates the original core tables (IF NOT EXISTS) with their pre-Alembic
baseline columns, then adds tenant_id and cost tracking on top.

Columns added by later migrations are deliberately excluded here to
avoid DuplicateColumn conflicts:
  - code_components: repository_id (s3a1), cost columns (s3a4/s3a5),
    analysis_started_at/completed_at (s3a6)
  - mismatches: direction/requirement_atom_id (s10a1), enterprise
    fields (s16b1)
  - document_segments: status/retry_count/last_error/analysis_run_id
    (b342e208f554)
  - analysisresult: status/error_message/processing_time_ms (b342e208f554)
  - documents: last_atom_diff (s16a1), file_suggestion_summary (s17c1)
  - ontology_concepts: source_type (s3b1), source_component_id (s4a3),
    source_document_id (s4a4)
  - analysis_runs: created by b342e208f554 (tenant_id added there)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c8f2a1d9e321'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Step 0: Create base tables for fresh installs ────────────────────────
    # Minimal baseline schema only — subsequent migrations add the rest.

    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              SERIAL PRIMARY KEY,
            email           VARCHAR NOT NULL,
            hashed_password VARCHAR NOT NULL,
            is_active       BOOLEAN NOT NULL DEFAULT true,
            is_superuser    BOOLEAN NOT NULL DEFAULT false,
            roles           VARCHAR[] NOT NULL DEFAULT '{}',
            created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_users_email UNIQUE (email)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")

    # documents: excludes last_atom_diff (s16a1), file_suggestion_summary (s17c1),
    # and cost columns (added below by this migration itself).
    op.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id                  SERIAL PRIMARY KEY,
            filename            VARCHAR NOT NULL,
            document_type       VARCHAR,
            version             VARCHAR DEFAULT '1.0',
            owner_id            INTEGER,
            storage_path        VARCHAR,
            raw_text            TEXT NOT NULL DEFAULT '',
            composition_analysis JSONB,
            status              VARCHAR DEFAULT 'uploaded',
            progress            INTEGER DEFAULT 0,
            error_message       TEXT,
            file_size_kb        INTEGER,
            content             TEXT,
            created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_filename ON documents (filename)")

    # code_components: excludes repository_id (s3a1/s3a3), cost columns (s3a4/s3a5),
    # analysis_started_at/completed_at (s3a6).
    op.execute("""
        CREATE TABLE IF NOT EXISTS code_components (
            id                      SERIAL PRIMARY KEY,
            name                    VARCHAR NOT NULL,
            component_type          VARCHAR NOT NULL,
            location                VARCHAR NOT NULL,
            version                 VARCHAR NOT NULL,
            summary                 TEXT,
            structured_analysis     JSONB,
            analysis_delta          JSONB,
            previous_analysis_hash  VARCHAR(64),
            analysis_status         VARCHAR NOT NULL DEFAULT 'pending',
            owner_id                INTEGER,
            created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_code_components_id ON code_components (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_code_components_name ON code_components (name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_code_components_analysis_status ON code_components (analysis_status)")

    # mismatches: excludes direction/requirement_atom_id (s10a1) and enterprise
    # fields (s16b1).
    op.execute("""
        CREATE TABLE IF NOT EXISTS mismatches (
            id                  SERIAL PRIMARY KEY,
            mismatch_type       VARCHAR NOT NULL,
            description         TEXT NOT NULL,
            severity            VARCHAR NOT NULL,
            status              VARCHAR NOT NULL DEFAULT 'open',
            details             JSONB,
            confidence          VARCHAR,
            user_notes          TEXT,
            document_id         INTEGER,
            code_component_id   INTEGER,
            owner_id            INTEGER,
            created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_mismatches_id ON mismatches (id)")

    # document_segments: excludes status/retry_count/last_error/analysis_run_id
    # (all added by b342e208f554).
    op.execute("""
        CREATE TABLE IF NOT EXISTS document_segments (
            id              SERIAL PRIMARY KEY,
            segment_type    VARCHAR NOT NULL,
            start_char_index INTEGER NOT NULL,
            end_char_index  INTEGER NOT NULL,
            document_id     INTEGER,
            created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # analysisresult: excludes status/error_message/processing_time_ms
    # (all added by b342e208f554). structured_data starts NOT NULL; b342e208f554
    # makes it nullable.
    op.execute("""
        CREATE TABLE IF NOT EXISTS analysisresult (
            id              SERIAL PRIMARY KEY,
            structured_data JSONB NOT NULL DEFAULT '{}',
            segment_id      INTEGER,
            document_id     INTEGER,
            created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS document_code_links (
            id                  SERIAL PRIMARY KEY,
            document_id         INTEGER,
            code_component_id   INTEGER,
            created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT _document_code_uc UNIQUE (document_id, code_component_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_code_links_id ON document_code_links (id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS initiatives (
            id          SERIAL PRIMARY KEY,
            name        VARCHAR(255) NOT NULL,
            description TEXT,
            status      VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
            owner_id    INTEGER,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_initiatives_name ON initiatives (name)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS initiative_assets (
            id              SERIAL PRIMARY KEY,
            initiative_id   INTEGER,
            asset_type      VARCHAR(50) NOT NULL,
            asset_id        INTEGER NOT NULL,
            is_active       BOOLEAN NOT NULL DEFAULT true,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            updated_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ontology_concepts: excludes source_type (s3b1), source_component_id (s4a3),
    # source_document_id (s4a4).
    op.execute("""
        CREATE TABLE IF NOT EXISTS ontology_concepts (
            id                  SERIAL PRIMARY KEY,
            initiative_id       INTEGER,
            name                VARCHAR(255) NOT NULL,
            concept_type        VARCHAR(100) NOT NULL,
            description         TEXT,
            confidence_score    FLOAT,
            is_active           BOOLEAN NOT NULL DEFAULT true,
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            updated_at          TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ontology_concepts_id ON ontology_concepts (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ontology_concepts_name ON ontology_concepts (name)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS ontology_relationships (
            id                  SERIAL PRIMARY KEY,
            source_concept_id   INTEGER,
            target_concept_id   INTEGER,
            relationship_type   VARCHAR(100) NOT NULL,
            description         TEXT,
            confidence_score    FLOAT,
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            updated_at          TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ontology_relationships_id ON ontology_relationships (id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS consolidated_analyses (
            id          SERIAL PRIMARY KEY,
            document_id INTEGER,
            data        JSONB NOT NULL DEFAULT '{}',
            created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # analysis_runs is NOT pre-created here; b342e208f554 creates it with
    # the correct ENUM column type AND adds tenant_id.

    # ── Step 1: Add tenant_id to all tables (IF NOT EXISTS) ─────────────────
    # analysis_runs is excluded — b342e208f554 handles it when it creates that table.
    tables_to_update = [
        'users', 'documents', 'code_components', 'mismatches',
        'document_segments', 'analysisresult', 'document_code_links',
        'initiatives', 'initiative_assets', 'ontology_concepts',
        'ontology_relationships', 'consolidated_analyses',
    ]
    for table in tables_to_update:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id INTEGER NOT NULL DEFAULT 1")
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id ON {table} (tenant_id)")

    # ── Step 2: Cost tracking columns on documents ───────────────────────────
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_cost_inr NUMERIC(10,4) NOT NULL DEFAULT 0.0")
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS token_count_input INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS token_count_output INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS cost_breakdown JSONB")

    # ── Step 3: tenant_billing table ─────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_billing (
            id                      SERIAL PRIMARY KEY,
            tenant_id               INTEGER NOT NULL,
            billing_type            VARCHAR NOT NULL,
            balance_inr             NUMERIC(12,2) NOT NULL DEFAULT 0.0,
            low_balance_threshold   NUMERIC(12,2) NOT NULL DEFAULT 100.0,
            current_month_cost      NUMERIC(12,2) NOT NULL DEFAULT 0.0,
            last_30_days_cost       NUMERIC(12,2) NOT NULL DEFAULT 0.0,
            monthly_limit_inr       NUMERIC(12,2),
            created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at              TIMESTAMP NOT NULL DEFAULT NOW(),
            last_billing_reset      TIMESTAMP,
            CONSTRAINT uq_tenant_billing_tenant_id UNIQUE (tenant_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tenant_billing_tenant_id ON tenant_billing (tenant_id)")
    op.execute("""
        INSERT INTO tenant_billing (tenant_id, billing_type, balance_inr,
            low_balance_threshold, current_month_cost, last_30_days_cost,
            created_at, updated_at)
        VALUES (1, 'postpaid', 0.0, 100.0, 0.0, 0.0, NOW(), NOW())
        ON CONFLICT (tenant_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tenant_billing_tenant_id")
    op.execute("DROP TABLE IF EXISTS tenant_billing")

    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS cost_breakdown")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS token_count_output")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS token_count_input")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS ai_cost_inr")

    tables_to_revert = [
        'consolidated_analyses', 'ontology_relationships', 'ontology_concepts',
        'initiative_assets', 'initiatives', 'document_code_links',
        'analysisresult', 'document_segments', 'mismatches',
        'code_components', 'documents', 'users',
    ]
    for table in tables_to_revert:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_tenant_id")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS tenant_id")
