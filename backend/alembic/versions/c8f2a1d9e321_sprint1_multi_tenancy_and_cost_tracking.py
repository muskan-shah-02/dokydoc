"""Sprint 1: Multi-tenancy and cost tracking

Revision ID: c8f2a1d9e321
Revises: None
Create Date: 2026-01-14 10:00:00.000000

This migration:
1. Creates all core application tables (IF NOT EXISTS — safe on existing DBs)
2. Adds tenant_id to all tables for multi-tenancy support
3. Adds cost tracking fields to documents table
4. Creates tenant_billing table

Using IF NOT EXISTS guards throughout makes this idempotent for both
fresh databases and existing ones that had tables pre-created via
Base.metadata.create_all().
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
    # Each statement uses IF NOT EXISTS so it is a no-op on existing databases.
    # FK constraints to tables created in later migrations (repositories,
    # requirement_atoms, document_versions) are intentionally omitted here;
    # those columns are plain integers and the FK constraints are added later.

    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          SERIAL PRIMARY KEY,
            email       VARCHAR NOT NULL,
            hashed_password VARCHAR NOT NULL,
            is_active   BOOLEAN NOT NULL DEFAULT true,
            is_superuser BOOLEAN NOT NULL DEFAULT false,
            roles       VARCHAR[] NOT NULL DEFAULT '{}',
            created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_users_email UNIQUE (email)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id              SERIAL PRIMARY KEY,
            filename        VARCHAR NOT NULL,
            document_type   VARCHAR,
            version         VARCHAR DEFAULT '1.0',
            owner_id        INTEGER,
            storage_path    VARCHAR,
            raw_text        TEXT NOT NULL DEFAULT '',
            composition_analysis JSONB,
            status          VARCHAR DEFAULT 'uploaded',
            progress        INTEGER DEFAULT 0,
            error_message   TEXT,
            file_size_kb    INTEGER,
            content         TEXT,
            last_atom_diff  JSONB,
            created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_filename ON documents (filename)")

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
        CREATE TABLE IF NOT EXISTS analysis_runs (
            id                  SERIAL PRIMARY KEY,
            document_id         INTEGER,
            triggered_by_user_id INTEGER,
            status              VARCHAR NOT NULL DEFAULT 'pending',
            created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
            started_at          TIMESTAMP,
            completed_at        TIMESTAMP,
            total_segments      INTEGER,
            completed_segments  INTEGER NOT NULL DEFAULT 0,
            failed_segments     INTEGER NOT NULL DEFAULT 0,
            error_message       TEXT,
            error_details       JSONB,
            learning_mode       BOOLEAN NOT NULL DEFAULT false,
            run_metadata        JSONB
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS document_segments (
            id              SERIAL PRIMARY KEY,
            segment_type    VARCHAR NOT NULL,
            start_char_index INTEGER NOT NULL,
            end_char_index  INTEGER NOT NULL,
            document_id     INTEGER,
            status          VARCHAR NOT NULL DEFAULT 'pending',
            retry_count     INTEGER NOT NULL DEFAULT 0,
            last_error      VARCHAR,
            analysis_run_id INTEGER,
            created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS analysisresult (
            id              SERIAL PRIMARY KEY,
            structured_data JSONB,
            segment_id      INTEGER,
            document_id     INTEGER,
            status          VARCHAR NOT NULL DEFAULT 'pending',
            error_message   TEXT,
            processing_time_ms INTEGER,
            created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS consolidated_analyses (
            id          SERIAL PRIMARY KEY,
            document_id INTEGER,
            data        JSONB NOT NULL DEFAULT '{}',
            created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # code_components references repositories (created in a later migration);
    # repository_id is created as a plain integer column here.
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
            repository_id           INTEGER,
            ai_cost_inr             NUMERIC(10,4) NOT NULL DEFAULT 0.0,
            token_count_input       INTEGER NOT NULL DEFAULT 0,
            token_count_output      INTEGER NOT NULL DEFAULT 0,
            cost_breakdown          JSONB,
            analysis_started_at     TIMESTAMP,
            analysis_completed_at   TIMESTAMP,
            created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_code_components_id ON code_components (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_code_components_name ON code_components (name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_code_components_analysis_status ON code_components (analysis_status)")

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

    op.execute("""
        CREATE TABLE IF NOT EXISTS ontology_concepts (
            id                  SERIAL PRIMARY KEY,
            initiative_id       INTEGER,
            name                VARCHAR(255) NOT NULL,
            concept_type        VARCHAR(100) NOT NULL,
            description         TEXT,
            confidence_score    FLOAT,
            source_type         VARCHAR(20) NOT NULL DEFAULT 'document',
            source_component_id INTEGER,
            source_document_id  INTEGER,
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

    # mismatches references requirement_atoms and document_versions (later migrations);
    # those FK columns are plain integers here.
    op.execute("""
        CREATE TABLE IF NOT EXISTS mismatches (
            id                      SERIAL PRIMARY KEY,
            mismatch_type           VARCHAR NOT NULL,
            description             TEXT NOT NULL,
            severity                VARCHAR NOT NULL,
            status                  VARCHAR NOT NULL DEFAULT 'open',
            details                 JSONB,
            confidence              VARCHAR,
            user_notes              TEXT,
            direction               VARCHAR DEFAULT 'forward',
            requirement_atom_id     INTEGER,
            document_id             INTEGER,
            code_component_id       INTEGER,
            owner_id                INTEGER,
            resolution_note         TEXT,
            status_changed_by_id    INTEGER,
            status_changed_at       TIMESTAMP,
            jira_issue_key          VARCHAR(50),
            jira_issue_url          VARCHAR(500),
            document_version_id     INTEGER,
            created_commit_hash     VARCHAR(40),
            resolved_commit_hash    VARCHAR(40),
            created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_mismatches_id ON mismatches (id)")

    # ── Step 1: Add tenant_id to all tables (IF NOT EXISTS) ─────────────────
    tables_to_update = [
        'users', 'documents', 'code_components', 'mismatches',
        'document_segments', 'analysisresult', 'document_code_links',
        'initiatives', 'initiative_assets', 'ontology_concepts',
        'ontology_relationships', 'analysis_runs', 'consolidated_analyses',
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

    # Seed default billing record for tenant 1 (idempotent)
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
        'consolidated_analyses', 'analysis_runs', 'ontology_relationships',
        'ontology_concepts', 'initiative_assets', 'initiatives',
        'document_code_links', 'analysisresult', 'document_segments',
        'mismatches', 'code_components', 'documents', 'users',
    ]
    for table in tables_to_revert:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_tenant_id")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS tenant_id")
