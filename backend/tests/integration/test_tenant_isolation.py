"""
Sprint 2 Phase 7: Tenant Isolation Tests

Tests to ensure complete data isolation between tenants.
Verifies that users in tenant A cannot access data from tenant B.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import models, crud, schemas


class TestDocumentIsolation:
    """Test that documents are isolated by tenant."""

    def test_user_cannot_see_other_tenant_documents(
        self, client: TestClient, developer_a_token: dict, developer_b_token: dict,
        auth_headers, db_session: Session, tenant_a: models.Tenant, tenant_b: models.Tenant,
        developer_user_a: models.User, developer_user_b: models.User
    ):
        """User in tenant A cannot see documents from tenant B."""
        # Create document in tenant A
        doc_a = models.Document(
            filename="tenant_a_doc.pdf",
            file_path="/uploads/tenant_a_doc.pdf",
            owner_id=developer_user_a.id,
            tenant_id=tenant_a.id,
            document_type="PRD"
        )
        db_session.add(doc_a)
        db_session.commit()
        db_session.refresh(doc_a)

        # Create document in tenant B
        doc_b = models.Document(
            filename="tenant_b_doc.pdf",
            file_path="/uploads/tenant_b_doc.pdf",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id,
            document_type="PRD"
        )
        db_session.add(doc_b)
        db_session.commit()
        db_session.refresh(doc_b)

        # User A lists documents - should only see doc_a
        response = client.get(
            "/api/v1/documents/",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 200
        documents = response.json()
        document_ids = [d["id"] for d in documents]
        assert doc_a.id in document_ids
        assert doc_b.id not in document_ids  # CRITICAL: Cannot see tenant B docs

        # User B lists documents - should only see doc_b
        response = client.get(
            "/api/v1/documents/",
            headers=auth_headers(developer_b_token)
        )
        assert response.status_code == 200
        documents = response.json()
        document_ids = [d["id"] for d in documents]
        assert doc_b.id in document_ids
        assert doc_a.id not in document_ids  # CRITICAL: Cannot see tenant A docs

    def test_user_cannot_access_other_tenant_document_by_id(
        self, client: TestClient, developer_a_token: dict,
        auth_headers, db_session: Session, tenant_b: models.Tenant,
        developer_user_b: models.User
    ):
        """User in tenant A cannot access document from tenant B by ID (404, not 403)."""
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

        # User A tries to access document B by ID
        # Should get 404 (Schrödinger's Document pattern)
        response = client.get(
            f"/api/v1/documents/{doc_b.id}",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 404  # Not 403 - don't leak existence
        assert "not found" in response.json()["detail"].lower()


class TestCodeComponentIsolation:
    """Test that code components are isolated by tenant."""

    def test_user_cannot_see_other_tenant_code_components(
        self, client: TestClient, developer_a_token: dict, developer_b_token: dict,
        auth_headers, db_session: Session, tenant_a: models.Tenant, tenant_b: models.Tenant,
        developer_user_a: models.User, developer_user_b: models.User
    ):
        """User in tenant A cannot see code components from tenant B."""
        # Create code component in tenant A
        code_a = models.CodeComponent(
            name="ServiceA.java",
            location="https://github.com/acme/repo/ServiceA.java",
            component_type="backend",
            owner_id=developer_user_a.id,
            tenant_id=tenant_a.id
        )
        db_session.add(code_a)
        db_session.commit()
        db_session.refresh(code_a)

        # Create code component in tenant B
        code_b = models.CodeComponent(
            name="ServiceB.java",
            location="https://github.com/beta/repo/ServiceB.java",
            component_type="backend",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id
        )
        db_session.add(code_b)
        db_session.commit()
        db_session.refresh(code_b)

        # User A lists code components - should only see code_a
        response = client.get(
            "/api/v1/code-components/",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 200
        components = response.json()
        component_ids = [c["id"] for c in components]
        assert code_a.id in component_ids
        assert code_b.id not in component_ids  # CRITICAL: Cannot see tenant B code

    def test_user_cannot_delete_other_tenant_code_component(
        self, client: TestClient, developer_a_token: dict,
        auth_headers, db_session: Session, tenant_b: models.Tenant,
        developer_user_b: models.User
    ):
        """User in tenant A cannot delete code component from tenant B."""
        # Create code component in tenant B
        code_b = models.CodeComponent(
            name="CriticalService.java",
            location="https://github.com/beta/repo/CriticalService.java",
            component_type="backend",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id
        )
        db_session.add(code_b)
        db_session.commit()
        db_session.refresh(code_b)

        # User A tries to delete code component B
        response = client.delete(
            f"/api/v1/code-components/{code_b.id}",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 404  # Schrödinger's Document pattern

        # Verify code component still exists
        db_session.refresh(code_b)
        assert code_b.id is not None


class TestAnalysisResultIsolation:
    """Test that analysis results are isolated by tenant."""

    def test_user_cannot_see_other_tenant_analysis_results(
        self, client: TestClient, developer_a_token: dict,
        auth_headers, db_session: Session, tenant_b: models.Tenant,
        developer_user_b: models.User
    ):
        """User in tenant A cannot see analysis results from tenant B."""
        # Create document in tenant B
        doc_b = models.Document(
            filename="prd_b.pdf",
            file_path="/uploads/prd_b.pdf",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id,
            document_type="PRD"
        )
        db_session.add(doc_b)
        db_session.commit()
        db_session.refresh(doc_b)

        # Create analysis result in tenant B
        analysis_b = models.AnalysisResult(
            document_id=doc_b.id,
            analysis_type="business_rules",
            result_data={"rule": "Secret business logic"},
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id
        )
        db_session.add(analysis_b)
        db_session.commit()

        # User A tries to access analysis results for document B
        response = client.get(
            f"/api/v1/analysis-results/document/{doc_b.id}",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 404  # Document not found in tenant A


class TestMismatchIsolation:
    """Test that mismatches are isolated by tenant."""

    def test_user_cannot_see_other_tenant_mismatches(
        self, client: TestClient, developer_a_token: dict, developer_b_token: dict,
        auth_headers, db_session: Session, tenant_a: models.Tenant, tenant_b: models.Tenant,
        developer_user_a: models.User, developer_user_b: models.User
    ):
        """User in tenant A cannot see mismatches from tenant B."""
        # Create document and code in tenant A
        doc_a = models.Document(
            filename="doc_a.pdf",
            file_path="/uploads/doc_a.pdf",
            owner_id=developer_user_a.id,
            tenant_id=tenant_a.id,
            document_type="PRD"
        )
        code_a = models.CodeComponent(
            name="CodeA.java",
            location="https://github.com/acme/CodeA.java",
            component_type="backend",
            owner_id=developer_user_a.id,
            tenant_id=tenant_a.id
        )
        db_session.add_all([doc_a, code_a])
        db_session.commit()
        db_session.refresh(doc_a)
        db_session.refresh(code_a)

        # Create link and mismatch in tenant A
        link_a = models.DocumentCodeLink(
            document_id=doc_a.id,
            code_component_id=code_a.id,
            owner_id=developer_user_a.id,
            tenant_id=tenant_a.id
        )
        db_session.add(link_a)
        db_session.commit()
        db_session.refresh(link_a)

        mismatch_a = models.Mismatch(
            link_id=link_a.id,
            mismatch_type="api_missing",
            severity="high",
            description="Mismatch in tenant A",
            owner_id=developer_user_a.id,
            tenant_id=tenant_a.id
        )
        db_session.add(mismatch_a)
        db_session.commit()

        # Create similar setup in tenant B
        doc_b = models.Document(
            filename="doc_b.pdf",
            file_path="/uploads/doc_b.pdf",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id,
            document_type="PRD"
        )
        code_b = models.CodeComponent(
            name="CodeB.java",
            location="https://github.com/beta/CodeB.java",
            component_type="backend",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id
        )
        db_session.add_all([doc_b, code_b])
        db_session.commit()
        db_session.refresh(doc_b)
        db_session.refresh(code_b)

        link_b = models.DocumentCodeLink(
            document_id=doc_b.id,
            code_component_id=code_b.id,
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id
        )
        db_session.add(link_b)
        db_session.commit()
        db_session.refresh(link_b)

        mismatch_b = models.Mismatch(
            link_id=link_b.id,
            mismatch_type="api_missing",
            severity="high",
            description="Mismatch in tenant B",
            owner_id=developer_user_b.id,
            tenant_id=tenant_b.id
        )
        db_session.add(mismatch_b)
        db_session.commit()

        # User A gets mismatches - should only see mismatch_a
        response = client.get(
            "/api/v1/validation/mismatches",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 200
        mismatches = response.json()
        mismatch_ids = [m["id"] for m in mismatches]
        assert mismatch_a.id in mismatch_ids
        assert mismatch_b.id not in mismatch_ids  # CRITICAL: Cannot see tenant B mismatches


class TestUserIsolation:
    """Test that user management is isolated by tenant."""

    def test_cxo_can_only_see_own_tenant_users(
        self, client: TestClient, cxo_a_token: dict, cxo_b_token: dict,
        auth_headers, tenant_a: models.Tenant, tenant_b: models.Tenant,
        developer_user_a: models.User, developer_user_b: models.User
    ):
        """CXO in tenant A can only see users from tenant A."""
        # CXO A lists users - should only see tenant A users
        response = client.get(
            "/api/v1/users/",
            headers=auth_headers(cxo_a_token)
        )
        assert response.status_code == 200
        users = response.json()
        user_emails = [u["email"] for u in users]
        assert developer_user_a.email in user_emails
        assert developer_user_b.email not in user_emails  # CRITICAL: Cannot see tenant B users

        # CXO B lists users - should only see tenant B users
        response = client.get(
            "/api/v1/users/",
            headers=auth_headers(cxo_b_token)
        )
        assert response.status_code == 200
        users = response.json()
        user_emails = [u["email"] for u in users]
        assert developer_user_b.email in user_emails
        assert developer_user_a.email not in user_emails  # CRITICAL: Cannot see tenant A users

    def test_cxo_cannot_modify_other_tenant_user_roles(
        self, client: TestClient, cxo_a_token: dict,
        auth_headers, developer_user_b: models.User
    ):
        """CXO in tenant A cannot modify user roles in tenant B."""
        response = client.put(
            f"/api/v1/users/{developer_user_b.id}/roles",
            headers=auth_headers(cxo_a_token),
            json={"roles": ["CXO"]}  # Try to elevate tenant B user to CXO
        )
        # Should get 404 (user not in tenant A)
        assert response.status_code == 404

    def test_cxo_cannot_delete_other_tenant_user(
        self, client: TestClient, cxo_a_token: dict,
        auth_headers, developer_user_b: models.User, db_session: Session
    ):
        """CXO in tenant A cannot delete user from tenant B."""
        response = client.delete(
            f"/api/v1/users/{developer_user_b.id}",
            headers=auth_headers(cxo_a_token)
        )
        # Should get 404 (user not in tenant A)
        assert response.status_code == 404

        # Verify user still exists
        db_session.refresh(developer_user_b)
        assert developer_user_b.id is not None
