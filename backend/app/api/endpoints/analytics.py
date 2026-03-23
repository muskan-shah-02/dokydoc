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
