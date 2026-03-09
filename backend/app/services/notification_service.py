"""
Notification Service — Helper for sending notifications from any part of the app.

Usage:
    from app.services.notification_service import notify

    notify(
        db=db,
        tenant_id=1,
        user_id=5,
        notification_type="analysis_complete",
        title="Analysis Complete",
        message="Your document 'BRD v2.pdf' has been analyzed.",
        resource_type="document",
        resource_id=42,
    )
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from app.crud.crud_notification import notification as notification_crud
from app.core.logging import get_logger

logger = get_logger("notification_service")


def notify(
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
) -> None:
    """
    Send an in-app notification. Fails silently to never break the main operation.
    """
    try:
        notification_crud.create(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
    except Exception as e:
        logger.warning(f"Notification send failed (non-fatal): {e}")


def notify_all_users(
    db: Session,
    *,
    tenant_id: int,
    notification_type: str,
    title: str,
    message: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
) -> int:
    """
    Send a notification to all users in a tenant.
    Returns count of notifications created.
    """
    try:
        from app.models.user import User
        users = db.query(User).filter(User.tenant_id == tenant_id).all()
        count = 0
        for user in users:
            notify(
                db=db,
                tenant_id=tenant_id,
                user_id=user.id,
                notification_type=notification_type,
                title=title,
                message=message,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            count += 1
        return count
    except Exception as e:
        logger.warning(f"Bulk notification failed: {e}")
        return 0
