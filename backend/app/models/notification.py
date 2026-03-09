"""
Notification model for in-app and email notifications.
Tracks notifications sent to users about analysis completions, errors, etc.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, JSON, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class Notification(Base):
    """
    In-app notification for users.

    Types:
    - analysis_complete: Document or repo analysis finished
    - analysis_failed: Analysis encountered errors
    - validation_alert: Mismatches detected
    - system: System-level messages
    - mention: User mentioned in a task/comment
    """
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Tenant isolation
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Target user
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )

    # Notification type
    notification_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # analysis_complete, analysis_failed, validation_alert, system, mention

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional link to a resource
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Read status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Email sent status
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Extra data
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self):
        return (
            f"<Notification(id={self.id}, type={self.notification_type}, "
            f"user_id={self.user_id}, read={self.is_read})>"
        )
