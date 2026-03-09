"""
CRUD operations for AuditLog model.
Provides methods for logging and querying audit events.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.audit_log import AuditLog


class CRUDAuditLog:
    """CRUD operations for audit log entries."""

    def log(
        self,
        db: Session,
        *,
        tenant_id: int,
        action: str,
        resource_type: str,
        description: str,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        resource_id: Optional[int] = None,
        resource_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[dict] = None,
        status: str = "success",
    ) -> AuditLog:
        """Create a new audit log entry."""
        entry = AuditLog(
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
            created_at=datetime.utcnow(),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    def build_query(
        self,
        db: Session,
        *,
        tenant_id: int,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        user_id: Optional[int] = None,
        search: Optional[str] = None,
        days: int = 30,
    ):
        """Build a filtered query for audit logs (without ordering/pagination)."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = db.query(AuditLog).filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= cutoff,
        )

        if action:
            query = query.filter(AuditLog.action == action)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if search:
            query = query.filter(
                AuditLog.description.ilike(f"%{search}%")
                | AuditLog.resource_name.ilike(f"%{search}%")
                | AuditLog.user_email.ilike(f"%{search}%")
            )

        return query

    def get_multi(
        self,
        db: Session,
        *,
        tenant_id: int,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        user_id: Optional[int] = None,
        search: Optional[str] = None,
        days: int = 30,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get audit logs with filters (offset-based, kept for export/backward compat)."""
        query = self.build_query(
            db=db,
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            user_id=user_id,
            search=search,
            days=days,
        )

        return (
            query.order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(
        self,
        db: Session,
        *,
        tenant_id: int,
        days: int = 30,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> int:
        """Count audit logs matching filters."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = db.query(func.count(AuditLog.id)).filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= cutoff,
        )
        if action:
            query = query.filter(AuditLog.action == action)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        return query.scalar() or 0

    def get_stats(
        self,
        db: Session,
        *,
        tenant_id: int,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get audit log statistics."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        base = db.query(AuditLog).filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= cutoff,
        )

        total = base.count()

        # Action breakdown
        action_counts = (
            db.query(AuditLog.action, func.count(AuditLog.id))
            .filter(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at >= cutoff,
            )
            .group_by(AuditLog.action)
            .all()
        )

        # Resource type breakdown
        resource_counts = (
            db.query(AuditLog.resource_type, func.count(AuditLog.id))
            .filter(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at >= cutoff,
            )
            .group_by(AuditLog.resource_type)
            .all()
        )

        # Status breakdown
        status_counts = (
            db.query(AuditLog.status, func.count(AuditLog.id))
            .filter(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at >= cutoff,
            )
            .group_by(AuditLog.status)
            .all()
        )

        return {
            "total_events": total,
            "by_action": {a: c for a, c in action_counts},
            "by_resource": {r: c for r, c in resource_counts},
            "by_status": {s: c for s, c in status_counts},
            "period_days": days,
        }

    def build_timeline_query(
        self,
        db: Session,
        *,
        tenant_id: int,
        days: int = 7,
        event_types: Optional[List[str]] = None,
    ):
        """Build a filtered query for timeline events (without ordering/pagination)."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = db.query(AuditLog).filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= cutoff,
        )

        if event_types:
            query = query.filter(AuditLog.resource_type.in_(event_types))

        return query

    def get_timeline(
        self,
        db: Session,
        *,
        tenant_id: int,
        days: int = 7,
        event_types: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AuditLog]:
        """Get timeline-friendly audit events (offset-based, kept for backward compat)."""
        query = self.build_timeline_query(
            db=db,
            tenant_id=tenant_id,
            days=days,
            event_types=event_types,
        )

        return (
            query.order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )


# Singleton
audit_log = CRUDAuditLog()
