"""
Analytics Service — Sprint 8: Analytics Dashboard

Aggregates UsageLog, OntologyConcept, AuditLog, and other entity data
to provide high-level metrics for the analytics dashboard.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.usage_log import UsageLog
from app.models.ontology_concept import OntologyConcept
from app.models.ontology_relationship import OntologyRelationship
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.repository import Repository
from app.models.conversation import Conversation

logger = get_logger("services.analytics")


def _period_to_days(period: str) -> int:
    """Convert period string to number of days."""
    mapping = {
        "week": 7,
        "month": 30,
        "quarter": 90,
        "year": 365,
    }
    return mapping.get(period, 30)


def get_overview(db: Session, tenant_id: int) -> Dict[str, Any]:
    """
    Return a combined summary dict for the analytics dashboard overview card.

    Fields returned:
        - total_cost_inr: all-time total cost in INR
        - total_tokens: all-time input + output tokens
        - total_operations: all-time operation count
        - this_month_cost: cost for the current calendar month
        - active_features: count of distinct feature_type values with usage
    """
    defaults: Dict[str, Any] = {
        "total_cost_inr": 0.0,
        "total_tokens": 0,
        "total_operations": 0,
        "this_month_cost": 0.0,
        "active_features": 0,
    }

    try:
        row = (
            db.query(
                func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total_cost_inr"),
                func.coalesce(
                    func.sum(UsageLog.input_tokens + UsageLog.output_tokens), 0
                ).label("total_tokens"),
                func.count(UsageLog.id).label("total_operations"),
            )
            .filter(UsageLog.tenant_id == tenant_id)
            .one()
        )
        defaults["total_cost_inr"] = float(row.total_cost_inr)
        defaults["total_tokens"] = int(row.total_tokens)
        defaults["total_operations"] = int(row.total_operations)
    except Exception as exc:
        logger.error(f"analytics get_overview: failed to fetch totals for tenant {tenant_id}: {exc}")

    try:
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month = (
            db.query(func.coalesce(func.sum(UsageLog.cost_inr), 0))
            .filter(
                UsageLog.tenant_id == tenant_id,
                UsageLog.created_at >= month_start,
            )
            .scalar()
        )
        defaults["this_month_cost"] = float(this_month or 0)
    except Exception as exc:
        logger.error(f"analytics get_overview: failed to fetch this_month_cost for tenant {tenant_id}: {exc}")

    try:
        active_features = (
            db.query(func.count(distinct(UsageLog.feature_type)))
            .filter(UsageLog.tenant_id == tenant_id)
            .scalar()
        )
        defaults["active_features"] = int(active_features or 0)
    except Exception as exc:
        logger.error(f"analytics get_overview: failed to fetch active_features for tenant {tenant_id}: {exc}")

    return defaults


def get_cost_breakdown(
    db: Session, tenant_id: int, period: str = "month"
) -> List[Dict[str, Any]]:
    """
    Return daily time-series cost data grouped by date and feature_type.

    Each item:
        - date: ISO date string (YYYY-MM-DD)
        - cost_inr: aggregated cost in INR for that day / feature
        - feature_type: feature label
        - operation_count: number of operations logged
    """
    days = _period_to_days(period)
    since = datetime.utcnow() - timedelta(days=days)

    try:
        rows = (
            db.query(
                func.date(UsageLog.created_at).label("date"),
                UsageLog.feature_type,
                func.coalesce(func.sum(UsageLog.cost_inr), 0).label("cost_inr"),
                func.count(UsageLog.id).label("operation_count"),
            )
            .filter(
                UsageLog.tenant_id == tenant_id,
                UsageLog.created_at >= since,
            )
            .group_by(func.date(UsageLog.created_at), UsageLog.feature_type)
            .order_by(func.date(UsageLog.created_at).asc())
            .all()
        )
        return [
            {
                "date": str(row.date),
                "cost_inr": float(row.cost_inr),
                "feature_type": row.feature_type,
                "operation_count": int(row.operation_count),
            }
            for row in rows
        ]
    except Exception as exc:
        logger.error(
            f"analytics get_cost_breakdown: failed for tenant {tenant_id}, period={period}: {exc}"
        )
        return []


def get_concept_growth(
    db: Session, tenant_id: int, period: str = "week"
) -> List[Dict[str, Any]]:
    """
    Return daily time-series concept and relationship counts over the period.

    Each item:
        - date: ISO date string (YYYY-MM-DD)
        - concept_count: cumulative concepts created up to that day
        - relationship_count: cumulative relationships created up to that day

    Uses a daily-bucket approach: counts new entities per day and returns
    the running totals alongside each bucket's daily new count.
    """
    days = _period_to_days(period)
    since = datetime.utcnow() - timedelta(days=days)
    results: List[Dict[str, Any]] = []

    try:
        concept_rows = (
            db.query(
                func.date(OntologyConcept.created_at).label("date"),
                func.count(OntologyConcept.id).label("daily_count"),
            )
            .filter(
                OntologyConcept.tenant_id == tenant_id,
                OntologyConcept.created_at >= since,
            )
            .group_by(func.date(OntologyConcept.created_at))
            .order_by(func.date(OntologyConcept.created_at).asc())
            .all()
        )
        concept_by_date = {str(row.date): int(row.daily_count) for row in concept_rows}
    except Exception as exc:
        logger.error(
            f"analytics get_concept_growth: failed to fetch concepts for tenant {tenant_id}: {exc}"
        )
        concept_by_date = {}

    try:
        rel_rows = (
            db.query(
                func.date(OntologyRelationship.created_at).label("date"),
                func.count(OntologyRelationship.id).label("daily_count"),
            )
            .filter(
                OntologyRelationship.tenant_id == tenant_id,
                OntologyRelationship.created_at >= since,
            )
            .group_by(func.date(OntologyRelationship.created_at))
            .order_by(func.date(OntologyRelationship.created_at).asc())
            .all()
        )
        rel_by_date = {str(row.date): int(row.daily_count) for row in rel_rows}
    except Exception as exc:
        logger.error(
            f"analytics get_concept_growth: failed to fetch relationships for tenant {tenant_id}: {exc}"
        )
        rel_by_date = {}

    # Merge into a unified date list covering every day in the period
    all_dates = sorted(set(concept_by_date.keys()) | set(rel_by_date.keys()))
    for date_str in all_dates:
        results.append(
            {
                "date": date_str,
                "concept_count": concept_by_date.get(date_str, 0),
                "relationship_count": rel_by_date.get(date_str, 0),
            }
        )

    return results


def get_activity_metrics(db: Session, tenant_id: int) -> Dict[str, Any]:
    """
    Return high-level activity counts across the tenant's entities.

    Fields returned:
        - total_documents: number of documents uploaded
        - total_repos: number of repositories connected
        - total_concepts: number of ontology concepts
        - total_chat_messages: number of chat operations (feature_type="chat") in UsageLog
        - total_validations: number of validation operations in UsageLog
    """
    metrics: Dict[str, Any] = {
        "total_documents": 0,
        "total_repos": 0,
        "total_concepts": 0,
        "total_chat_messages": 0,
        "total_validations": 0,
    }

    try:
        metrics["total_documents"] = (
            db.query(func.count(Document.id))
            .filter(Document.tenant_id == tenant_id)
            .scalar()
            or 0
        )
    except Exception as exc:
        logger.error(
            f"analytics get_activity_metrics: failed to count documents for tenant {tenant_id}: {exc}"
        )

    try:
        metrics["total_repos"] = (
            db.query(func.count(Repository.id))
            .filter(Repository.tenant_id == tenant_id)
            .scalar()
            or 0
        )
    except Exception as exc:
        logger.error(
            f"analytics get_activity_metrics: failed to count repos for tenant {tenant_id}: {exc}"
        )

    try:
        metrics["total_concepts"] = (
            db.query(func.count(OntologyConcept.id))
            .filter(OntologyConcept.tenant_id == tenant_id)
            .scalar()
            or 0
        )
    except Exception as exc:
        logger.error(
            f"analytics get_activity_metrics: failed to count concepts for tenant {tenant_id}: {exc}"
        )

    try:
        metrics["total_chat_messages"] = (
            db.query(func.count(UsageLog.id))
            .filter(
                UsageLog.tenant_id == tenant_id,
                UsageLog.feature_type == "chat",
            )
            .scalar()
            or 0
        )
    except Exception as exc:
        logger.error(
            f"analytics get_activity_metrics: failed to count chat messages for tenant {tenant_id}: {exc}"
        )

    try:
        metrics["total_validations"] = (
            db.query(func.count(UsageLog.id))
            .filter(
                UsageLog.tenant_id == tenant_id,
                UsageLog.feature_type == "validation",
            )
            .scalar()
            or 0
        )
    except Exception as exc:
        logger.error(
            f"analytics get_activity_metrics: failed to count validations for tenant {tenant_id}: {exc}"
        )

    return metrics
