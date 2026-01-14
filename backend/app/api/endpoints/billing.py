"""
Billing and cost tracking API endpoints.
Sprint 1: BE-COST-03 (Billing API)
"""
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps
from app.core.logging import LoggerMixin, get_logger
from app.models.user import User
from app.models.document import Document

logger = get_logger("api.billing")


class BillingEndpoints(LoggerMixin):
    """Billing endpoints with enhanced logging and error handling."""

    def __init__(self):
        super().__init__()


# Create instance for use in endpoints
billing_endpoints = BillingEndpoints()

router = APIRouter()


@router.get("/current", response_model=schemas.billing.CurrentCostSummary)
def get_current_costs(
    *,
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
    """
    logger.info(f"Fetching billing summary for user {current_user.email}, tenant {current_user.tenant_id}")

    # Get or create billing record for this tenant
    billing = crud.tenant_billing.get_or_create(db, tenant_id=current_user.tenant_id)

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
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    document_id: int
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
    """
    logger.info(f"Fetching cost for document {document_id}, user {current_user.email}")

    # Get document with tenant filtering
    document = crud.document.get(db, id=document_id, tenant_id=current_user.tenant_id)

    if not document:
        logger.warning(f"Document {document_id} not found or access denied for tenant {current_user.tenant_id}")
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    # Verify ownership
    if document.owner_id != current_user.id:
        logger.warning(f"User {current_user.email} attempted to access document {document_id} owned by user {document.owner_id}")
        raise HTTPException(
            status_code=403,
            detail="Access denied"
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
    """
    logger.info(f"Processing top-up request for user {current_user.email}, amount={request.amount_inr} INR")

    # Get billing record
    billing = crud.tenant_billing.get_or_create(db, tenant_id=current_user.tenant_id)

    # Verify this is a prepaid account
    if billing.billing_type != "prepaid":
        logger.warning(f"Top-up attempted on postpaid account for tenant {current_user.tenant_id}")
        raise HTTPException(
            status_code=400,
            detail="Top-up is only available for prepaid accounts"
        )

    # Add balance
    updated_billing = crud.tenant_billing.add_balance(
        db,
        tenant_id=current_user.tenant_id,
        amount_inr=request.amount_inr
    )

    logger.info(f"Balance added successfully: new balance={updated_billing.balance_inr} INR")
    return updated_billing


@router.get("/settings", response_model=schemas.billing.TenantBillingResponse)
def get_billing_settings(
    *,
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
    """
    logger.info(f"Fetching billing settings for user {current_user.email}, tenant {current_user.tenant_id}")

    billing = crud.tenant_billing.get_or_create(db, tenant_id=current_user.tenant_id)

    logger.info(f"Billing settings retrieved for tenant {billing.tenant_id}")
    return billing


@router.put("/settings", response_model=schemas.billing.TenantBillingResponse)
def update_billing_settings(
    *,
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
    """
    logger.info(f"Updating billing settings for user {current_user.email}, tenant {current_user.tenant_id}")

    updated_billing = crud.tenant_billing.update_settings(
        db,
        tenant_id=current_user.tenant_id,
        billing_type=request.billing_type,
        monthly_limit_inr=request.monthly_limit_inr,
        low_balance_threshold=request.low_balance_threshold
    )

    logger.info(f"Billing settings updated successfully for tenant {updated_billing.tenant_id}")
    return updated_billing
