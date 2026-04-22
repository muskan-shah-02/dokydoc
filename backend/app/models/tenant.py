"""
Tenant model for multi-tenancy support.
Represents an organization/company using DokyDoc.
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.task import Task


class Tenant(Base):
    """
    Database model for tenants (organizations).

    Each tenant represents a separate organization with isolated data.
    Users, documents, and all other resources belong to a tenant.
    """
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Business Information
    name: Mapped[str] = mapped_column(String, nullable=False)
    subdomain: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    domain: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Custom domain

    # Subscription & Status
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)  # active, suspended, trial
    tier: Mapped[str] = mapped_column(String, default="free", nullable=False)  # free, professional, enterprise

    # Billing Configuration
    billing_type: Mapped[str] = mapped_column(String, default="prepaid", nullable=False)  # prepaid, postpaid

    # Limits & Quotas (enforced by tier)
    max_users: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_documents: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    max_monthly_cost_inr: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Settings (JSON field for flexible configuration)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False, server_default='{}')

    # Phase 9: Wallet / prepaid billing
    wallet_balance_inr: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0.0, server_default='0')
    wallet_free_credit_inr: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0.0, server_default='0')
    preferred_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    razorpay_customer_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # First admin user

    # Relationships (Sprint 2 Extended - Phase 10)
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="tenant", lazy="dynamic")
