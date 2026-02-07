"""
Billing and cost tracking API endpoints.
Sprint 1: BE-COST-03 (Billing API)
Sprint 2: Billing Analytics Dashboard with full transparency
"""
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Request, Response, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps
from app.core.logging import LoggerMixin, get_logger
from app.models.user import User
from app.models.document import Document
from app.middleware.rate_limiter import limiter, RateLimits
from app.schemas.usage_log import (
    TimeRangeEnum,
    BillingAnalyticsResponse,
    FeatureUsageSummary,
    OperationUsageSummary,
    TimeSeriesDataPoint,
    DocumentUsageSummary,
    TokenSummary,
    WeeklyUsageSummary,
    UsageLogResponse,
    UserUsageSummary,
    UserBillingAnalyticsResponse,
    AllUsersAnalyticsResponse,
)

logger = get_logger("api.billing")


class BillingEndpoints(LoggerMixin):
    """Billing endpoints with enhanced logging and error handling."""

    def __init__(self):
        super().__init__()


# Create instance for use in endpoints
billing_endpoints = BillingEndpoints()

router = APIRouter()


@router.get("/current", response_model=schemas.billing.CurrentCostSummary)
@limiter.limit(RateLimits.BILLING)  # API-01 FIX: Rate limit billing queries (30/min, 200/hour)
def get_current_costs(
    request: Request,  # API-01 FIX: Required for rate limiter
    response: Response,  # Required for rate limiter to inject headers
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get current cost summary for the authenticated user's tenant.

    Returns:
        - Current month cost
        - Last 30 days cost
        - Balance (for prepaid)
        - Limit status
        - Low balance alert

    Rate Limit: 30 requests/minute, 200/hour per user

    SPRINT 2: Uses tenant_id dependency injection for consistency.
    """
    logger.info(f"Fetching billing summary for user {current_user.email}, tenant {tenant_id}")

    # Get or create billing record for this tenant
    billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)

    # Calculate remaining budget
    limit_remaining = None
    if billing.monthly_limit_inr is not None:
        limit_remaining = billing.monthly_limit_inr - billing.current_month_cost

    # Check for low balance alert (prepaid only)
    low_balance_alert = False
    if billing.billing_type == "prepaid":
        low_balance_alert = billing.balance_inr < billing.low_balance_threshold

    response = schemas.billing.CurrentCostSummary(
        tenant_id=billing.tenant_id,
        billing_type=billing.billing_type,
        current_month_cost=float(billing.current_month_cost),
        last_30_days_cost=float(billing.last_30_days_cost),
        balance_inr=float(billing.balance_inr) if billing.billing_type == "prepaid" else None,
        monthly_limit_inr=float(billing.monthly_limit_inr) if billing.monthly_limit_inr else None,
        limit_remaining=float(limit_remaining) if limit_remaining is not None else None,
        low_balance_alert=low_balance_alert
    )

    logger.info(f"Billing summary retrieved: {billing.billing_type}, current_month={response.current_month_cost} INR")
    return response


@router.get("/documents/{document_id}/cost", response_model=schemas.billing.DocumentCostResponse)
def get_document_cost(
    *,
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get cost breakdown for a specific document.

    Args:
        document_id: ID of the document

    Returns:
        - Document ID and filename
        - Total AI cost in INR
        - Token counts (input/output)
        - Cost breakdown by analysis pass

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when document not in tenant to avoid leaking existence.
    """
    logger.info(f"Fetching cost for document {document_id}, user {current_user.email} (tenant_id={tenant_id})")

    # Get document with tenant filtering
    document = crud.document.get(db, id=document_id, tenant_id=tenant_id)

    if not document:
        logger.warning(f"Document {document_id} not found in tenant {tenant_id}")
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    response = schemas.billing.DocumentCostResponse(
        document_id=document.id,
        filename=document.filename,
        ai_cost_inr=float(document.ai_cost_inr),
        token_count_input=document.token_count_input,
        token_count_output=document.token_count_output,
        cost_breakdown=document.cost_breakdown
    )

    logger.info(f"Document cost retrieved: {document.filename}, cost={response.ai_cost_inr} INR")
    return response


@router.post("/topup", response_model=schemas.billing.TenantBillingResponse)
def add_balance(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    request: schemas.billing.TopUpRequest
):
    """
    Add balance to prepaid account.

    This endpoint is only available for prepaid billing accounts.

    Args:
        request: TopUpRequest with amount_inr

    Returns:
        Updated billing information

    SPRINT 2: Uses tenant_id dependency injection for consistency.
    """
    logger.info(f"Processing top-up request for user {current_user.email} (tenant_id={tenant_id}), amount={request.amount_inr} INR")

    # Get billing record
    billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)

    # Verify this is a prepaid account
    if billing.billing_type != "prepaid":
        logger.warning(f"Top-up attempted on postpaid account for tenant {tenant_id}")
        raise HTTPException(
            status_code=400,
            detail="Top-up is only available for prepaid accounts"
        )

    # Add balance
    updated_billing = crud.tenant_billing.add_balance(
        db,
        tenant_id=tenant_id,
        amount_inr=request.amount_inr
    )

    logger.info(f"Balance added successfully: new balance={updated_billing.balance_inr} INR")
    return updated_billing


