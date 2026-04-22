"""Pydantic schemas for wallet transactions — Phase 9."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class WalletTransactionResponse(BaseModel):
    id: int
    tenant_id: int
    txn_type: str
    amount_inr: float
    balance_after_inr: float
    usage_log_id: Optional[int] = None
    razorpay_payment_id: Optional[str] = None
    description: Optional[str] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WalletBalanceResponse(BaseModel):
    tenant_id: int
    balance_inr: float = Field(..., description="Paid credits remaining")
    free_credit_inr: float = Field(..., description="Signup/promo free credits remaining")
    total_available_inr: float = Field(..., description="Total spendable balance")
    low_balance: bool = Field(..., description="True when total < threshold")
    preferred_model: Optional[str] = None


class TopUpRequest(BaseModel):
    amount_inr: float = Field(..., gt=0, description="Amount to add in INR")
    razorpay_payment_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None


class SetPreferredModelRequest(BaseModel):
    model_id: str = Field(..., description="Model ID to set as tenant default")
