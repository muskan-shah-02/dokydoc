"""Add unique constraint on ontology_concepts name+tenant+source_type

Revision ID: s11b1
Revises: s11a1
Create Date: 2026-04-05

WARNING: The upgrade() function deletes duplicate ontology_concepts rows,
keeping the one with the highest id in each duplicate group. Run on staging
first and verify the duplicate removal query matches your data expectations.
"""
from alembic import op

revision = 's11b1'
down_revision = 's11a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove existing duplicates — keeps the row with the highest id per group.
    # This is safe: the highest-id row is the most recent extraction.
    op.execute("""
        DELETE FROM ontology_concepts
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM ontology_concepts
            GROUP BY name, tenant_id, source_type
        );
    """)

    # Add the unique index — prevents future duplicates at DB level
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_ontology_concept_name_tenant_source
        ON ontology_concepts (name, tenant_id, source_type);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_ontology_concept_name_tenant_source;")