@router.get("/settings", response_model=schemas.billing.TenantBillingResponse)
def get_billing_settings(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get complete billing settings for the authenticated user's tenant.

    Returns:
        - Billing type (prepaid/postpaid)
        - Balance and limits
        - Cost history
        - All billing settings

    SPRINT 2: Uses tenant_id dependency injection for consistency.
    """
    logger.info(f"Fetching billing settings for user {current_user.email}, tenant {tenant_id}")

    billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)

    logger.info(f"Billing settings retrieved for tenant {billing.tenant_id}")
    return billing


@router.put("/settings", response_model=schemas.billing.TenantBillingResponse)
def update_billing_settings(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    request: schemas.billing.UpdateBillingSettingsRequest
):
    """
    Update billing settings for the authenticated user's tenant.

    Allowed updates:
        - Change billing type (prepaid <-> postpaid)
        - Set monthly spending limit
        - Set low balance alert threshold

    Args:
        request: UpdateBillingSettingsRequest with optional fields

    Returns:
        Updated billing information

    SPRINT 2: Uses tenant_id dependency injection for consistency.
    """
    logger.info(f"Updating billing settings for user {current_user.email}, tenant {tenant_id}")

    updated_billing = crud.tenant_billing.update_settings(
        db,
        tenant_id=tenant_id,
        billing_type=request.billing_type,
        monthly_limit_inr=request.monthly_limit_inr,
        low_balance_threshold=request.low_balance_threshold
    )

    logger.info(f"Billing settings updated successfully for tenant {updated_billing.tenant_id}")
    return updated_billing


@router.get("/usage")
def get_billing_usage(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get current billing usage for tenant.

    SPRINT 2 Phase 4: Shows current usage, balance, limits, and alerts.

    Returns:
        {
            "tenant_id": int,
            "billing_type": "prepaid" | "postpaid",
            "balance_inr": float (prepaid only),
            "current_month_cost": float,
            "last_30_days_cost": float,
            "monthly_limit_inr": float (if set),
            "limit_remaining_inr": float (if limit set),
            "limit_usage_percentage": float (if limit set),
            "low_balance_alert": bool
        }
    """
    logger.info(f"Fetching billing usage for tenant {tenant_id}, user {current_user.email}")

    from app.services.billing_enforcement_service import billing_enforcement_service

    usage = billing_enforcement_service.get_current_usage(db=db, tenant_id=tenant_id)

    logger.info(
        f"Billing usage retrieved for tenant {tenant_id}: "
        f"type={usage['billing_type']}, current_month=₹{usage['current_month_cost']}"
    )

    return usage


@router.get("/pricing")
def get_pricing_info():
    """
    Get complete pricing information for transparency.

    SPRINT 2: Returns all pricing factors, formulas, and current rates
    for display on billing dashboards.

    No authentication required - pricing is public information.

    Returns:
        {
            "model": "gemini-2.5-flash",
            "rates_usd": {
                "input_per_1m_tokens": 0.30,
                "output_per_1m_tokens": 2.50,
                ...
            },
            "rates_inr": {...},
            "exchange_rate": {...},
            "formula": {...},
            "cost_factors": [...]
        }
    """
    from app.services.cost_service import cost_service

    pricing_info = cost_service.get_pricing_info()

    logger.info(
        f"Pricing info requested: model={pricing_info['model']}, "
        f"input=${pricing_info['rates_usd']['input_per_1m_tokens']}/1M, "
        f"output=${pricing_info['rates_usd']['output_per_1m_tokens']}/1M"
    )

    return pricing_info


@router.get("/estimate")
def estimate_document_cost(
    doc_size_kb: float = 10.0,
    passes: int = 3,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Estimate cost for processing a document.

    Args:
        doc_size_kb: Document size in KB (default: 10)
        passes: Number of analysis passes (default: 3)

    Returns:
        Cost estimate with detailed breakdown
    """
    from app.services.cost_service import cost_service

    estimate = cost_service.estimate_document_cost(doc_size_kb, passes)

    logger.info(
        f"Cost estimate requested: {doc_size_kb}KB doc, {passes} passes = ₹{estimate['cost_inr']:.2f}"
    )

    return estimate


# =============================================================================
# BILLING ANALYTICS ENDPOINTS
# Sprint 2: Full transparency dashboard with filters
# =============================================================================

@router.get("/analytics", response_model=BillingAnalyticsResponse)
def get_billing_analytics(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    time_range: TimeRangeEnum = Query(default=TimeRangeEnum.THIS_MONTH, description="Time range filter"),
    start_date: Optional[date] = Query(default=None, description="Custom start date (for CUSTOM range)"),
    end_date: Optional[date] = Query(default=None, description="Custom end date (for CUSTOM range)"),
    feature_type: Optional[str] = Query(default=None, description="Filter by feature type"),
):
    """
    Get comprehensive billing analytics with filters.

    SPRINT 2: Full transparency dashboard for AI usage monitoring.

    Provides:
    - Total costs and API calls
    - Token usage summary (input/output/cached)
    - Breakdown by feature (document_analysis, code_analysis, validation, etc.)
    - Breakdown by operation (pass_1, pass_2, pass_3, code_review, etc.)
    - Daily usage time series for charts
    - Top documents by cost

    Query Parameters:
    - time_range: Predefined time range (today, this_week, this_month, last_30_days, etc.)
    - start_date/end_date: For custom date range
    - feature_type: Filter by specific feature

    Returns:
        BillingAnalyticsResponse with complete analytics data
    """
    logger.info(
        f"Fetching billing analytics for tenant {tenant_id}, "
        f"range={time_range.value}, feature={feature_type}"
    )

    # Get date range
    start, end = crud.usage_log.get_date_range(time_range, start_date, end_date)

    # Get total summary
    total_summary = crud.usage_log.get_total_summary(
        db, tenant_id=tenant_id, start=start, end=end, feature_type=feature_type
    )

    # Get token summary
    token_summary = crud.usage_log.get_token_summary(
        db, tenant_id=tenant_id, start=start, end=end
    )

    # Get feature breakdown
    by_feature = crud.usage_log.get_by_feature(
        db, tenant_id=tenant_id, start=start, end=end
    )

    # Get operation breakdown
    by_operation = crud.usage_log.get_by_operation(
        db, tenant_id=tenant_id, start=start, end=end, limit=10
    )

    # Get daily usage for charts
    daily_usage = crud.usage_log.get_daily_usage(
        db, tenant_id=tenant_id, start=start, end=end, feature_type=feature_type
    )

    # Get top documents by cost
    top_documents = crud.usage_log.get_top_documents(
        db, tenant_id=tenant_id, start=start, end=end, limit=10
    )

    response = BillingAnalyticsResponse(
        time_range=time_range.value,
        start_date=start,
        end_date=end,
        total_cost_inr=total_summary["total_cost_inr"],
        total_cost_usd=total_summary["total_cost_usd"],
        total_api_calls=total_summary["total_calls"],
        tokens=token_summary,
        by_feature=by_feature,
        by_operation=by_operation,
        daily_usage=daily_usage,
        top_documents=top_documents,
    )

    logger.info(
        f"Analytics retrieved: {total_summary['total_calls']} calls, "
        f"₹{total_summary['total_cost_inr']:.2f} total"
    )

    return response


@router.get("/analytics/by-feature", response_model=List[FeatureUsageSummary])
def get_usage_by_feature(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    time_range: TimeRangeEnum = Query(default=TimeRangeEnum.THIS_MONTH),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
):
    """
    Get usage breakdown by feature type.

    Returns cost and token usage for each feature:
    - document_analysis
    - code_analysis
    - validation
    - chat
    - summary
    - other
    """
    start, end = crud.usage_log.get_date_range(time_range, start_date, end_date)

    return crud.usage_log.get_by_feature(
        db, tenant_id=tenant_id, start=start, end=end
    )


@router.get("/analytics/by-operation", response_model=List[OperationUsageSummary])
def get_usage_by_operation(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    time_range: TimeRangeEnum = Query(default=TimeRangeEnum.THIS_MONTH),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    """
    Get usage breakdown by specific operation.

    Returns top operations by cost:
    - pass_1_composition, pass_2_segmenting, pass_3_extraction
    - code_review, code_explanation
    - requirement_validation, etc.
    """
    start, end = crud.usage_log.get_date_range(time_range, start_date, end_date)

    return crud.usage_log.get_by_operation(
        db, tenant_id=tenant_id, start=start, end=end, limit=limit
    )


@router.get("/analytics/daily", response_model=List[TimeSeriesDataPoint])
def get_daily_usage(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    time_range: TimeRangeEnum = Query(default=TimeRangeEnum.LAST_30_DAYS),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    feature_type: Optional[str] = Query(default=None),
):
    """
    Get daily usage time series for charts.

    Returns data points with:
    - date
    - total_cost_inr
    - total_tokens
    - call_count
    """
    start, end = crud.usage_log.get_date_range(time_range, start_date, end_date)

    return crud.usage_log.get_daily_usage(
        db, tenant_id=tenant_id, start=start, end=end, feature_type=feature_type
    )


@router.get("/analytics/weekly", response_model=List[WeeklyUsageSummary])
def get_weekly_usage(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    weeks: int = Query(default=4, ge=1, le=12),
):
    """
    Get weekly usage summary for dashboard cards.

    Returns:
    - Weekly totals (cost, tokens, calls)
    - Week-over-week change percentage
    """
    return crud.usage_log.get_weekly_summary(
        db, tenant_id=tenant_id, weeks=weeks
    )


@router.get("/analytics/tokens", response_model=TokenSummary)
def get_token_summary(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    time_range: TimeRangeEnum = Query(default=TimeRangeEnum.THIS_MONTH),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
):
    """
    Get aggregate token usage summary.

    Returns:
    - Total input/output/cached tokens
    - Average per call
    - Input/output ratio
    """
    start, end = crud.usage_log.get_date_range(time_range, start_date, end_date)

    return crud.usage_log.get_token_summary(
        db, tenant_id=tenant_id, start=start, end=end
    )


@router.get("/analytics/documents", response_model=List[DocumentUsageSummary])
def get_document_usage(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    time_range: TimeRangeEnum = Query(default=TimeRangeEnum.THIS_MONTH),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    """
    Get usage breakdown by document.

    Returns top documents by cost with:
    - Document ID and filename
    - Total calls, tokens, cost
    - Last used timestamp
    """
    start, end = crud.usage_log.get_date_range(time_range, start_date, end_date)

    return crud.usage_log.get_top_documents(
        db, tenant_id=tenant_id, start=start, end=end, limit=limit
    )


@router.get("/analytics/logs", response_model=List[UsageLogResponse])
def get_usage_logs(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    time_range: TimeRangeEnum = Query(default=TimeRangeEnum.THIS_MONTH),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    feature_type: Optional[str] = Query(default=None),
    document_id: Optional[int] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    Get detailed usage logs with pagination.

    Returns individual API call records for detailed analysis.
    Useful for auditing and debugging.
    """
    logs = crud.usage_log.get_by_tenant(
        db,
        tenant_id=tenant_id,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        feature_type=feature_type,
        document_id=document_id,
        limit=limit,
        offset=offset,
    )

    # Convert to response format with total_tokens calculated
    return [
        UsageLogResponse(
            id=log.id,
            tenant_id=log.tenant_id,
            user_id=log.user_id,
            document_id=log.document_id,
            feature_type=log.feature_type,
            operation=log.operation,
            model_used=log.model_used,
            input_tokens=log.input_tokens,
            output_tokens=log.output_tokens,
            cached_tokens=log.cached_tokens,
            total_tokens=log.input_tokens + log.output_tokens,
            cost_usd=float(log.cost_usd),
            cost_inr=float(log.cost_inr),
            processing_time_seconds=float(log.processing_time_seconds) if log.processing_time_seconds else None,
            extra_data=log.extra_data,
            created_at=log.created_at,
        )
        for log in logs
    ]


# =============================================================================
# USER-LEVEL ANALYTICS (For Admin/CXO Dashboard)
# Sprint 2: Billing transparency by user
# =============================================================================

@router.get("/analytics/users", response_model=AllUsersAnalyticsResponse)
def get_all_users_analytics(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    time_range: TimeRangeEnum = Query(default=TimeRangeEnum.THIS_MONTH),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
):
    """
    Get billing breakdown by user for Admin/CXO dashboard.

    SPRINT 2: Enables admins to see total AI cost by each team member.

    Returns:
    - Total tenant cost and calls for the period
    - Per-user breakdown with:
      - User email and name
      - Total calls, tokens, cost
      - Percentage of total tenant cost
      - Last activity timestamp

    Access: Requires admin/CXO role (TODO: add role check)
    """
    logger.info(
        f"Fetching all users analytics for tenant {tenant_id}, "
        f"range={time_range.value}, requested by {current_user.email}"
    )

    # Get date range
    start, end = crud.usage_log.get_date_range(time_range, start_date, end_date)

    # Get total summary for tenant
    total_summary = crud.usage_log.get_total_summary(
        db, tenant_id=tenant_id, start=start, end=end
    )

    # Get per-user breakdown
    users_data = crud.usage_log.get_all_users_summary(
        db, tenant_id=tenant_id, start=start, end=end
    )

    # Convert to response format
    users = [
        UserUsageSummary(
            user_id=u["user_id"],
            user_email=u["user_email"],
            user_name=u["user_name"],
            total_calls=u["total_calls"],
            total_input_tokens=u["total_input_tokens"],
            total_output_tokens=u["total_output_tokens"],
            total_tokens=u["total_tokens"],
            total_cost_usd=u["total_cost_usd"],
            total_cost_inr=u["total_cost_inr"],
            percentage_of_total=u["percentage_of_total"],
            last_activity=u["last_activity"],
        )
        for u in users_data
    ]

    response = AllUsersAnalyticsResponse(
        time_range=time_range.value,
        start_date=start,
        end_date=end,
        total_tenant_cost_inr=total_summary["total_cost_inr"],
        total_tenant_calls=total_summary["total_calls"],
        users=users,
    )

    logger.info(
        f"Users analytics retrieved: {len(users)} users, "
        f"₹{total_summary['total_cost_inr']:.2f} total"
    )

    return response


@router.get("/analytics/users/{user_id}", response_model=UserBillingAnalyticsResponse)
def get_user_analytics(
    *,
    user_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    time_range: TimeRangeEnum = Query(default=TimeRangeEnum.THIS_MONTH),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
):
    """
    Get detailed billing analytics for a specific user.

    SPRINT 2: Deep-dive into individual user's AI usage.

    Returns:
    - User info and total costs
    - Feature breakdown (document_analysis, code_analysis, etc.)
    - Daily usage time series
    - Top documents by cost

    Access: Requires admin/CXO role or user viewing own data (TODO: add role check)
    """
    logger.info(
        f"Fetching user {user_id} analytics for tenant {tenant_id}, "
        f"range={time_range.value}, requested by {current_user.email}"
    )

    # Get date range
    start, end = crud.usage_log.get_date_range(time_range, start_date, end_date)

    # Get user summary
    user_summary = crud.usage_log.get_user_summary(
        db, tenant_id=tenant_id, user_id=user_id, start=start, end=end
    )

    # Get feature breakdown for user
    by_feature = crud.usage_log.get_user_by_feature(
        db, tenant_id=tenant_id, user_id=user_id, start=start, end=end
    )

    # Get daily usage for user
    daily_usage = crud.usage_log.get_user_daily_usage(
        db, tenant_id=tenant_id, user_id=user_id, start=start, end=end
    )

    # Get top documents for user
    top_documents = crud.usage_log.get_user_documents(
        db, tenant_id=tenant_id, user_id=user_id, start=start, end=end, limit=10
    )

    response = UserBillingAnalyticsResponse(
        user_id=user_id,
        user_email=user_summary["user_email"],
        user_name=user_summary["user_name"],
        time_range=time_range.value,
        start_date=start,
        end_date=end,
        total_cost_inr=user_summary["total_cost_inr"],
        total_cost_usd=user_summary["total_cost_usd"],
        total_api_calls=user_summary["total_calls"],
        total_tokens=user_summary["total_tokens"],
        by_feature=by_feature,
        daily_usage=daily_usage,
        top_documents=top_documents,
    )

    logger.info(
        f"User {user_id} analytics retrieved: {user_summary['total_calls']} calls, "
        f"₹{user_summary['total_cost_inr']:.2f} total"
    )

    return response


@router.get("/analytics/users/{user_id}/by-feature", response_model=List[FeatureUsageSummary])
def get_user_feature_breakdown(
    *,
    user_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    time_range: TimeRangeEnum = Query(default=TimeRangeEnum.THIS_MONTH),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
):
    """
    Get feature breakdown for a specific user.

    Returns cost and usage by feature type for the specified user.
    """
    start, end = crud.usage_log.get_date_range(time_range, start_date, end_date)

    return crud.usage_log.get_user_by_feature(
        db, tenant_id=tenant_id, user_id=user_id, start=start, end=end
    )


@router.get("/analytics/users/{user_id}/daily", response_model=List[TimeSeriesDataPoint])
def get_user_daily_usage(
    *,
    user_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    time_range: TimeRangeEnum = Query(default=TimeRangeEnum.LAST_30_DAYS),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
):
    """
    Get daily usage time series for a specific user.

    Returns daily data points for charts and trend analysis.
    """
    start, end = crud.usage_log.get_date_range(time_range, start_date, end_date)

    return crud.usage_log.get_user_daily_usage(
        db, tenant_id=tenant_id, user_id=user_id, start=start, end=end
    )


@router.get("/analytics/users/{user_id}/documents", response_model=List[DocumentUsageSummary])
def get_user_document_usage(
    *,
    user_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    time_range: TimeRangeEnum = Query(default=TimeRangeEnum.THIS_MONTH),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    """
    Get top documents by cost for a specific user.

    Returns document-level usage breakdown for the specified user.
    """
    start, end = crud.usage_log.get_date_range(time_range, start_date, end_date)

    return crud.usage_log.get_user_documents(
        db, tenant_id=tenant_id, user_id=user_id, start=start, end=end, limit=limit
    )
