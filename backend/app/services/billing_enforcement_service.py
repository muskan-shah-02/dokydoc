"""
Billing Enforcement Service
Sprint 2 Phase 4: Simplified Billing Service

Handles billing enforcement, cost deduction, and balance checks.
Keeps it simple - no complex rolling windows or invoice PDFs.
"""
from typing import Optional, Dict
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.orm import Session

from app import crud
from app.core.logging import get_logger
from app.core.exceptions import DokyDocException

logger = get_logger("services.billing_enforcement")


class InsufficientBalanceException(DokyDocException):
    """Raised when tenant has insufficient balance for prepaid operations."""

    def __init__(self, tenant_id: int, required: float, available: float):
        self.tenant_id = tenant_id
        self.required = required
        self.available = available
        super().__init__(
            message=f"Insufficient balance. Required: ₹{required:.2f}, Available: ₹{available:.2f}",
            details={
                "tenant_id": tenant_id,
                "required_inr": required,
                "available_inr": available,
                "shortage_inr": required - available
            }
        )


class MonthlyLimitExceededException(DokyDocException):
    """Raised when tenant exceeds monthly spending limit."""

    def __init__(self, tenant_id: int, limit: float, current: float):
        self.tenant_id = tenant_id
        self.limit = limit
        self.current = current
        super().__init__(
            message=f"Monthly spending limit exceeded. Limit: ₹{limit:.2f}, Current: ₹{current:.2f}",
            details={
                "tenant_id": tenant_id,
                "monthly_limit_inr": limit,
                "current_month_cost": current,
                "overage_inr": current - limit
            }
        )


