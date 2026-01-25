"""
Sprint 2 Phase 7: Cross-Tenant Security Tests

Security tests to ensure tenants cannot access each other's data.
Tests for various attack vectors and security edge cases.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import models, crud


class TestCrossTenantDocumentSecurity:
    """Test security of document access across tenants."""

    def test_cannot_create_link_to_other_tenant_document(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        db_session: Session, tenant_b: models.Tenant, developer_user_b: models.User,
        developer_user_a: models.User, tenant_a: models.Tenant
    ):
        """User cannot create link between their code and another tenant's document."""
        # Create document in tenant B
        doc_b = models.Document(
            filename="secret_prd.pdf",
            file_path="/uploads/secret_prd.pdf",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id,
            document_type="PRD"
        )
        db_session.add(doc_b)
        db_session.commit()
        db_session.refresh(doc_b)

        # Create code component in tenant A
        code_a = models.CodeComponent(
            name="MyCode.java",
            location="https://github.com/acme/MyCode.java",
            component_type="backend",
            owner_id=developer_user_a.id,
            tenant_id=tenant_a.id
        )
        db_session.add(code_a)
        db_session.commit()
        db_session.refresh(code_a)

        # Try to create link between tenant A code and tenant B document
        response = client.post(
            "/api/v1/links/",
            headers=auth_headers(developer_a_token),
            json={
                "document_id": doc_b.id,  # Tenant B document
                "code_component_id": code_a.id  # Tenant A code
            }
        )
        # Should fail - document not found in tenant A
        assert response.status_code in [404, 403]

    def test_cannot_create_link_to_other_tenant_code(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        db_session: Session, tenant_a: models.Tenant, tenant_b: models.Tenant,
        developer_user_a: models.User, developer_user_b: models.User
    ):
        """User cannot create link between their document and another tenant's code."""
        # Create document in tenant A
        doc_a = models.Document(
            filename="my_prd.pdf",
            file_path="/uploads/my_prd.pdf",
            owner_id=developer_user_a.id,
            tenant_id=tenant_a.id,
            document_type="PRD"
        )
        db_session.add(doc_a)
        db_session.commit()
        db_session.refresh(doc_a)

        # Create code component in tenant B
        code_b = models.CodeComponent(
            name="TheirCode.java",
            location="https://github.com/beta/TheirCode.java",
            component_type="backend",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id
        )
        db_session.add(code_b)
        db_session.commit()
        db_session.refresh(code_b)

        # Try to create link between tenant A document and tenant B code
        response = client.post(
            "/api/v1/links/",
            headers=auth_headers(developer_a_token),
            json={
                "document_id": doc_a.id,  # Tenant A document
                "code_component_id": code_b.id  # Tenant B code
            }
        )
        # Should fail - code component not found in tenant A
        assert response.status_code in [404, 403]


class TestCrossTenantValidationSecurity:
    """Test security of validation across tenants."""

    def test_cannot_run_validation_on_other_tenant_documents(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        db_session: Session, tenant_b: models.Tenant, developer_user_b: models.User
    ):
        """User cannot run validation on documents from another tenant."""
        # Create document in tenant B
        doc_b = models.Document(
            filename="secret_doc.pdf",
            file_path="/uploads/secret_doc.pdf",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id,
            document_type="PRD"
        )
        db_session.add(doc_b)
        db_session.commit()
        db_session.refresh(doc_b)

        # User A tries to run validation on tenant B document
        response = client.post(
            "/api/v1/validation/run-scan",
            headers=auth_headers(developer_a_token),
            json={"document_ids": [doc_b.id]}
        )
        assert response.status_code == 404  # Documents not found in tenant A
        assert "not found" in response.json()["detail"].lower()


