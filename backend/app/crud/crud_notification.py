"""
CRUD operations for Notification model.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.notification import Notification


class CRUDNotification:
    """CRUD operations for notifications."""

    def create(
        self,
        db: Session,
        *,
        tenant_id: int,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[dict] = None,
    ) -> Notification:
        """Create a new notification."""
        obj = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            is_read=False,
            email_sent=False,
            created_at=datetime.utcnow(),
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get_for_user(
        self,
        db: Session,
        *,
        user_id: int,
        tenant_id: int,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Notification]:
        """Get notifications for a user."""
        query = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.tenant_id == tenant_id,
        )
        if unread_only:
            query = query.filter(Notification.is_read == False)
        return (
            query.order_by(desc(Notification.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_unread(
        self,
        db: Session,
        *,
        user_id: int,
        tenant_id: int,
    ) -> int:
        """Count unread notifications for a user."""
        return (
            db.query(func.count(Notification.id))
            .filter(
                Notification.user_id == user_id,
                Notification.tenant_id == tenant_id,
                Notification.is_read == False,
            )
            .scalar()
            or 0
        )

    def mark_read(
        self,
        db: Session,
        *,
        notification_id: int,
        user_id: int,
        tenant_id: int,
    ) -> Optional[Notification]:
        """Mark a notification as read."""
        obj = (
            db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.tenant_id == tenant_id,
            )
            .first()
        )
        if obj:
            obj.is_read = True
            obj.read_at = datetime.utcnow()
            db.commit()
            db.refresh(obj)
        return obj

    def mark_all_read(
        self,
        db: Session,
        *,
        user_id: int,
        tenant_id: int,
    ) -> int:
        """Mark all notifications as read for a user. Returns count updated."""
        count = (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.tenant_id == tenant_id,
                Notification.is_read == False,
            )
            .update(
                {"is_read": True, "read_at": datetime.utcnow()},
                synchronize_session=False,
            )
        )
        db.commit()
        return count

    def delete_old(
        self,
        db: Session,
        *,
        tenant_id: int,
        days: int = 90,
    ) -> int:
        """Delete notifications older than N days."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        count = (
            db.query(Notification)
            .filter(
                Notification.tenant_id == tenant_id,
                Notification.created_at < cutoff,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        return count


# Singleton
notification = CRUDNotification()
