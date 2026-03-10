"""
Approval Workflow API Endpoints
Sprint 6.

Provides:
  POST   /approvals/              — Create a new approval request
  GET    /approvals/              — List approvals with filters
  GET    /approvals/pending       — List items awaiting the user's approval
  GET    /approvals/stats         — Approval statistics
  GET    /approvals/{id}          — Get single approval detail
  POST   /approvals/{id}/approve  — Approve an item
  POST   /approvals/{id}/reject   — Reject an item
  POST   /approvals/{id}/request-revision — Request changes
  GET    /approvals/history       — Audit trail of past decisions
  GET    /approvals/entity/{entity_type}/{entity_id} — Get approvals for a specific entity
"""
from typing import Any, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.api import deps
from app.db.session import get_db
from app.crud.crud_approval import approval as approval_crud
from app.schemas.approval import ApprovalCreate, ApprovalResolve, ApprovalResponse
from app.services import approval_service
from app.core.logging import get_logger

logger = get_logger("api.approvals")

router = APIRouter()


@router.post("/", response_model=ApprovalResponse)
def create_approval(
    data: ApprovalCreate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Create a new approval request."""
    try:
        obj = approval_service.request_approval(
            db=db,
            tenant_id=tenant_id,
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            entity_name=data.entity_name,
            requested_by=current_user,
            approval_level=data.approval_level,
            request_notes=data.request_notes,
        )
        return obj
    except Exception as e:
        logger.error(f"Failed to create approval: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/")
def list_approvals(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    status: Optional[str] = Query(None, description="Filter by status"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    search: Optional[str] = Query(None, description="Search in entity name/notes"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    """List approvals with filters."""
    items = approval_crud.get_multi(
        db=db,
        tenant_id=tenant_id,
        status=status,
        entity_type=entity_type,
        search=search,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [_serialize(a) for a in items],
        "total": approval_crud.count(db=db, tenant_id=tenant_id, status=status),
    }


@router.get("/pending")
def list_pending_approvals(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    entity_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    """List items awaiting approval that the current user can approve."""
    # Determine the user's max approval level
    max_level = _user_max_level(current_user)

    items = approval_crud.get_pending(
        db=db,
        tenant_id=tenant_id,
        entity_type=entity_type,
        approval_level=max_level,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [_serialize(a) for a in items],
        "total": len(items),
    }


@router.get("/stats")
def get_approval_stats(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get approval statistics."""
    return approval_crud.get_stats(db=db, tenant_id=tenant_id)


@router.get("/history")
def get_approval_history(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    """Get resolved approvals (audit trail of past decisions)."""
    items = approval_crud.get_multi(
        db=db,
        tenant_id=tenant_id,
        skip=skip,
        limit=limit,
    )
    resolved = [a for a in items if a.status != "pending"]
    return {
        "items": [_serialize(a) for a in resolved],
        "total": len(resolved),
    }


@router.get("/entity/{entity_type}/{entity_id}")
def get_entity_approvals(
    entity_type: str,
    entity_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get all approvals for a specific entity."""
    items = approval_crud.get_for_entity(
        db=db,
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return {"items": [_serialize(a) for a in items]}


@router.get("/{approval_id}")
def get_approval(
    approval_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get a single approval by ID."""
    obj = approval_crud.get(db=db, id=approval_id, tenant_id=tenant_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Approval not found")
    return _serialize(obj)


@router.post("/{approval_id}/approve")
def approve_item(
    approval_id: int,
    data: ApprovalResolve,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Approve a pending approval."""
    try:
        obj = approval_service.approve(
            db=db,
            approval_id=approval_id,
            tenant_id=tenant_id,
            resolved_by=current_user,
            resolution_notes=data.resolution_notes,
        )
        return _serialize(obj)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{approval_id}/reject")
def reject_item(
    approval_id: int,
    data: ApprovalResolve,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Reject a pending approval."""
    try:
        obj = approval_service.reject(
            db=db,
            approval_id=approval_id,
            tenant_id=tenant_id,
            resolved_by=current_user,
            resolution_notes=data.resolution_notes,
        )
        return _serialize(obj)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{approval_id}/request-revision")
def request_revision(
    approval_id: int,
    data: ApprovalResolve,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Request revision on a pending approval."""
    try:
        obj = approval_service.request_revision(
            db=db,
            approval_id=approval_id,
            tenant_id=tenant_id,
            resolved_by=current_user,
            resolution_notes=data.resolution_notes,
        )
        return _serialize(obj)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


def _user_max_level(user: models.User) -> int:
    """Determine the max approval level a user can handle based on roles."""
    roles = set(user.roles)
    if "CXO" in roles:
        return 3
    if "Admin" in roles:
        return 2
    return 1


def _serialize(a) -> dict:
    """Serialize an Approval model to dict."""
    return {
        "id": a.id,
        "tenant_id": a.tenant_id,
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "entity_name": a.entity_name,
        "status": a.status,
        "requested_by_id": a.requested_by_id,
        "requested_by_email": a.requested_by_email,
        "resolved_by_id": a.resolved_by_id,
        "resolved_by_email": a.resolved_by_email,
        "approval_level": a.approval_level,
        "request_notes": a.request_notes,
        "resolution_notes": a.resolution_notes,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
    }
