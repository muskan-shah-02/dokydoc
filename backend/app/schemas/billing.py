"""
Pydantic schemas for billing and cost tracking.
Sprint 1: BE-COST-03 (Billing API)
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================================
# Response Schemas
# ============================================================================

class DocumentCostResponse(BaseModel):
    """Response schema for document cost information."""
    document_id: int
    filename: str
    ai_cost_inr: float = Field(..., description="Total AI cost in INR")
    token_count_input: int = Field(..., description="Total input tokens")
    token_count_output: int = Field(..., description="Total output tokens")
    cost_breakdown: Optional[dict] = Field(None, description="Cost breakdown by analysis pass")

    class Config:
        from_attributes = True


class TenantBillingResponse(BaseModel):
    """Response schema for tenant billing information."""
    tenant_id: int
    billing_type: str = Field(..., description="Billing type: prepaid or postpaid")
    balance_inr: float = Field(..., description="Current balance (prepaid only)")
    low_balance_threshold: float = Field(..., description="Low balance alert threshold")
    current_month_cost: float = Field(..., description="Cost for current month")
    last_30_days_cost: float = Field(..., description="Cost for last 30 days")
    monthly_limit_inr: Optional[float] = Field(None, description="Monthly spending limit")
    created_at: datetime
    updated_at: datetime
    last_billing_reset: Optional[datetime] = Field(None, description="Last billing cycle reset")

    class Config:
        from_attributes = True


class CurrentCostSummary(BaseModel):
    """Summary of current user/tenant costs."""
    tenant_id: int
    billing_type: str
    current_month_cost: float = Field(..., description="Cost for current month (INR)")
    last_30_days_cost: float = Field(..., description="Cost for last 30 days (INR)")
    balance_inr: Optional[float] = Field(None, description="Remaining balance (prepaid only)")
    monthly_limit_inr: Optional[float] = Field(None, description="Monthly spending limit")
    limit_remaining: Optional[float] = Field(None, description="Remaining budget before limit")
    low_balance_alert: bool = Field(False, description="True if balance is below threshold")

    class Config:
        from_attributes = True


# ============================================================================
# Request Schemas
# ============================================================================

class TopUpRequest(BaseModel):
    """Request schema for adding balance to prepaid account."""
    amount_inr: float = Field(..., gt=0, description="Amount to add (must be positive)")


class UpdateBillingSettingsRequest(BaseModel):
    """Request schema for updating billing settings."""
    billing_type: Optional[str] = Field(None, description="Change billing type: prepaid or postpaid")
    monthly_limit_inr: Optional[float] = Field(None, ge=0, description="Set monthly spending limit")
    low_balance_threshold: Optional[float] = Field(None, ge=0, description="Set low balance threshold")
