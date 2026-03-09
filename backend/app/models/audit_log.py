"""
Audit Log model for tracking all user and system actions.
Provides comprehensive activity tracking for compliance and monitoring.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class AuditLog(Base):
    """
    Audit log entry tracking user actions and system events.

    Captures:
    - User CRUD operations on documents, code, repos, initiatives
    - Authentication events (login, logout)
    - Analysis triggers and completions
    - Settings and permission changes
    - System events (webhook triggers, scheduled tasks)
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Tenant isolation
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Who performed the action (null for system events)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # What action was performed
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # create, read, update, delete, login, logout, analyze, export, webhook

    # What type of resource was affected
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # document, repository, code_component, initiative, ontology, user, auth, settings, system

    # Which specific resource (optional)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resource_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Human-readable description
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Additional context (flexible JSON)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Status of the action
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="success"
    )  # success, failure, warning

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self):
        return (
            f"<AuditLog(id={self.id}, action={self.action}, "
            f"resource={self.resource_type}, user={self.user_email})>"
        )
