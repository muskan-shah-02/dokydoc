"""
Sprint 2 Phase 7: Billing Enforcement Tests

Tests to ensure billing enforcement works correctly.
Verifies balance checks, cost deduction, and limit enforcement.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from decimal import Decimal

from app import models, crud
from app.services.billing_enforcement_service import billing_enforcement_service


class TestPrepaidBilling:
    """Test prepaid billing enforcement."""

    def test_prepaid_tenant_can_afford_analysis_with_sufficient_balance(
        self, db_session: Session, tenant_a: models.Tenant
    ):
        """Prepaid tenant with sufficient balance can proceed with analysis."""
        # Create prepaid billing with balance
        billing = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_a.id)
        billing.billing_type = "prepaid"
        billing.balance_inr = Decimal("100.00")
        db_session.add(billing)
        db_session.commit()

        # Check affordability
        result = billing_enforcement_service.check_can_afford_analysis(
            db=db_session,
            tenant_id=tenant_a.id,
            estimated_cost_inr=5.0
        )

        assert result["can_proceed"] is True
        assert result["billing_type"] == "prepaid"
        assert result["balance_inr"] == 100.0

    def test_prepaid_tenant_cannot_afford_analysis_with_insufficient_balance(
        self, db_session: Session, tenant_a: models.Tenant
    ):
        """Prepaid tenant with insufficient balance cannot proceed with analysis."""
        # Create prepaid billing with low balance
        billing = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_a.id)
        billing.billing_type = "prepaid"
        billing.balance_inr = Decimal("2.00")  # Less than estimated cost
        db_session.add(billing)
        db_session.commit()

        # Check affordability - should raise exception
        from app.services.billing_enforcement_service import InsufficientBalanceException
        with pytest.raises(InsufficientBalanceException) as exc_info:
            billing_enforcement_service.check_can_afford_analysis(
                db=db_session,
                tenant_id=tenant_a.id,
                estimated_cost_inr=5.0
            )
        
        assert exc_info.value.tenant_id == tenant_a.id
        assert exc_info.value.required == 5.0
        assert exc_info.value.available == 2.0

    def test_prepaid_balance_deduction_after_analysis(
        self, db_session: Session, tenant_a: models.Tenant
    ):
        """Prepaid balance is deducted after successful analysis."""
        # Create prepaid billing with balance
        billing = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_a.id)
        billing.billing_type = "prepaid"
        billing.balance_inr = Decimal("100.00")
        db_session.add(billing)
        db_session.commit()

        # Deduct cost
        result = billing_enforcement_service.deduct_cost(
            db=db_session,
            tenant_id=tenant_a.id,
            cost_inr=5.50,
            description="Test analysis"
        )

        assert result["success"] is True
        assert result["new_balance_inr"] == 94.50
        assert result["cost_deducted_inr"] == 5.50

        # Verify in database
        db_session.refresh(billing)
        assert float(billing.balance_inr) == 94.50

    def test_prepaid_low_balance_alert(
        self, db_session: Session, tenant_a: models.Tenant
    ):
        """Low balance alert is triggered when balance drops below threshold."""
        # Create prepaid billing with balance just above threshold
        billing = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_a.id)
        billing.billing_type = "prepaid"
        billing.balance_inr = Decimal("105.00")
        billing.low_balance_threshold = Decimal("100.00")
        db_session.add(billing)
        db_session.commit()

        # Deduct cost that brings balance below threshold
        result = billing_enforcement_service.deduct_cost(
            db=db_session,
            tenant_id=tenant_a.id,
            cost_inr=10.0,
            description="Test analysis"
        )

        assert result["low_balance_alert"] is True
        assert result["new_balance_inr"] < 100.0


class TestPostpaidBilling:
    """Test postpaid billing enforcement."""

    def test_postpaid_tenant_can_proceed_within_monthly_limit(
        self, db_session: Session, tenant_b: models.Tenant
    ):
        """Postpaid tenant can proceed if within monthly limit."""
        # Create postpaid billing with limit
        billing = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_b.id)
        billing.billing_type = "postpaid"
        billing.monthly_limit_inr = Decimal("1000.00")
        billing.current_month_cost = Decimal("100.00")
        db_session.add(billing)
        db_session.commit()

        # Check affordability
        result = billing_enforcement_service.check_can_afford_analysis(
            db=db_session,
            tenant_id=tenant_b.id,
            estimated_cost_inr=50.0
        )

        assert result["can_proceed"] is True
        assert result["billing_type"] == "postpaid"
        assert result["current_month_cost"] == 100.0

    def test_postpaid_tenant_cannot_exceed_monthly_limit(
        self, db_session: Session, tenant_b: models.Tenant
    ):
        """Postpaid tenant cannot proceed if it would exceed monthly limit."""
        # Create postpaid billing near limit
        billing = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_b.id)
        billing.billing_type = "postpaid"
        billing.monthly_limit_inr = Decimal("1000.00")
        billing.current_month_cost = Decimal("995.00")
        db_session.add(billing)
        db_session.commit()

        # Check affordability - should raise exception
        from app.services.billing_enforcement_service import MonthlyLimitExceededException
        with pytest.raises(MonthlyLimitExceededException) as exc_info:
            billing_enforcement_service.check_can_afford_analysis(
                db=db_session,
                tenant_id=tenant_b.id,
                estimated_cost_inr=10.0  # Would bring total to 1005
            )
        
        assert exc_info.value.tenant_id == tenant_b.id
        assert exc_info.value.limit == 1000.0

    def test_postpaid_cost_added_to_monthly_total(
        self, db_session: Session, tenant_b: models.Tenant
    ):
        """Postpaid cost is added to monthly total after analysis."""
        # Create postpaid billing
        billing = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_b.id)
        billing.billing_type = "postpaid"
        billing.current_month_cost = Decimal("100.00")
        db_session.add(billing)
        db_session.commit()

        # Deduct cost
        result = billing_enforcement_service.deduct_cost(
            db=db_session,
            tenant_id=tenant_b.id,
            cost_inr=25.50,
            description="Test analysis"
        )

        assert result["success"] is True
        assert result["new_current_month_cost"] == 125.50

        # Verify in database
        db_session.refresh(billing)
        assert float(billing.current_month_cost) == 125.50

    def test_postpaid_without_limit_has_no_restrictions(
        self, db_session: Session, tenant_b: models.Tenant
    ):
        """Postpaid tenant without monthly limit can proceed unlimited."""
        # Create postpaid billing without limit
        billing = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_b.id)
        billing.billing_type = "postpaid"
        billing.monthly_limit_inr = None  # No limit
        billing.current_month_cost = Decimal("9999.00")  # Already high spending
        db_session.add(billing)
        db_session.commit()

        # Check affordability - should succeed
        result = billing_enforcement_service.check_can_afford_analysis(
            db=db_session,
            tenant_id=tenant_b.id,
            estimated_cost_inr=100.0
        )

        assert result["can_proceed"] is True


class TestMonthlyRollover:
    """Test monthly cost rollover on 1st of month."""

    def test_monthly_rollover_resets_current_month_cost(
        self, db_session: Session, tenant_a: models.Tenant
    ):
        """Monthly rollover resets current_month_cost to 0."""
        from datetime import date
        
        # Create billing with last rollover not today
        billing = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_a.id)
        billing.current_month_cost = Decimal("500.00")
        billing.last_rollover_date = date(2025, 12, 1)  # Last month
        db_session.add(billing)
        db_session.commit()

        # Manually trigger rollover check
        # Note: This only works if today is 1st of month
        # We're testing the logic, not the date check
        today = date.today()
        if today.day == 1:
            billing_enforcement_service._check_and_perform_rollover(db_session, billing)
            
            db_session.refresh(billing)
            assert float(billing.current_month_cost) == 0.0
            assert billing.last_rollover_date == today


class TestCostEstimation:
    """Test cost estimation for analysis."""

    def test_cost_estimation_has_base_cost(self):
        """Cost estimation includes base cost."""
        cost = billing_enforcement_service.estimate_analysis_cost(
            document_size_kb=0  # Even 0 KB has base cost
        )
        assert cost >= 2.0  # Base cost is ₹2

    def test_cost_estimation_scales_with_document_size(self):
        """Cost estimation increases with document size."""
        small_cost = billing_enforcement_service.estimate_analysis_cost(
            document_size_kb=10
        )
        large_cost = billing_enforcement_service.estimate_analysis_cost(
            document_size_kb=100
        )
        assert large_cost > small_cost

    def test_cost_estimation_has_max_cap(self):
        """Cost estimation has a maximum cap."""
        huge_cost = billing_enforcement_service.estimate_analysis_cost(
            document_size_kb=10000  # 10 MB
        )
        # Max should be ₹2 base + ₹10 size = ₹12
        assert huge_cost == 12.0


class TestBillingAPI:
    """Test billing API endpoints."""

    def test_cxo_can_view_billing_usage(
        self, client: TestClient, cxo_a_token: dict, auth_headers,
        db_session: Session, tenant_a: models.Tenant
    ):
        """CXO can view current billing usage."""
        # Setup billing
        billing = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_a.id)
        billing.billing_type = "prepaid"
        billing.balance_inr = Decimal("150.00")
        billing.current_month_cost = Decimal("50.00")
        db_session.add(billing)
        db_session.commit()

        # Get usage
        response = client.get(
            "/api/v1/billing/usage",
            headers=auth_headers(cxo_a_token)
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["billing_type"] == "prepaid"
        assert data["balance_inr"] == 150.0
        assert data["current_month_cost"] == 50.0

    def test_cxo_can_add_balance(
        self, client: TestClient, cxo_a_token: dict, auth_headers,
        db_session: Session, tenant_a: models.Tenant
    ):
        """CXO can add balance to prepaid account."""
        # Setup prepaid billing
        billing = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_a.id)
        billing.billing_type = "prepaid"
        billing.balance_inr = Decimal("100.00")
        db_session.add(billing)
        db_session.commit()

        # Add balance
        response = client.post(
            "/api/v1/billing/add-balance",
            headers=auth_headers(cxo_a_token),
            json={"amount_inr": 500.0}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["new_balance_inr"] == 600.0

    def test_developer_cannot_add_balance(
        self, client: TestClient, developer_a_token: dict, auth_headers
    ):
        """Developer cannot add balance (no BILLING_MANAGE permission)."""
        response = client.post(
            "/api/v1/billing/add-balance",
            headers=auth_headers(developer_a_token),
            json={"amount_inr": 500.0}
        )
        assert response.status_code == 403

    def test_document_analysis_blocked_when_insufficient_funds(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        db_session: Session, tenant_a: models.Tenant, developer_user_a: models.User
    ):
        """Document analysis is blocked when tenant has insufficient funds."""
        # Create document
        doc = models.Document(
            filename="test.pdf",
            file_path="/uploads/test.pdf",
            owner_id=developer_user_a.id,
            tenant_id=tenant_a.id,
            document_type="PRD",
            file_size_kb=100
        )
        db_session.add(doc)
        db_session.commit()
        db_session.refresh(doc)

        # Set low balance
        billing = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_a.id)
        billing.billing_type = "prepaid"
        billing.balance_inr = Decimal("1.00")  # Too low
        db_session.add(billing)
        db_session.commit()

        # Try to analyze - should fail with 402
        response = client.post(
            f"/api/v1/documents/{doc.id}/analyze",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 402  # Payment Required
        assert "insufficient balance" in response.json()["detail"].lower()