class BillingEnforcementService:
    """
    Simplified billing enforcement service.

    Features:
    - Pre-check balance before operations
    - Deduct costs after operations complete
    - Monthly limit enforcement
    - Low balance alerts
    - Simple monthly rollover (first of month)

    Non-features (keeping it simple):
    - No complex rolling 30-day windows
    - No invoice PDF generation
    - No payment gateway integration
    - No detailed audit logs
    """

    def __init__(self):
        self.logger = logger

    def check_can_afford_analysis(
        self,
        db: Session,
        *,
        tenant_id: int,
        estimated_cost_inr: float = 5.0  # Default estimate for analysis
    ) -> Dict:
        """
        Check if tenant can afford a document analysis operation.

        For prepaid: Checks balance
        For postpaid: Checks monthly limit

        Args:
            db: Database session
            tenant_id: Tenant ID
            estimated_cost_inr: Estimated cost for the operation (default 5 INR)

        Returns:
            Dictionary with check results:
            {
                "can_proceed": bool,
                "reason": str,
                "billing_type": str,
                "balance_inr": float (prepaid only),
                "current_month_cost": float,
                "monthly_limit_inr": float (if set)
            }

        Raises:
            InsufficientBalanceException: If prepaid and balance too low
            MonthlyLimitExceededException: If monthly limit would be exceeded
        """
        self.logger.info(f"Checking affordability for tenant {tenant_id}, estimated cost: ₹{estimated_cost_inr}")

        # Get billing record
        billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)

        # Perform monthly rollover if needed
        self._check_and_perform_rollover(db, billing)

        result = {
            "can_proceed": True,
            "reason": "OK",
            "billing_type": billing.billing_type,
            "current_month_cost": float(billing.current_month_cost),
            "monthly_limit_inr": float(billing.monthly_limit_inr) if billing.monthly_limit_inr else None
        }

        # Check based on billing type
        if billing.billing_type == "prepaid":
            # Prepaid: Check balance
            result["balance_inr"] = float(billing.balance_inr)

            if billing.balance_inr < estimated_cost_inr:
                self.logger.warning(
                    f"Insufficient balance for tenant {tenant_id}: "
                    f"balance=₹{billing.balance_inr}, required=₹{estimated_cost_inr}"
                )
                raise InsufficientBalanceException(
                    tenant_id=tenant_id,
                    required=estimated_cost_inr,
                    available=float(billing.balance_inr)
                )

            self.logger.info(f"Prepaid check passed: balance=₹{billing.balance_inr}")

        elif billing.billing_type == "postpaid":
            # Postpaid: Check monthly limit (if set)
            if billing.monthly_limit_inr is not None:
                projected_cost = billing.current_month_cost + estimated_cost_inr

                if projected_cost > billing.monthly_limit_inr:
                    self.logger.warning(
                        f"Monthly limit exceeded for tenant {tenant_id}: "
                        f"limit=₹{billing.monthly_limit_inr}, projected=₹{projected_cost}"
                    )
                    raise MonthlyLimitExceededException(
                        tenant_id=tenant_id,
                        limit=float(billing.monthly_limit_inr),
                        current=float(billing.current_month_cost)
                    )

            self.logger.info(f"Postpaid check passed: current_month=₹{billing.current_month_cost}")

        return result

    def deduct_cost(
        self,
        db: Session,
        *,
        tenant_id: int,
        cost_inr: float,
        description: str = "Document analysis"
    ) -> Dict:
        """
        Deduct cost from tenant after operation completes.

        For prepaid: Deducts from balance
        For postpaid: Adds to current month cost

        Args:
            db: Database session
            tenant_id: Tenant ID
            cost_inr: Actual cost to deduct
            description: Description of the charge

        Returns:
            Dictionary with updated billing info:
            {
                "success": bool,
                "billing_type": str,
                "cost_deducted_inr": float,
                "new_balance_inr": float (prepaid only),
                "new_current_month_cost": float,
                "low_balance_alert": bool
            }
        """
        self.logger.info(f"Deducting ₹{cost_inr} from tenant {tenant_id} for: {description}")

        # Get billing record
        billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)

        # Perform monthly rollover if needed
        self._check_and_perform_rollover(db, billing)

        result = {
            "success": True,
            "billing_type": billing.billing_type,
            "cost_deducted_inr": cost_inr,
            "new_current_month_cost": float(billing.current_month_cost) + cost_inr,
            "low_balance_alert": False
        }

        if billing.billing_type == "prepaid":
            # Prepaid: Deduct from balance
            new_balance = billing.balance_inr - Decimal(str(cost_inr))

            # Update balance and current month cost
            billing.balance_inr = new_balance
            billing.current_month_cost += Decimal(str(cost_inr))
            billing.last_30_days_cost += Decimal(str(cost_inr))

            db.add(billing)
            db.commit()
            db.refresh(billing)

            result["new_balance_inr"] = float(new_balance)

            # Check for low balance alert
            if new_balance < billing.low_balance_threshold:
                result["low_balance_alert"] = True
                self.logger.warning(
                    f"Low balance alert for tenant {tenant_id}: "
                    f"balance=₹{new_balance}, threshold=₹{billing.low_balance_threshold}"
                )

            self.logger.info(f"Prepaid deduction complete: new_balance=₹{new_balance}")

        elif billing.billing_type == "postpaid":
            # Postpaid: Add to current month cost
            billing.current_month_cost += Decimal(str(cost_inr))
            billing.last_30_days_cost += Decimal(str(cost_inr))

            db.add(billing)
            db.commit()
            db.refresh(billing)

            self.logger.info(f"Postpaid charge recorded: new_current_month=₹{billing.current_month_cost}")

        return result

    def check_low_balance(
        self,
        db: Session,
        *,
        tenant_id: int
    ) -> Dict:
        """
        Check if tenant has low balance (prepaid only).

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            {
                "is_low": bool,
                "balance_inr": float,
                "threshold_inr": float,
                "percentage_remaining": float
            }
        """
        billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)

        if billing.billing_type != "prepaid":
            return {
                "is_low": False,
                "balance_inr": None,
                "threshold_inr": None,
                "percentage_remaining": None
            }

        is_low = billing.balance_inr < billing.low_balance_threshold
        percentage = (float(billing.balance_inr) / float(billing.low_balance_threshold) * 100) if billing.low_balance_threshold > 0 else 100

        return {
            "is_low": is_low,
            "balance_inr": float(billing.balance_inr),
            "threshold_inr": float(billing.low_balance_threshold),
            "percentage_remaining": round(percentage, 2)
        }

    def get_current_usage(
        self,
        db: Session,
        *,
        tenant_id: int
    ) -> Dict:
        """
        Get current billing usage for tenant.

        Returns:
            {
                "tenant_id": int,
                "billing_type": str,
                "balance_inr": float (prepaid only),
                "current_month_cost": float,
                "last_30_days_cost": float,
                "monthly_limit_inr": float (if set),
                "limit_remaining_inr": float (if limit set),
                "limit_usage_percentage": float (if limit set),
                "low_balance_alert": bool
            }
        """
        billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)

        # Perform monthly rollover if needed
        self._check_and_perform_rollover(db, billing)

        result = {
            "tenant_id": tenant_id,
            "billing_type": billing.billing_type,
            "current_month_cost": float(billing.current_month_cost),
            "last_30_days_cost": float(billing.last_30_days_cost),
            "monthly_limit_inr": float(billing.monthly_limit_inr) if billing.monthly_limit_inr else None,
            "low_balance_alert": False
        }

        if billing.billing_type == "prepaid":
            result["balance_inr"] = float(billing.balance_inr)
            result["low_balance_alert"] = billing.balance_inr < billing.low_balance_threshold

        if billing.monthly_limit_inr:
            limit_remaining = float(billing.monthly_limit_inr) - float(billing.current_month_cost)
            limit_usage = (float(billing.current_month_cost) / float(billing.monthly_limit_inr) * 100)

            result["limit_remaining_inr"] = max(0, limit_remaining)
            result["limit_usage_percentage"] = round(limit_usage, 2)

        return result

    def _check_and_perform_rollover(self, db: Session, billing) -> bool:
        """
        Check if we need to rollover to a new month and perform it if needed.

        Simple logic: If current date is first of month and last_rollover_date
        is not today, perform rollover.

        Args:
            db: Database session
            billing: TenantBilling record

        Returns:
            True if rollover was performed, False otherwise
        """
        today = date.today()

        # Check if it's the first of the month
        if today.day != 1:
            return False

        # Check if we already rolled over today
        if billing.last_rollover_date == today:
            return False

        # Perform rollover
        self.logger.info(f"Performing monthly rollover for tenant {billing.tenant_id}")

        # Reset current month cost
        billing.current_month_cost = Decimal("0.00")

        # Update last rollover date
        billing.last_rollover_date = today

        db.add(billing)
        db.commit()
        db.refresh(billing)

        self.logger.info(
            f"Monthly rollover complete for tenant {billing.tenant_id}: "
            f"current_month_cost reset to ₹0.00"
        )

        return True

    def estimate_analysis_cost(
        self,
        *,
        document_size_kb: int,
        document_type: str = "PRD"
    ) -> float:
        """
        Estimate cost for document analysis.

        Simple estimation based on document size.
        More sophisticated models can be added later.

        Args:
            document_size_kb: Document size in KB
            document_type: Type of document

        Returns:
            Estimated cost in INR
        """
        # Base cost: ₹2 per analysis
        base_cost = 2.0

        # Size-based cost: ₹0.01 per KB (max ₹10)
        size_cost = min(document_size_kb * 0.01, 10.0)

        # Total estimate
        total = base_cost + size_cost

        self.logger.debug(f"Cost estimate: size={document_size_kb}KB, type={document_type}, total=₹{total:.2f}")

        return round(total, 2)


# Singleton instance
billing_enforcement_service = BillingEnforcementService()
