"""
CRUD operations for NotificationPreference model.
Sprint 8: Notification Preferences Feature.
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.models.notification_preference import NotificationPreference


class CRUDNotificationPreference:

    def get_or_create_defaults(
        self, db: Session, *, user_id: int, tenant_id: int
    ) -> NotificationPreference:
        """Return existing preferences, or create with all-True defaults on first call."""
        obj = db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).first()
        if obj is None:
            obj = NotificationPreference(
                user_id=user_id,
                tenant_id=tenant_id,
                analysis_complete=True,
                analysis_failed=True,
                validation_alert=True,
                mention=True,
                system=True,
            )
            db.add(obj)
            db.commit()
            db.refresh(obj)
        return obj

    def update(
        self,
        db: Session,
        *,
        user_id: int,
        tenant_id: int,
        update_data: dict,
    ) -> NotificationPreference:
        """Update preference toggles. Creates with defaults first if not yet present."""
        obj = self.get_or_create_defaults(db, user_id=user_id, tenant_id=tenant_id)
        allowed = {"analysis_complete", "analysis_failed", "validation_alert", "mention", "system"}
        for field, value in update_data.items():
            if field in allowed and isinstance(value, bool):
                setattr(obj, field, value)
        db.commit()
        db.refresh(obj)
        return obj

    def is_enabled(
        self, db: Session, *, user_id: int, notification_type: str
    ) -> bool:
        """Return True if this notification type is enabled for the user (default True if no record)."""
        obj = db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).first()
        if obj is None:
            return True
        return bool(getattr(obj, notification_type, True))


crud_notification_preference = CRUDNotificationPreference()
