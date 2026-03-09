"""
Notification API Endpoints

Provides endpoints for:
  GET    /notifications/         — List notifications for current user
  GET    /notifications/unread   — Count unread notifications
  PUT    /notifications/{id}/read — Mark notification as read
  PUT    /notifications/read-all  — Mark all as read
"""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models
from app.api import deps
from app.db.session import get_db
from app.crud.crud_notification import notification as notification_crud
from app.core.logging import get_logger

logger = get_logger("api.notifications")

router = APIRouter()


@router.get("/")
def list_notifications(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    unread_only: bool = Query(False, description="Only return unread"),
    skip: int = 0,
    limit: int = 50,
) -> Any:
    """List notifications for the current user."""
    notifications = notification_crud.get_for_user(
        db=db,
        user_id=current_user.id,
        tenant_id=tenant_id,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )

    return [
        {
            "id": n.id,
            "type": n.notification_type,
            "title": n.title,
            "message": n.message,
            "resource_type": n.resource_type,
            "resource_id": n.resource_id,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "read_at": n.read_at.isoformat() if n.read_at else None,
            "details": n.details,
        }
        for n in notifications
    ]


@router.get("/unread")
def count_unread(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get count of unread notifications."""
    count = notification_crud.count_unread(
        db=db, user_id=current_user.id, tenant_id=tenant_id
    )
    return {"unread_count": count}


@router.put("/{notification_id}/read")
def mark_read(
    notification_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Mark a notification as read."""
    result = notification_crud.mark_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
        tenant_id=tenant_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "read", "id": notification_id}


@router.put("/read-all")
def mark_all_read(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Mark all notifications as read for the current user."""
    count = notification_crud.mark_all_read(
        db=db, user_id=current_user.id, tenant_id=tenant_id
    )
    return {"status": "all_read", "count": count}
