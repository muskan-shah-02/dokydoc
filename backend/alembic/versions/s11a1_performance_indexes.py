"""Add critical performance indexes

Revision ID: s11a1
Revises: s10a1_requirement_atoms
Create Date: 2026-04-05
"""
from alembic import op

revision = 's11a1'
down_revision = 's10a1_requirement_atoms'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Mismatches — validation panel loads these constantly
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_mismatches_tenant_doc_status
        ON mismatches (tenant_id, document_id, status);
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_mismatches_tenant_severity_open
        ON mismatches (tenant_id, severity)
        WHERE status = 'new';
    """)

    # Requirement atoms — 9-pass validation scans these in every run
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requirement_atoms_document_type
        ON requirement_atoms (document_id, atom_type);
    """)

    # Ontology graph — most expensive endpoint
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ontology_concepts_tenant_type
        ON ontology_concepts (tenant_id, concept_type);
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ontology_relationships_tenant_source
        ON ontology_relationships (tenant_id, source_concept_id);
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ontology_relationships_tenant_target
        ON ontology_relationships (tenant_id, target_concept_id);
    """)

    # Audit logs — compliance time-range queries
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_tenant_created
        ON audit_logs (tenant_id, created_at DESC);
    """)

    # Concept mappings — used in every mapping run
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_concept_mappings_tenant_doc
        ON concept_mappings (tenant_id, document_concept_id);
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_concept_mappings_tenant_code
        ON concept_mappings (tenant_id, code_concept_id);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_mismatches_tenant_doc_status;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_mismatches_tenant_severity_open;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_requirement_atoms_document_type;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_ontology_concepts_tenant_type;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_ontology_relationships_tenant_source;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_ontology_relationships_tenant_target;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_audit_logs_tenant_created;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_concept_mappings_tenant_doc;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_concept_mappings_tenant_code;")
