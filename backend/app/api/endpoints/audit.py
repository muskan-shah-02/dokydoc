"""
Audit Trail & Sync Timeline API Endpoints

Provides endpoints for:
  GET  /audit/logs          — List audit log entries with filters (cursor-paginated)
  GET  /audit/stats         — Get audit statistics
  GET  /audit/timeline      — Get timeline-formatted events for sync timeline (cursor-paginated)
  GET  /audit/export        — Export audit logs as JSON
  GET  /audit/export/pdf    — Export audit logs as PDF (Sprint 6)
"""
from typing import Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io
import csv

from app import models
from app.api import deps
from app.api.pagination import paginate_query
from app.db.session import get_db
from app.crud.crud_audit_log import audit_log
from app.core.logging import get_logger

logger = get_logger("api.audit")

router = APIRouter()


@router.get("/logs")
def list_audit_logs(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    search: Optional[str] = Query(None, description="Search in description/resource/user"),
    days: int = Query(30, description="Look back N days"),
    cursor: Optional[int] = Query(None, description="Cursor (last ID from previous page)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
) -> Any:
    """List audit log entries with filters and cursor-based pagination."""
    query = audit_log.build_query(
        db=db,
        tenant_id=tenant_id,
        action=action,
        resource_type=resource_type,
        search=search,
        days=days,
    )

    from app.models.audit_log import AuditLog
    page = paginate_query(query, AuditLog.id, cursor=cursor, page_size=page_size)

    page["items"] = [
        {
            "id": log.id,
            "timestamp": log.created_at.isoformat() if log.created_at else None,
            "user": {
                "id": log.user_id,
                "email": log.user_email or "system",
                "role": "System" if not log.user_id else "User",
            },
            "action": log.action,
            "action_type": log.action,
            "resource": log.resource_name or f"{log.resource_type}#{log.resource_id}",
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "description": log.description,
            "ip_address": log.ip_address or "—",
            "status": log.status,
            "details": log.details,
        }
        for log in page["items"]
    ]

    return page


@router.get("/stats")
def get_audit_stats(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    days: int = Query(30, description="Look back N days"),
) -> Any:
    """Get audit log statistics for dashboard cards."""
    return audit_log.get_stats(db=db, tenant_id=tenant_id, days=days)


@router.get("/timeline")
def get_timeline_events(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    days: int = Query(7, description="Look back N days"),
    cursor: Optional[int] = Query(None, description="Cursor (last ID from previous page)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
) -> Any:
    """
    Get timeline-formatted events for the Sync Timeline page.
    Returns events in reverse chronological order with cursor-based pagination.
    """
    event_types = [event_type] if event_type else None
    query = audit_log.build_timeline_query(
        db=db,
        tenant_id=tenant_id,
        days=days,
        event_types=event_types,
    )

    from app.models.audit_log import AuditLog
    page = paginate_query(query, AuditLog.id, cursor=cursor, page_size=page_size)

    events = []
    for log in page["items"]:
        event_type_mapped = _map_event_type(log.action, log.resource_type)

        events.append({
            "id": log.id,
            "type": event_type_mapped,
            "title": _format_title(log.action, log.resource_type),
            "description": log.description,
            "timestamp": log.created_at.isoformat() if log.created_at else None,
            "status": log.status,
            "user_email": log.user_email,
            "related_item": {
                "type": log.resource_type,
                "name": log.resource_name or "",
                "id": log.resource_id,
            } if log.resource_id else None,
        })

    page["items"] = events
    return page


@router.get("/export")
def export_audit_logs(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    days: int = Query(30, description="Look back N days"),
    limit: int = Query(1000, description="Max records"),
) -> Any:
    """Export audit logs as JSON for compliance/archival."""
    logs = audit_log.get_multi(
        db=db, tenant_id=tenant_id, days=days, skip=0, limit=limit
    )

    return {
        "exported_at": __import__("datetime").datetime.utcnow().isoformat(),
        "tenant_id": tenant_id,
        "total_records": len(logs),
        "records": [
            {
                "id": log.id,
                "timestamp": log.created_at.isoformat() if log.created_at else None,
                "user_email": log.user_email,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "resource_name": log.resource_name,
                "description": log.description,
                "ip_address": log.ip_address,
                "status": log.status,
                "details": log.details,
            }
            for log in logs
        ],
    }


@router.get("/export/pdf")
def export_audit_logs_pdf(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    days: int = Query(30, ge=1, le=365, description="Look back N days"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    limit: int = Query(2000, ge=1, le=10000, description="Max records"),
) -> Any:
    """
    Export audit logs as a CSV file (Sprint 6).
    Supports date range filtering for compliance reports.
    """
    # Calculate effective days from date range if provided
    effective_days = days
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
            effective_days = max(1, (datetime.utcnow() - from_date).days + 1)
        except ValueError:
            pass

    logs = audit_log.get_multi(
        db=db,
        tenant_id=tenant_id,
        action=action,
        resource_type=resource_type,
        days=effective_days,
        skip=0,
        limit=limit,
    )

    # Apply date_to filter if provided
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            logs = [log for log in logs if log.created_at and log.created_at <= to_date]
        except ValueError:
            pass

    # Apply date_from filter for precision
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
            logs = [log for log in logs if log.created_at and log.created_at >= from_date]
        except ValueError:
            pass

    # Generate CSV (universally readable, can be opened in Excel for PDF printing)
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID", "Timestamp", "User Email", "Action", "Resource Type",
        "Resource ID", "Resource Name", "Description", "IP Address",
        "Status",
    ])

    for log in logs:
        writer.writerow([
            log.id,
            log.created_at.isoformat() if log.created_at else "",
            log.user_email or "system",
            log.action,
            log.resource_type,
            log.resource_id or "",
            log.resource_name or "",
            log.description,
            log.ip_address or "",
            log.status,
        ])

    output.seek(0)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"audit_report_{tenant_id}_{timestamp}.csv"

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _map_event_type(action: str, resource_type: str) -> str:
    """Map action + resource to a user-friendly event type."""
    mapping = {
        ("create", "document"): "document_upload",
        ("create", "repository"): "code_register",
        ("create", "code_component"): "code_register",
        ("analyze", "document"): "analysis_complete",
        ("analyze", "repository"): "analysis_complete",
        ("analyze", "code_component"): "analysis_complete",
        ("update", "ontology"): "validation_run",
        ("create", "ontology"): "validation_run",
        ("login", "auth"): "login",
        ("logout", "auth"): "logout",
    }
    return mapping.get((action, resource_type), "system_event")


def _format_title(action: str, resource_type: str) -> str:
    """Create a user-friendly title for the event."""
    titles = {
        ("create", "document"): "Document Uploaded",
        ("create", "repository"): "Repository Onboarded",
        ("create", "code_component"): "Code Component Registered",
        ("delete", "document"): "Document Deleted",
        ("delete", "repository"): "Repository Deleted",
        ("delete", "code_component"): "Code Component Deleted",
        ("analyze", "document"): "Analysis Completed",
        ("analyze", "repository"): "Repository Analysis Triggered",
        ("analyze", "code_component"): "File Analysis Completed",
        ("update", "document"): "Document Updated",
        ("update", "repository"): "Repository Updated",
        ("create", "initiative"): "Project Created",
        ("delete", "initiative"): "Project Deleted",
        ("create", "ontology"): "Ontology Concept Created",
        ("update", "ontology"): "Ontology Updated",
        ("login", "auth"): "User Logged In",
        ("logout", "auth"): "User Logged Out",
        ("export", "document"): "Data Exported",
        ("webhook", "system"): "Webhook Received",
    }
    return titles.get(
        (action, resource_type),
        f"{action.title()} {resource_type.replace('_', ' ').title()}"
    )
