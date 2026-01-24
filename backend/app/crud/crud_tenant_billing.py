"""
CRUD operations for TenantBilling model.
Sprint 1: BE-COST-03 (Billing API)
"""
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.crud.base import CRUDBase
from app.models.tenant_billing import TenantBilling


class CRUDTenantBilling(CRUDBase[TenantBilling, dict, dict]):
    """
    CRUD functions for TenantBilling model.
    """

    def get_by_tenant_id(self, db: Session, *, tenant_id: int) -> Optional[TenantBilling]:
        """
        Get billing record for a specific tenant.

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            TenantBilling record or None if not found
        """
        return db.query(self.model).filter(self.model.tenant_id == tenant_id).first()

    def get_or_create(self, db: Session, *, tenant_id: int) -> TenantBilling:
        """
        Get billing record for tenant, or create one if it doesn't exist.

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            TenantBilling record (existing or newly created)
        """
        billing = self.get_by_tenant_id(db, tenant_id=tenant_id)

        if not billing:
            # Create new billing record with default values
            billing = TenantBilling(
                tenant_id=tenant_id,
                billing_type="postpaid",
                balance_inr=0.0,
                low_balance_threshold=100.0,
                current_month_cost=0.0,
                last_30_days_cost=0.0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(billing)
            db.commit()
            db.refresh(billing)

        return billing

    def add_balance(self, db: Session, *, tenant_id: int, amount_inr: float) -> TenantBilling:
        """
        Add balance to a prepaid tenant account.

        Args:
            db: Database session
            tenant_id: Tenant ID
            amount_inr: Amount to add (positive value)

        Returns:
            Updated TenantBilling record
        """
        billing = self.get_or_create(db, tenant_id=tenant_id)

        billing.balance_inr += amount_inr
        billing.updated_at = datetime.now()

        db.add(billing)
        db.commit()
        db.refresh(billing)

        return billing

    def deduct_cost(
        self,
        db: Session,
        *,
        tenant_id: int,
        cost_inr: float
    ) -> TenantBilling:
        """
        Deduct cost from tenant billing (prepaid deducts from balance, postpaid adds to current cost).

        Args:
            db: Database session
            tenant_id: Tenant ID
            cost_inr: Cost to deduct/add

        Returns:
            Updated TenantBilling record
        """
        billing = self.get_or_create(db, tenant_id=tenant_id)

        if billing.billing_type == "prepaid":
            # Deduct from balance
            billing.balance_inr -= cost_inr
        else:
            # Add to current month cost
            billing.current_month_cost += cost_inr
            billing.last_30_days_cost += cost_inr

        billing.updated_at = datetime.now()

        db.add(billing)
        db.commit()
        db.refresh(billing)

        return billing

    def update_settings(
        self,
        db: Session,
        *,
        tenant_id: int,
        billing_type: Optional[str] = None,
        monthly_limit_inr: Optional[float] = None,
        low_balance_threshold: Optional[float] = None
    ) -> TenantBilling:
        """
        Update billing settings for a tenant.

        Args:
            db: Database session
            tenant_id: Tenant ID
            billing_type: Optional new billing type
            monthly_limit_inr: Optional monthly spending limit
            low_balance_threshold: Optional low balance alert threshold

        Returns:
            Updated TenantBilling record
        """
        billing = self.get_or_create(db, tenant_id=tenant_id)

        if billing_type is not None:
            billing.billing_type = billing_type

        if monthly_limit_inr is not None:
            billing.monthly_limit_inr = monthly_limit_inr

        if low_balance_threshold is not None:
            billing.low_balance_threshold = low_balance_threshold

        billing.updated_at = datetime.now()

        db.add(billing)
        db.commit()
        db.refresh(billing)

        return billing


# Create a single instance of the CRUDTenantBilling class that we can import elsewhere
tenant_billing = CRUDTenantBilling(TenantBilling)
