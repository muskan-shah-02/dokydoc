"""
P5B-03/04/10/11: Add enterprise workflow fields to mismatches.

  P5B-03: jira_issue_key, jira_issue_url
  P5B-04: resolution_note, status_changed_by_id, status_changed_at
  P5B-10: update default status 'new' → 'open'
  P5B-11: document_version_id, created_commit_hash, resolved_commit_hash

Revision ID: s16b1
Revises: s16a1
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa

revision = 's16b1'
down_revision = 's16a1'
branch_labels = None
depends_on = None


def upgrade():
    # P5B-04: False Positive Workflow fields
    op.add_column('mismatches', sa.Column('resolution_note', sa.Text(), nullable=True))
    op.add_column('mismatches', sa.Column('status_changed_by_id', sa.Integer(), nullable=True))
    op.add_column('mismatches', sa.Column('status_changed_at', sa.DateTime(), nullable=True))
    op.create_foreign_key(
        'fk_mismatches_status_changed_by',
        'mismatches', 'users',
        ['status_changed_by_id'], ['id'],
        ondelete='SET NULL'
    )

    # P5B-03: Jira issue linking
    op.add_column('mismatches', sa.Column('jira_issue_key', sa.String(50), nullable=True))
    op.add_column('mismatches', sa.Column('jira_issue_url', sa.String(500), nullable=True))
    op.create_index('ix_mismatches_jira_issue_key', 'mismatches', ['jira_issue_key'])

    # P5B-11: Version-linked mismatches
    op.add_column('mismatches', sa.Column('document_version_id', sa.Integer(), nullable=True))
    op.add_column('mismatches', sa.Column('created_commit_hash', sa.String(40), nullable=True))
    op.add_column('mismatches', sa.Column('resolved_commit_hash', sa.String(40), nullable=True))
    op.create_foreign_key(
        'fk_mismatches_document_version_id',
        'mismatches', 'document_versions',
        ['document_version_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_mismatches_document_version_id', 'mismatches', ['document_version_id'])
    op.create_index('ix_mismatches_created_commit_hash', 'mismatches', ['created_commit_hash'])

    # P5B-10: Migrate status 'new' → 'open' for existing rows
    op.execute("UPDATE mismatches SET status = 'open' WHERE status = 'new'")


def downgrade():
    op.execute("UPDATE mismatches SET status = 'new' WHERE status = 'open'")
    op.drop_index('ix_mismatches_created_commit_hash')
    op.drop_index('ix_mismatches_document_version_id')
    op.drop_constraint('fk_mismatches_document_version_id', 'mismatches', type_='foreignkey')
    op.drop_column('mismatches', 'resolved_commit_hash')
    op.drop_column('mismatches', 'created_commit_hash')
    op.drop_column('mismatches', 'document_version_id')
    op.drop_index('ix_mismatches_jira_issue_key')
    op.drop_column('mismatches', 'jira_issue_url')
    op.drop_column('mismatches', 'jira_issue_key')
    op.drop_constraint('fk_mismatches_status_changed_by', 'mismatches', type_='foreignkey')
    op.drop_column('mismatches', 'status_changed_at')
    op.drop_column('mismatches', 'status_changed_by_id')
    op.drop_column('mismatches', 'resolution_note')
