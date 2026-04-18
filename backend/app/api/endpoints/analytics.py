"""
Analytics API endpoints — Sprint 8: Analytics Dashboard

Provides aggregated metrics for the analytics dashboard:
  GET /overview   — combined usage summary
  GET /costs      — daily cost time-series grouped by feature
  GET /concepts   — ontology concept & relationship growth over time
  GET /activity   — high-level entity counts across the tenant
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Any

from app.api import deps
from app import models
from app.db.session import get_db
from app.core.logging import get_logger
from app.services import analytics_service

logger = get_logger("api.analytics")

router = APIRouter()


@router.get("/overview")
def get_analytics_overview(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Return a combined analytics summary for the dashboard overview card.

    Includes:
    - total_cost_inr: all-time spend in INR
    - total_tokens: all-time token consumption
    - total_operations: all-time operation count
    - this_month_cost: current calendar-month spend in INR
    - active_features: number of distinct feature types with usage
    """
    logger.info(
        f"Fetching analytics overview for tenant {tenant_id}, user {current_user.email}"
    )
    result = analytics_service.get_overview(db=db, tenant_id=tenant_id)
    logger.info(
        f"Analytics overview retrieved for tenant {tenant_id}: "
        f"total_operations={result['total_operations']}, "
        f"this_month_cost=₹{result['this_month_cost']}"
    )
    return result


@router.get("/costs")
def get_cost_breakdown(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    period: str = Query(default="month", description="Time period: week | month | quarter | year"),
):
    """
    Return daily cost time-series grouped by date and feature_type.

    Query Parameters:
    - period: week (7d), month (30d), quarter (90d), year (365d). Default: month.

    Each data point includes:
    - date: ISO date (YYYY-MM-DD)
    - cost_inr: aggregated cost in INR
    - feature_type: document_analysis | code_analysis | validation | chat | summary | other
    - operation_count: number of API operations logged
    """
    logger.info(
        f"Fetching cost breakdown for tenant {tenant_id}, user {current_user.email}, period={period}"
    )
    result = analytics_service.get_cost_breakdown(db=db, tenant_id=tenant_id, period=period)
    logger.info(
        f"Cost breakdown retrieved for tenant {tenant_id}: {len(result)} data points"
    )
    return result


@router.get("/concepts")
def get_concept_growth(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    period: str = Query(default="week", description="Time period: week | month | quarter | year"),
):
    """
    Return daily ontology concept and relationship growth over the period.

    Query Parameters:
    - period: week (7d), month (30d), quarter (90d), year (365d). Default: week.

    Each data point includes:
    - date: ISO date (YYYY-MM-DD)
    - concept_count: new concepts created on that day
    - relationship_count: new relationships created on that day
    """
    logger.info(
        f"Fetching concept growth for tenant {tenant_id}, user {current_user.email}, period={period}"
    )
    result = analytics_service.get_concept_growth(db=db, tenant_id=tenant_id, period=period)
    logger.info(
        f"Concept growth retrieved for tenant {tenant_id}: {len(result)} data points"
    )
    return result


