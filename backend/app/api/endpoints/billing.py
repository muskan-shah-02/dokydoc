"""
Billing and cost tracking API endpoints.
Sprint 1: BE-COST-03 (Billing API)
"""
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps
from app.core.logging import LoggerMixin, get_logger
from app.models.user import User
from app.models.document import Document
from app.middleware.rate_limiter import limiter, RateLimits

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
