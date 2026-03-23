"""
NotificationPreference model — controls which notification types appear in a user's feed.
Sprint 8: Notification Preferences Feature.
"""
from sqlalchemy import Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    # In-app notification toggles (True = show, False = suppress)
    analysis_complete: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    analysis_failed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validation_alert: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mention: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
