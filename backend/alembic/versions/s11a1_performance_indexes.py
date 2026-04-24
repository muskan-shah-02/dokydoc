"""Add critical performance indexes

Revision ID: s11a1
Revises: s10a1_requirement_atoms
Create Date: 2026-04-05

Note: CONCURRENTLY was removed because it cannot run inside Alembic's
transaction wrapper. For production DBs with heavy write traffic, build
these indexes manually outside Alembic with CONCURRENTLY.
"""
from alembic import op

revision = 's11a1'
down_revision = 's10a1_requirement_atoms'
branch_labels = None
depends_on = None

_INDEXES = [
    ("idx_mismatches_tenant_doc_status",
     "ON mismatches (tenant_id, document_id, status)"),
    ("idx_mismatches_tenant_severity_open",
     "ON mismatches (tenant_id, severity) WHERE status = 'new'"),
    ("idx_requirement_atoms_document_type",
     "ON requirement_atoms (document_id, atom_type)"),
    ("idx_ontology_concepts_tenant_type",
     "ON ontology_concepts (tenant_id, concept_type)"),
    ("idx_ontology_relationships_tenant_source",
     "ON ontology_relationships (tenant_id, source_concept_id)"),
    ("idx_ontology_relationships_tenant_target",
     "ON ontology_relationships (tenant_id, target_concept_id)"),
    ("idx_audit_logs_tenant_created",
     "ON audit_logs (tenant_id, created_at DESC)"),
    ("idx_concept_mappings_tenant_doc",
     "ON concept_mappings (tenant_id, document_concept_id)"),
    ("idx_concept_mappings_tenant_code",
     "ON concept_mappings (tenant_id, code_concept_id)"),
]


def upgrade() -> None:
    for name, definition in _INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} {definition}")


def downgrade() -> None:
    for name, _ in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
