"""Sprint 9c1: Create jira_items table for deep JIRA sync.

Revision ID: s9c1
Revises: s9b1
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa

revision = "s9c1"
down_revision = "s9b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jira_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("integration_config_id", sa.Integer(), nullable=False),
        sa.Column("external_key", sa.String(50), nullable=False),
        sa.Column("project_key", sa.String(30), nullable=True),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("priority", sa.String(30), nullable=True),
        sa.Column("assignee", sa.String(200), nullable=True),
        sa.Column("reporter", sa.String(200), nullable=True),
        sa.Column("epic_key", sa.String(50), nullable=True),
        sa.Column("parent_key", sa.String(50), nullable=True),
        sa.Column("sprint_name", sa.String(200), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("components", sa.JSON(), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("ontology_concept_id", sa.Integer(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["integration_config_id"], ["integration_configs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ontology_concept_id"], ["ontology_concepts.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_jira_items_tenant_id", "jira_items", ["tenant_id"])
    op.create_index("ix_jira_items_item_type", "jira_items", ["item_type"])
    op.create_index("ix_jira_items_project_key", "jira_items", ["project_key"])
    op.create_index("ix_jira_items_epic_key", "jira_items", ["epic_key"])
    op.create_index("ix_jira_items_sprint_name", "jira_items", ["sprint_name"])
    op.create_index(
        "ix_jira_items_tenant_key",
        "jira_items",
        ["tenant_id", "integration_config_id", "external_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_jira_items_tenant_key", table_name="jira_items")
    op.drop_index("ix_jira_items_sprint_name", table_name="jira_items")
    op.drop_index("ix_jira_items_epic_key", table_name="jira_items")
    op.drop_index("ix_jira_items_project_key", table_name="jira_items")
    op.drop_index("ix_jira_items_item_type", table_name="jira_items")
    op.drop_index("ix_jira_items_tenant_id", table_name="jira_items")
    op.drop_table("jira_items")
