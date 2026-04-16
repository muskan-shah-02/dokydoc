"""
ARC-DB-01: Add partial unique index on brd_sign_offs to prevent duplicate certificates.
ARC-DB-02: Add index on mismatches.document_id (FK with no index).
ARC-BE-05: Add composite index (tenant_id, document_id, status) on mismatches hot path.

Revision ID: s17b1
Revises: s17a1
Create Date: 2026-04-16
"""
from alembic import op

revision = 's17b1'
down_revision = 's17a1'
branch_labels = None
depends_on = None


def upgrade():
    # ARC-DB-02: mismatches.document_id FK had no index — all coverage matrix,
    # compliance score, and sign-off queries filter on this column.
    op.create_index(
        'ix_mismatches_document_id',
        'mismatches', ['document_id'],
    )

    # ARC-BE-05: Composite index for the hot query path
    # (tenant_id, document_id, status) — used by get_multi_by_owner,
    # coverage matrix, compliance score, and sign-off.
    op.create_index(
        'ix_mismatches_tenant_doc_status',
        'mismatches', ['tenant_id', 'document_id', 'status'],
    )

    # ARC-DB-01: Prevent two concurrent BAs from each generating a certificate
    # for the same document.  Partial index only applies when there are no
    # unresolved criticals (i.e. the "clean" sign-off path).
    op.execute("""
        CREATE UNIQUE INDEX uq_brd_sign_off_active
        ON brd_sign_offs (document_id, tenant_id)
        WHERE has_unresolved_critical = FALSE
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_brd_sign_off_active")
    op.drop_index('ix_mismatches_tenant_doc_status', table_name='mismatches')
    op.drop_index('ix_mismatches_document_id', table_name='mismatches')
