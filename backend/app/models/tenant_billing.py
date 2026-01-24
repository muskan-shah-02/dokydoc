"""
Tenant billing model for tracking costs and balances per tenant.
Supports both prepaid and postpaid billing models.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class TenantBilling(Base):
    """
    Database model for per-tenant billing and cost tracking.

    Supports two billing models:
    1. Prepaid: Tenant has a balance, charged per usage
    2. Postpaid: Tenant billed monthly based on usage
    """
    __tablename__ = "tenant_billing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)

    # Billing type: "prepaid" or "postpaid"
    billing_type: Mapped[str] = mapped_column(String, default="postpaid", nullable=False)

    # --- Prepaid fields ---
    # Current balance in INR (for prepaid tenants)
    balance_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)

    # Alert threshold for low balance warning
    low_balance_threshold: Mapped[float] = mapped_column(Numeric(12, 2), default=100.0, nullable=False)

    # --- Postpaid fields ---
    # Total cost in current calendar month (resets on 1st of month)
    current_month_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)

    # Rolling 30-day cost (for dashboard display)
    last_30_days_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)

    # --- Limits & Controls ---
    # Optional monthly spending limit (null = unlimited)
    monthly_limit_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)

    # Timestamp fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Last billing cycle reset date (for postpaid)
    last_billing_reset: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
