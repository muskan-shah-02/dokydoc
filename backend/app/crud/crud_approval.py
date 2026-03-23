"""
CRUD operations for Approval model.
Sprint 6: Approval Workflow.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.approval import Approval


class CRUDApproval:
    """CRUD operations for approval records."""

    def create(
        self,
        db: Session,
        *,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
        entity_name: Optional[str] = None,
        requested_by_id: int,
        requested_by_email: Optional[str] = None,
        approval_level: int = 1,
        request_notes: Optional[str] = None,
    ) -> Approval:
        """Create a new approval request."""
        obj = Approval(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            status="pending",
            requested_by_id=requested_by_id,
            requested_by_email=requested_by_email,
            approval_level=approval_level,
            request_notes=request_notes,
            created_at=datetime.utcnow(),
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get(self, db: Session, *, id: int, tenant_id: int) -> Optional[Approval]:
        """Get a single approval by ID."""
        return (
            db.query(Approval)
            .filter(Approval.id == id, Approval.tenant_id == tenant_id)
            .first()
        )

    def get_pending(
        self,
        db: Session,
        *,
        tenant_id: int,
        entity_type: Optional[str] = None,
        approval_level: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Approval]:
        """Get pending approvals, optionally filtered."""
        query = db.query(Approval).filter(
            Approval.tenant_id == tenant_id,
            Approval.status == "pending",
        )
        if entity_type:
            query = query.filter(Approval.entity_type == entity_type)
        if approval_level is not None:
            query = query.filter(Approval.approval_level <= approval_level)
        return (
            query.order_by(desc(Approval.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_multi(
        self,
        db: Session,
        *,
        tenant_id: int,
        status: Optional[str] = None,
        entity_type: Optional[str] = None,
        requested_by_id: Optional[int] = None,
        resolved_by_id: Optional[int] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Approval]:
        """Get approvals with filters."""
        query = db.query(Approval).filter(Approval.tenant_id == tenant_id)

        if status:
            query = query.filter(Approval.status == status)
        if entity_type:
            query = query.filter(Approval.entity_type == entity_type)
        if requested_by_id:
            query = query.filter(Approval.requested_by_id == requested_by_id)
        if resolved_by_id:
            query = query.filter(Approval.resolved_by_id == resolved_by_id)
        if search:
            query = query.filter(
                Approval.entity_name.ilike(f"%{search}%")
                | Approval.request_notes.ilike(f"%{search}%")
                | Approval.requested_by_email.ilike(f"%{search}%")
            )

        return (
            query.order_by(desc(Approval.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(
        self,
        db: Session,
        *,
        tenant_id: int,
        status: Optional[str] = None,
    ) -> int:
        """Count approvals matching filters."""
        query = db.query(func.count(Approval.id)).filter(
            Approval.tenant_id == tenant_id
        )
        if status:
            query = query.filter(Approval.status == status)
        return query.scalar() or 0

    def resolve(
        self,
        db: Session,
        *,
        approval: Approval,
        status: str,
        resolved_by_id: int,
        resolved_by_email: Optional[str] = None,
        resolution_notes: Optional[str] = None,
    ) -> Approval:
        """Resolve an approval (approve / reject / request revision)."""
        approval.status = status
        approval.resolved_by_id = resolved_by_id
        approval.resolved_by_email = resolved_by_email
        approval.resolution_notes = resolution_notes
        approval.resolved_at = datetime.utcnow()
        approval.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(approval)
        return approval

    def get_stats(
        self,
        db: Session,
        *,
        tenant_id: int,
    ) -> Dict[str, Any]:
        """Get approval statistics."""
        base = db.query(Approval).filter(Approval.tenant_id == tenant_id)

        total = base.count()
        pending = base.filter(Approval.status == "pending").count()
        approved = base.filter(Approval.status == "approved").count()
        rejected = base.filter(Approval.status == "rejected").count()
        revision_requested = base.filter(Approval.status == "revision_requested").count()

        # By entity type
        by_type = (
            db.query(Approval.entity_type, func.count(Approval.id))
            .filter(Approval.tenant_id == tenant_id)
            .group_by(Approval.entity_type)
            .all()
        )

        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "revision_requested": revision_requested,
            "by_entity_type": {t: c for t, c in by_type},
        }

    def get_for_entity(
        self,
        db: Session,
        *,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
    ) -> List[Approval]:
        """Get all approvals for a specific entity."""
        return (
            db.query(Approval)
            .filter(
                Approval.tenant_id == tenant_id,
                Approval.entity_type == entity_type,
                Approval.entity_id == entity_id,
            )
            .order_by(desc(Approval.created_at))
            .all()
        )


# Singleton
approval = CRUDApproval()
