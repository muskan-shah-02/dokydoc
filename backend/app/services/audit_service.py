"""
Audit Service — Helper for logging audit events from any endpoint.

Usage:
    from app.services.audit_service import log_audit

    log_audit(
        db=db,
        tenant_id=tenant_id,
        user=current_user,
        action="create",
        resource_type="document",
        resource_id=doc.id,
        resource_name=doc.filename,
        description=f"Uploaded document: {doc.filename}",
        request=request,  # Optional: extracts IP and user-agent
    )
"""
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import Request

from app.crud.crud_audit_log import audit_log
from app.core.logging import get_logger

logger = get_logger("audit_service")


def log_audit(
    db: Session,
    *,
    tenant_id: int,
    user: Optional[object] = None,
    action: str,
    resource_type: str,
    description: str,
    resource_id: Optional[int] = None,
    resource_name: Optional[str] = None,
    request: Optional[Request] = None,
    details: Optional[dict] = None,
    status: str = "success",
) -> None:
    """
    Log an audit event. Fails silently to never break the main operation.
    """
    try:
        user_id = getattr(user, "id", None) if user else None
        user_email = getattr(user, "email", None) if user else None
        ip_address = None
        user_agent = None

        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent", "")[:500]

        audit_log.log(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            status=status,
        )
    except Exception as e:
        # Never fail the main operation due to audit logging
        logger.warning(f"Audit logging failed (non-fatal): {e}")
