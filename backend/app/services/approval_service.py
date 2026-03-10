"""
Approval Service — Multi-level approval workflow logic.
Sprint 6.

Provides:
  - Per-tenant approval policies (who can approve what)
  - Multi-level approval chains (Developer -> Lead -> CXO)
  - Auto-approve low-risk items
  - Notification integration
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from app.crud.crud_approval import approval as approval_crud
from app.models.approval import Approval
from app.models.user import User
from app.services.notification_service import notify
from app.core.logging import get_logger

logger = get_logger("approval_service")

# Map approval_level -> minimum role required to approve
LEVEL_ROLE_MAP = {
    1: {"Developer", "BA", "Product Manager", "Admin", "CXO"},  # Peer review
    2: {"Admin", "CXO"},  # Managerial
    3: {"CXO"},  # Executive
}

# Entity types that auto-approve at "info" severity (level 1)
AUTO_APPROVE_ENTITY_TYPES = {"mismatch_resolution"}


def can_user_approve(user: User, approval: Approval) -> bool:
    """Check if user has the required role to approve at this level."""
    required_roles = LEVEL_ROLE_MAP.get(approval.approval_level, {"CXO"})
    user_role_set = set(user.roles)
    return bool(user_role_set & required_roles)


def request_approval(
    db: Session,
    *,
    tenant_id: int,
    entity_type: str,
    entity_id: int,
    entity_name: Optional[str] = None,
    requested_by: User,
    approval_level: int = 1,
    request_notes: Optional[str] = None,
) -> Approval:
    """
    Create a new approval request.
    Auto-approves low-risk items if applicable.
    """
    # Auto-approve low-risk items (level 1, info severity types)
    if approval_level == 1 and entity_type in AUTO_APPROVE_ENTITY_TYPES:
        logger.info(
            f"Auto-approving low-risk {entity_type}#{entity_id} for tenant {tenant_id}"
        )
        obj = approval_crud.create(
            db=db,
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            requested_by_id=requested_by.id,
            requested_by_email=requested_by.email,
            approval_level=approval_level,
            request_notes=request_notes,
        )
        return approval_crud.resolve(
            db=db,
            approval=obj,
            status="approved",
            resolved_by_id=requested_by.id,
            resolved_by_email=requested_by.email,
            resolution_notes="Auto-approved (low-risk item)",
        )

    obj = approval_crud.create(
        db=db,
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        requested_by_id=requested_by.id,
        requested_by_email=requested_by.email,
        approval_level=approval_level,
        request_notes=request_notes,
    )

    # Notify approvers (users with required roles)
    _notify_approvers(
        db=db,
        tenant_id=tenant_id,
        approval=obj,
    )

    logger.info(
        f"Approval requested: {entity_type}#{entity_id} (level {approval_level}) "
        f"by {requested_by.email}"
    )
    return obj


def approve(
    db: Session,
    *,
    approval_id: int,
    tenant_id: int,
    resolved_by: User,
    resolution_notes: Optional[str] = None,
) -> Approval:
    """Approve a pending approval."""
    obj = approval_crud.get(db=db, id=approval_id, tenant_id=tenant_id)
    if not obj:
        raise ValueError("Approval not found")
    if obj.status != "pending":
        raise ValueError(f"Approval is already {obj.status}")
    if not can_user_approve(resolved_by, obj):
        raise PermissionError(
            f"User does not have required role for level {obj.approval_level} approval"
        )

    result = approval_crud.resolve(
        db=db,
        approval=obj,
        status="approved",
        resolved_by_id=resolved_by.id,
        resolved_by_email=resolved_by.email,
        resolution_notes=resolution_notes,
    )

    # Notify requester
    notify(
        db=db,
        tenant_id=tenant_id,
        user_id=obj.requested_by_id,
        notification_type="approval_resolved",
        title="Approval Granted",
        message=f"Your {obj.entity_type} approval for '{obj.entity_name or obj.entity_id}' has been approved by {resolved_by.email}.",
        resource_type="approval",
        resource_id=obj.id,
    )

    logger.info(f"Approval #{approval_id} approved by {resolved_by.email}")
    return result


def reject(
    db: Session,
    *,
    approval_id: int,
    tenant_id: int,
    resolved_by: User,
    resolution_notes: Optional[str] = None,
) -> Approval:
    """Reject a pending approval."""
    obj = approval_crud.get(db=db, id=approval_id, tenant_id=tenant_id)
    if not obj:
        raise ValueError("Approval not found")
    if obj.status != "pending":
        raise ValueError(f"Approval is already {obj.status}")
    if not can_user_approve(resolved_by, obj):
        raise PermissionError(
            f"User does not have required role for level {obj.approval_level} approval"
        )

    result = approval_crud.resolve(
        db=db,
        approval=obj,
        status="rejected",
        resolved_by_id=resolved_by.id,
        resolved_by_email=resolved_by.email,
        resolution_notes=resolution_notes,
    )

    notify(
        db=db,
        tenant_id=tenant_id,
        user_id=obj.requested_by_id,
        notification_type="approval_resolved",
        title="Approval Rejected",
        message=f"Your {obj.entity_type} approval for '{obj.entity_name or obj.entity_id}' has been rejected by {resolved_by.email}.",
        resource_type="approval",
        resource_id=obj.id,
    )

    logger.info(f"Approval #{approval_id} rejected by {resolved_by.email}")
    return result


def request_revision(
    db: Session,
    *,
    approval_id: int,
    tenant_id: int,
    resolved_by: User,
    resolution_notes: Optional[str] = None,
) -> Approval:
    """Request revision on a pending approval."""
    obj = approval_crud.get(db=db, id=approval_id, tenant_id=tenant_id)
    if not obj:
        raise ValueError("Approval not found")
    if obj.status != "pending":
        raise ValueError(f"Approval is already {obj.status}")
    if not can_user_approve(resolved_by, obj):
        raise PermissionError(
            f"User does not have required role for level {obj.approval_level} approval"
        )

    result = approval_crud.resolve(
        db=db,
        approval=obj,
        status="revision_requested",
        resolved_by_id=resolved_by.id,
        resolved_by_email=resolved_by.email,
        resolution_notes=resolution_notes,
    )

    notify(
        db=db,
        tenant_id=tenant_id,
        user_id=obj.requested_by_id,
        notification_type="approval_resolved",
        title="Revision Requested",
        message=f"Revision requested on your {obj.entity_type} approval for '{obj.entity_name or obj.entity_id}' by {resolved_by.email}.",
        resource_type="approval",
        resource_id=obj.id,
    )

    logger.info(f"Approval #{approval_id} revision requested by {resolved_by.email}")
    return result


def _notify_approvers(
    db: Session,
    *,
    tenant_id: int,
    approval: Approval,
) -> None:
    """Notify users who can approve this request."""
    required_roles = LEVEL_ROLE_MAP.get(approval.approval_level, {"CXO"})

    users = db.query(User).filter(User.tenant_id == tenant_id).all()
    for user in users:
        if user.id == approval.requested_by_id:
            continue  # Don't notify the requester
        user_role_set = set(user.roles)
        if user_role_set & required_roles:
            notify(
                db=db,
                tenant_id=tenant_id,
                user_id=user.id,
                notification_type="approval_pending",
                title="Approval Required",
                message=f"{approval.requested_by_email} is requesting approval for {approval.entity_type} '{approval.entity_name or approval.entity_id}'.",
                resource_type="approval",
                resource_id=approval.id,
            )