@router.get("/activity")
def get_activity_metrics(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Return high-level entity activity counts for the tenant.

    Includes:
    - total_documents: number of documents uploaded
    - total_repos: number of repositories connected
    - total_concepts: number of ontology concepts extracted
    - total_chat_messages: number of chat AI operations
    - total_validations: number of validation AI operations
    """
    logger.info(
        f"Fetching activity metrics for tenant {tenant_id}, user {current_user.email}"
    )
    result = analytics_service.get_activity_metrics(db=db, tenant_id=tenant_id)
    logger.info(
        f"Activity metrics retrieved for tenant {tenant_id}: "
        f"documents={result['total_documents']}, repos={result['total_repos']}, "
        f"concepts={result['total_concepts']}"
    )
    return result


# ── P5C-09: Cross-Project Aggregate Compliance Dashboard ─────────────────────

@router.get("/compliance-overview")
def get_compliance_overview(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    P5C-09: CTO/VP dashboard — aggregate compliance across all documents in the tenant.
    Returns overall compliance %, per-document breakdown, mismatch severity, regulatory risk,
    and QA time saved estimate.
    """
    from app.models.document import Document
    from app.models.requirement_atom import RequirementAtom
    from app.models.mismatch import Mismatch
    from app.models.compliance_score_snapshot import ComplianceScoreSnapshot
    from app.models.tenant import Tenant
    from sqlalchemy import func, distinct
    from datetime import date

    docs_with_atoms = db.query(
        RequirementAtom.document_id,
        func.count(RequirementAtom.id).label("atom_count"),
    ).filter(RequirementAtom.tenant_id == tenant_id).group_by(RequirementAtom.document_id).all()

    doc_ids = [r.document_id for r in docs_with_atoms]
    atom_count_by_doc = {r.document_id: r.atom_count for r in docs_with_atoms}

    if not doc_ids:
        return {
            "tenant_id": tenant_id, "total_documents": 0, "total_atoms": 0,
            "overall_compliance_pct": 100.0, "total_open_mismatches": 0,
            "mismatch_breakdown": {}, "regulatory_risk": {},
            "qa_time_saved_hours": 0.0, "auto_testable_atoms": 0,
            "qa_baseline_hours_per_atom": 0.5, "projects": [],
            "generated_at": date.today().isoformat(),
        }

    latest_subq = db.query(
        ComplianceScoreSnapshot.document_id,
        func.max(ComplianceScoreSnapshot.snapshot_date).label("latest_date"),
    ).filter(
        ComplianceScoreSnapshot.tenant_id == tenant_id,
        ComplianceScoreSnapshot.document_id.in_(doc_ids),
    ).group_by(ComplianceScoreSnapshot.document_id).subquery()

    latest_snapshots = db.query(ComplianceScoreSnapshot).join(
        latest_subq,
        (ComplianceScoreSnapshot.document_id == latest_subq.c.document_id) &
        (ComplianceScoreSnapshot.snapshot_date == latest_subq.c.latest_date),
    ).all()
    score_by_doc = {s.document_id: s for s in latest_snapshots}

    docs = db.query(Document).filter(Document.id.in_(doc_ids), Document.tenant_id == tenant_id).all()
    doc_meta = {d.id: d for d in docs}

    mismatch_rows = db.query(
        Mismatch.severity, func.count(Mismatch.id).label("count"),
    ).filter(
        Mismatch.tenant_id == tenant_id,
        Mismatch.document_id.in_(doc_ids),
        Mismatch.status.in_(["open", "in_progress"]),
    ).group_by(Mismatch.severity).all()

    mismatch_breakdown = {r.severity: r.count for r in mismatch_rows}
    total_open_mismatches = sum(mismatch_breakdown.values())

    regulatory_risk: dict = {}
    try:
        reg_rows = db.execute(
            """
            SELECT ra.regulatory_tags, COUNT(*) as cnt
            FROM requirement_atoms ra
            WHERE ra.tenant_id = :tenant_id
              AND ra.document_id = ANY(:doc_ids)
              AND ra.regulatory_tags IS NOT NULL
              AND array_length(ra.regulatory_tags, 1) > 0
            GROUP BY ra.regulatory_tags
            """,
            {"tenant_id": tenant_id, "doc_ids": doc_ids}
        ).fetchall()
        for row in reg_rows:
            for tag in (row[0] or []):
                regulatory_risk[tag] = regulatory_risk.get(tag, 0) + row[1]
    except Exception:
        pass

    auto_testable_count = db.query(func.count(RequirementAtom.id)).filter(
        RequirementAtom.tenant_id == tenant_id,
        RequirementAtom.document_id.in_(doc_ids),
        RequirementAtom.testability.in_(["static", "runtime"]),
    ).scalar() or 0

    tenant_obj = db.query(Tenant).filter_by(id=tenant_id).first()
    ts = (tenant_obj.settings if tenant_obj and hasattr(tenant_obj, "settings") and tenant_obj.settings else {})
    baseline_hours = float(ts.get("qa_baseline_hours_per_atom", 0.5))
    qa_time_saved = round(auto_testable_count * baseline_hours, 1)

    total_atoms = sum(atom_count_by_doc.values())
    weighted_sum = sum(
        (score_by_doc[did].score_percentage if did in score_by_doc else 100.0) * atom_count_by_doc[did]
        for did in doc_ids
    )
    overall_compliance = round(weighted_sum / total_atoms, 1) if total_atoms > 0 else 100.0

    projects = []
    for doc_id in doc_ids:
        snap = score_by_doc.get(doc_id)
        doc = doc_meta.get(doc_id)
        projects.append({
            "document_id": doc_id,
            "title": doc.filename if doc else f"Document {doc_id}",
            "atom_count": atom_count_by_doc[doc_id],
            "compliance_score": snap.score_percentage if snap else None,
            "open_mismatches": snap.open_mismatches if snap else 0,
            "critical_mismatches": snap.critical_mismatches if snap else 0,
            "last_snapshot_date": snap.snapshot_date.isoformat() if snap else None,
        })
    projects.sort(key=lambda p: p["compliance_score"] if p["compliance_score"] is not None else 100.0)

    return {
        "tenant_id": tenant_id,
        "total_documents": len(doc_ids),
        "total_atoms": total_atoms,
        "overall_compliance_pct": overall_compliance,
        "total_open_mismatches": total_open_mismatches,
        "mismatch_breakdown": mismatch_breakdown,
        "regulatory_risk": regulatory_risk,
        "qa_time_saved_hours": qa_time_saved,
        "auto_testable_atoms": auto_testable_count,
        "qa_baseline_hours_per_atom": baseline_hours,
        "projects": projects,
        "generated_at": date.today().isoformat(),
    }
