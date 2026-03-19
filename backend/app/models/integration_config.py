"""
IntegrationConfig model — stores OAuth credentials and settings for
third-party documentation integrations.
Sprint 8: Documentation Integrations (Module 11).
Sprint 9: Deep JIRA sync support.

provider values: notion, jira, confluence, sharepoint, slack
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # notion | jira | confluence | sharepoint

    # Display info
    workspace_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    workspace_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Auth — stored encrypted (plain for MVP; encrypt in production via field_encryption)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Jira-specific
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # e.g. https://mycompany.atlassian.net

    # Jira deep-sync config (Sprint 9) — stored as JSON, fully tenant-configurable
    # Example: {
    #   "project_keys": ["PROJ", "BE"],
    #   "sync_frequency": "hourly",            # manual | hourly | daily
    #   "custom_field_mappings": {             # maps AC field name per Jira instance
    #     "acceptance_criteria": "customfield_10100"
    #   },
    #   "include_subtasks": true,
    #   "webhook_secret": "abc123"             # HMAC secret for incoming Jira webhooks
    # }
    sync_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Connection state
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow, nullable=True)
