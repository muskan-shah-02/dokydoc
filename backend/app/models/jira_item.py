"""
JiraItem model — stores JIRA hierarchy items synced from a connected Jira integration.
Sprint 9: Deep JIRA integration.

item_type values:
  epic      — top-level epic
  feature   — feature (may map to Epic children in some Jira configs)
  story     — user story (primary unit for acceptance criteria)
  task      — dev task
  bug       — bug report
  sub_task  — sub-task
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class JiraItem(Base):
    __tablename__ = "jira_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    integration_config_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("integration_configs.id", ondelete="CASCADE"), nullable=False
    )

    # Jira identifiers
    external_key: Mapped[str] = mapped_column(String(50), nullable=False)
    # e.g. "PROJ-123" — unique per tenant + integration
    project_key: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)

    # Item classification
    item_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # epic | feature | story | task | bug | sub_task

    # Core content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # acceptance_criteria: list of strings extracted from the Jira issue
    acceptance_criteria: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Status & priority
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # To Do | In Progress | In Review | Done | Closed
    priority: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # Blocker | Critical | Major | Minor | Trivial

    # People
    assignee: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    reporter: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Hierarchy
    epic_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    parent_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sprint_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)

    # Metadata
    labels: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    components: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Full raw Jira API response (for custom field extraction)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Link back to ontology brain (set after brain ingestion)
    ontology_concept_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ontology_concepts.id", ondelete="SET NULL"), nullable=True
    )

    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow, nullable=True)

    __table_args__ = (
        # Unique per tenant + integration + key to prevent duplicates on re-sync
        Index("ix_jira_items_tenant_key", "tenant_id", "integration_config_id", "external_key", unique=True),
    )