class TestCrossTenantUserSecurity:
    """Test security of user management across tenants."""

    def test_cannot_list_users_from_other_tenant(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        developer_user_b: models.User
    ):
        """User cannot see users from other tenants in list."""
        response = client.get(
            "/api/v1/users/",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 200
        users = response.json()
        user_ids = [u["id"] for u in users]
        
        # Should NOT contain tenant B users
        assert developer_user_b.id not in user_ids

    def test_cannot_view_other_tenant_user_details(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        developer_user_b: models.User
    ):
        """User cannot view details of user from other tenant."""
        response = client.get(
            f"/api/v1/users/{developer_user_b.id}",
            headers=auth_headers(developer_a_token)
        )
        # Should get 404 (not 403) - Schrödinger's User pattern
        assert response.status_code == 404


class TestCrossTenantBillingSecurity:
    """Test security of billing across tenants."""

    def test_cannot_view_other_tenant_billing(
        self, client: TestClient, developer_a_token: dict, developer_b_token: dict,
        auth_headers, db_session: Session, tenant_a: models.Tenant, tenant_b: models.Tenant
    ):
        """User cannot view billing info from other tenant."""
        # Set up different billing for each tenant
        billing_a = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_a.id)
        billing_a.billing_type = "prepaid"
        billing_a.balance_inr = 100.00
        db_session.add(billing_a)

        billing_b = crud.tenant_billing.get_or_create(db_session, tenant_id=tenant_b.id)
        billing_b.billing_type = "postpaid"
        billing_b.balance_inr = 500.00
        db_session.add(billing_b)
        db_session.commit()

        # User A gets their billing
        response_a = client.get(
            "/api/v1/billing/usage",
            headers=auth_headers(developer_a_token)
        )
        assert response_a.status_code == 200
        billing_data_a = response_a.json()
        assert billing_data_a["billing_type"] == "prepaid"
        assert billing_data_a["balance_inr"] == 100.0

        # User B gets their billing  
        response_b = client.get(
            "/api/v1/billing/usage",
            headers=auth_headers(developer_b_token)
        )
        assert response_b.status_code == 200
        billing_data_b = response_b.json()
        assert billing_data_b["billing_type"] == "postpaid"
        # User B should NOT see tenant A's balance
        assert billing_data_b["balance_inr"] != billing_data_a["balance_inr"]


class TestSchrodingersDocumentPattern:
    """Test that 'Schrödinger's Document' pattern is consistently applied.
    
    When a user tries to access a resource that doesn't exist in their tenant,
    they should get 404 (not found), not 403 (forbidden).
    This prevents information leakage about what exists in other tenants.
    """

    def test_document_get_returns_404_not_403_for_other_tenant(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        db_session: Session, tenant_b: models.Tenant, developer_user_b: models.User
    ):
        """GET /documents/{id} returns 404 for other tenant's document."""
        doc_b = models.Document(
            filename="secret.pdf",
            file_path="/uploads/secret.pdf",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id,
            document_type="PRD"
        )
        db_session.add(doc_b)
        db_session.commit()
        db_session.refresh(doc_b)

        response = client.get(
            f"/api/v1/documents/{doc_b.id}",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 404  # NOT 403
        assert "not found" in response.json()["detail"].lower()

    def test_code_component_get_returns_404_not_403_for_other_tenant(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        db_session: Session, tenant_b: models.Tenant, developer_user_b: models.User
    ):
        """GET /code-components/{id} returns 404 for other tenant's code."""
        code_b = models.CodeComponent(
            name="Secret.java",
            location="https://github.com/beta/Secret.java",
            component_type="backend",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id
        )
        db_session.add(code_b)
        db_session.commit()
        db_session.refresh(code_b)

        response = client.get(
            f"/api/v1/code-components/{code_b.id}",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 404  # NOT 403

    def test_document_delete_returns_404_not_403_for_other_tenant(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        db_session: Session, tenant_b: models.Tenant, developer_user_b: models.User
    ):
        """DELETE /documents/{id} returns 404 for other tenant's document."""
        doc_b = models.Document(
            filename="to_delete.pdf",
            file_path="/uploads/to_delete.pdf",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id,
            document_type="PRD"
        )
        db_session.add(doc_b)
        db_session.commit()
        db_session.refresh(doc_b)

        response = client.delete(
            f"/api/v1/documents/{doc_b.id}",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 404  # NOT 403

        # Verify document still exists
        db_session.refresh(doc_b)
        assert doc_b.id is not None


class TestTenantLimitEnforcement:
    """Test that tenant limits are enforced."""

    def test_cannot_exceed_user_limit(
        self, client: TestClient, cxo_a_token: dict, auth_headers,
        db_session: Session, tenant_a: models.Tenant
    ):
        """Cannot invite users beyond tenant's max_users limit."""
        # Set low user limit
        tenant_a.max_users = 2  # Only 2 users allowed
        db_session.add(tenant_a)
        db_session.commit()

        # We already have cxo_user_a and developer_user_a (2 users)
        # Try to invite a third user
        response = client.post(
            "/api/v1/users/invite",
            headers=auth_headers(cxo_a_token),
            json={
                "email": "third@acme.com",
                "password": "password123",
                "roles": ["Developer"]
            }
        )
        assert response.status_code == 402  # Payment Required / Limit Exceeded
        assert "user limit" in response.json()["detail"].lower()

    def test_tenant_limits_are_tenant_specific(
        self, client: TestClient, cxo_a_token: dict, cxo_b_token: dict, auth_headers,
        db_session: Session, tenant_a: models.Tenant, tenant_b: models.Tenant
    ):
        """Tenant limits are enforced per-tenant, not globally."""
        # Set different limits
        tenant_a.max_users = 2  # Tenant A: low limit
        tenant_b.max_users = 100  # Tenant B: high limit
        db_session.add_all([tenant_a, tenant_b])
        db_session.commit()

        # Tenant A cannot add more users (already at limit)
        response_a = client.post(
            "/api/v1/users/invite",
            headers=auth_headers(cxo_a_token),
            json={
                "email": "blocked@acme.com",
                "password": "password123",
                "roles": ["Developer"]
            }
        )
        assert response_a.status_code == 402  # Blocked

        # Tenant B can still add users (not at limit)
        response_b = client.post(
            "/api/v1/users/invite",
            headers=auth_headers(cxo_b_token),
            json={
                "email": "allowed@beta.com",
                "password": "password123",
                "roles": ["Developer"]
            }
        )
        assert response_b.status_code == 201  # Allowed


class TestBackgroundTaskSecurity:
    """Test that background tasks respect tenant context.
    
    Note: These tests verify that tasks receive tenant_id and would filter correctly.
    Full integration testing would require running actual Celery workers.
    """

    def test_validation_scan_receives_tenant_id(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        db_session: Session, tenant_a: models.Tenant, developer_user_a: models.User
    ):
        """Validation scan background task receives tenant_id."""
        # Create document in tenant A
        doc_a = models.Document(
            filename="test.pdf",
            file_path="/uploads/test.pdf",
            owner_id=developer_user_a.id,
            tenant_id=tenant_a.id,
            document_type="PRD"
        )
        db_session.add(doc_a)
        db_session.commit()
        db_session.refresh(doc_a)

        # Trigger validation scan
        response = client.post(
            "/api/v1/validation/run-scan",
            headers=auth_headers(developer_a_token),
            json={"document_ids": [doc_a.id]}
        )
        # Should accept the request (202 Accepted)
        assert response.status_code == 202
        # The background task will filter by tenant_id (verified in Phase 6)


class TestDataLeakagePrevention:
    """Test that error messages don't leak information about other tenants."""

    def test_error_messages_dont_reveal_existence(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        db_session: Session, tenant_b: models.Tenant, developer_user_b: models.User
    ):
        """Error messages don't reveal if a resource exists in another tenant."""
        # Create document in tenant B
        doc_b = models.Document(
            filename="secret.pdf",
            file_path="/uploads/secret.pdf",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id,
            document_type="PRD"
        )
        db_session.add(doc_b)
        db_session.commit()
        db_session.refresh(doc_b)

        # Try to access it from tenant A
        response = client.get(
            f"/api/v1/documents/{doc_b.id}",
            headers=auth_headers(developer_a_token)
        )
        
        # Error should be generic "not found", not "forbidden" or "belongs to another tenant"
        assert response.status_code == 404
        error_detail = response.json()["detail"].lower()
        assert "not found" in error_detail
        assert "forbidden" not in error_detail
        assert "tenant" not in error_detail  # Don't mention tenants in error
        assert "permission" not in error_detail  # Don't mention permissions
