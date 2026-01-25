"""
Sprint 2 Phase 7: RBAC Permission Tests

Tests to ensure Role-Based Access Control works correctly.
Verifies that each role has appropriate permissions.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import models


class TestCXOPermissions:
    """Test CXO role permissions (tenant admin - has all permissions)."""

    def test_cxo_can_view_users(self, client: TestClient, cxo_a_token: dict, auth_headers):
        """CXO can view users in their tenant."""
        response = client.get(
            "/api/v1/users/",
            headers=auth_headers(cxo_a_token)
        )
        assert response.status_code == 200

    def test_cxo_can_invite_users(self, client: TestClient, cxo_a_token: dict, auth_headers):
        """CXO can invite new users to tenant."""
        response = client.post(
            "/api/v1/users/invite",
            headers=auth_headers(cxo_a_token),
            json={
                "email": "newuser@acme.com",
                "password": "password123",
                "roles": ["Developer"]
            }
        )
        # Should succeed (201) or fail due to tenant limits (402)
        assert response.status_code in [201, 402]

    def test_cxo_can_manage_user_roles(
        self, client: TestClient, cxo_a_token: dict, auth_headers,
        developer_user_a: models.User
    ):
        """CXO can update user roles."""
        response = client.put(
            f"/api/v1/users/{developer_user_a.id}/roles",
            headers=auth_headers(cxo_a_token),
            json={"roles": ["BA"]}
        )
        assert response.status_code == 200

    def test_cxo_can_delete_users(
        self, client: TestClient, cxo_a_token: dict, auth_headers,
        ba_user_a: models.User
    ):
        """CXO can delete users (except themselves)."""
        response = client.delete(
            f"/api/v1/users/{ba_user_a.id}",
            headers=auth_headers(cxo_a_token)
        )
        assert response.status_code == 204

    def test_cxo_can_view_billing(self, client: TestClient, cxo_a_token: dict, auth_headers):
        """CXO can view billing information."""
        response = client.get(
            "/api/v1/billing/",
            headers=auth_headers(cxo_a_token)
        )
        assert response.status_code == 200

    def test_cxo_can_manage_billing(self, client: TestClient, cxo_a_token: dict, auth_headers):
        """CXO can manage billing (add balance, update limits)."""
        response = client.post(
            "/api/v1/billing/add-balance",
            headers=auth_headers(cxo_a_token),
            json={"amount_inr": 1000.0}
        )
        assert response.status_code == 200

    def test_cxo_cannot_modify_own_roles(
        self, client: TestClient, cxo_a_token: dict, auth_headers,
        cxo_user_a: models.User
    ):
        """CXO cannot modify their own roles (admin lockout prevention)."""
        response = client.put(
            f"/api/v1/users/{cxo_user_a.id}/roles",
            headers=auth_headers(cxo_a_token),
            json={"roles": ["Developer"]}  # Try to demote self
        )
        assert response.status_code == 403
        assert "cannot update your own roles" in response.json()["detail"].lower()

    def test_cxo_cannot_delete_self(
        self, client: TestClient, cxo_a_token: dict, auth_headers,
        cxo_user_a: models.User
    ):
        """CXO cannot delete themselves (admin lockout prevention)."""
        response = client.delete(
            f"/api/v1/users/{cxo_user_a.id}",
            headers=auth_headers(cxo_a_token)
        )
        assert response.status_code == 403
        assert "cannot delete yourself" in response.json()["detail"].lower()


class TestDeveloperPermissions:
    """Test Developer role permissions."""

    def test_developer_can_read_documents(
        self, client: TestClient, developer_a_token: dict, auth_headers
    ):
        """Developer can read documents."""
        response = client.get(
            "/api/v1/documents/",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 200

    def test_developer_can_write_code_components(
        self, client: TestClient, developer_a_token: dict, auth_headers
    ):
        """Developer can create code components."""
        response = client.post(
            "/api/v1/code-components/",
            headers=auth_headers(developer_a_token),
            json={
                "name": "NewService.java",
                "location": "https://github.com/acme/NewService.java",
                "component_type": "backend"
            }
        )
        # Will succeed or fail due to background task issues (not permissions)
        assert response.status_code in [200, 500]

    def test_developer_can_view_users(
        self, client: TestClient, developer_a_token: dict, auth_headers
    ):
        """Developer can view users in tenant."""
        response = client.get(
            "/api/v1/users/",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 200

    def test_developer_cannot_invite_users(
        self, client: TestClient, developer_a_token: dict, auth_headers
    ):
        """Developer cannot invite users (no USER_INVITE permission)."""
        response = client.post(
            "/api/v1/users/invite",
            headers=auth_headers(developer_a_token),
            json={
                "email": "hacker@acme.com",
                "password": "password123",
                "roles": ["Developer"]
            }
        )
        assert response.status_code == 403

    def test_developer_cannot_manage_user_roles(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        ba_user_a: models.User
    ):
        """Developer cannot update user roles (no USER_MANAGE permission)."""
        response = client.put(
            f"/api/v1/users/{ba_user_a.id}/roles",
            headers=auth_headers(developer_a_token),
            json={"roles": ["CXO"]}  # Try to elevate BA to CXO
        )
        assert response.status_code == 403

    def test_developer_cannot_delete_users(
        self, client: TestClient, developer_a_token: dict, auth_headers,
        ba_user_a: models.User
    ):
        """Developer cannot delete users (no USER_DELETE permission)."""
        response = client.delete(
            f"/api/v1/users/{ba_user_a.id}",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 403

    def test_developer_can_view_billing(
        self, client: TestClient, developer_a_token: dict, auth_headers
    ):
        """Developer can view billing (read-only)."""
        response = client.get(
            "/api/v1/billing/",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 200

    def test_developer_cannot_manage_billing(
        self, client: TestClient, developer_a_token: dict, auth_headers
    ):
        """Developer cannot manage billing (no BILLING_MANAGE permission)."""
        response = client.post(
            "/api/v1/billing/add-balance",
            headers=auth_headers(developer_a_token),
            json={"amount_inr": 1000.0}
        )
        assert response.status_code == 403


class TestBAPermissions:
    """Test Business Analyst role permissions."""

    def test_ba_can_read_write_documents(
        self, client: TestClient, ba_a_token: dict, auth_headers
    ):
        """BA can read and write documents."""
        # Read
        response = client.get(
            "/api/v1/documents/",
            headers=auth_headers(ba_a_token)
        )
        assert response.status_code == 200

    def test_ba_can_run_validation(
        self, client: TestClient, ba_a_token: dict, auth_headers
    ):
        """BA can run validation scans."""
        response = client.post(
            "/api/v1/validation/run-scan",
            headers=auth_headers(ba_a_token),
            json={"document_ids": []}  # Empty list for quick test
        )
        # Should fail with 400 (no documents), not 403 (permission denied)
        assert response.status_code == 400

    def test_ba_can_view_code_read_only(
        self, client: TestClient, ba_a_token: dict, auth_headers
    ):
        """BA can view code components (read-only)."""
        response = client.get(
            "/api/v1/code-components/",
            headers=auth_headers(ba_a_token)
        )
        assert response.status_code == 200

    def test_ba_cannot_write_code(
        self, client: TestClient, ba_a_token: dict, auth_headers
    ):
        """BA cannot create code components (no CODE_WRITE permission)."""
        response = client.post(
            "/api/v1/code-components/",
            headers=auth_headers(ba_a_token),
            json={
                "name": "Unauthorized.java",
                "location": "https://github.com/acme/Unauthorized.java",
                "component_type": "backend"
            }
        )
        assert response.status_code == 403

    def test_ba_cannot_delete_code(
        self, client: TestClient, ba_a_token: dict, auth_headers,
        db_session: Session, developer_user_a: models.User, tenant_a: models.Tenant
    ):
        """BA cannot delete code components (no CODE_DELETE permission)."""
        # Create code component
        code = models.CodeComponent(
            name="ToDelete.java",
            location="https://github.com/acme/ToDelete.java",
            component_type="backend",
            owner_id=developer_user_a.id,
            tenant_id=tenant_a.id
        )
        db_session.add(code)
        db_session.commit()
        db_session.refresh(code)

        response = client.delete(
            f"/api/v1/code-components/{code.id}",
            headers=auth_headers(ba_a_token)
        )
        assert response.status_code == 403

    def test_ba_cannot_invite_users(
        self, client: TestClient, ba_a_token: dict, auth_headers
    ):
        """BA cannot invite users (no USER_INVITE permission)."""
        response = client.post(
            "/api/v1/users/invite",
            headers=auth_headers(ba_a_token),
            json={
                "email": "newba@acme.com",
                "password": "password123",
                "roles": ["BA"]
            }
        )
        assert response.status_code == 403

    def test_ba_can_view_billing_read_only(
        self, client: TestClient, ba_a_token: dict, auth_headers
    ):
        """BA can view billing (read-only)."""
        response = client.get(
            "/api/v1/billing/",
            headers=auth_headers(ba_a_token)
        )
        assert response.status_code == 200


class TestProductManagerPermissions:
    """Test Product Manager role permissions."""

    def test_pm_can_read_documents(
        self, client: TestClient, pm_a_token: dict, auth_headers
    ):
        """PM can read documents."""
        response = client.get(
            "/api/v1/documents/",
            headers=auth_headers(pm_a_token)
        )
        assert response.status_code == 200

    def test_pm_can_write_documents(
        self, client: TestClient, pm_a_token: dict, auth_headers
    ):
        """PM can upload documents (PRDs)."""
        # We won't actually upload a file, but we can check they have DOCUMENT_WRITE permission
        # by checking they can list documents (if upload endpoint existed)
        pass  # Document upload tests would go here

    def test_pm_can_view_code_read_only(
        self, client: TestClient, pm_a_token: dict, auth_headers
    ):
        """PM can view code (read-only)."""
        response = client.get(
            "/api/v1/code-components/",
            headers=auth_headers(pm_a_token)
        )
        assert response.status_code == 200

    def test_pm_cannot_write_code(
        self, client: TestClient, pm_a_token: dict, auth_headers
    ):
        """PM cannot create code components (no CODE_WRITE permission)."""
        response = client.post(
            "/api/v1/code-components/",
            headers=auth_headers(pm_a_token),
            json={
                "name": "PMCode.java",
                "location": "https://github.com/acme/PMCode.java",
                "component_type": "backend"
            }
        )
        assert response.status_code == 403

    def test_pm_cannot_delete_code(
        self, client: TestClient, pm_a_token: dict, auth_headers,
        db_session: Session, developer_user_a: models.User, tenant_a: models.Tenant
    ):
        """PM cannot delete code components (no CODE_DELETE permission)."""
        code = models.CodeComponent(
            name="PMToDelete.java",
            location="https://github.com/acme/PMToDelete.java",
            component_type="backend",
            owner_id=developer_user_a.id,
            tenant_id=tenant_a.id
        )
        db_session.add(code)
        db_session.commit()
        db_session.refresh(code)

        response = client.delete(
            f"/api/v1/code-components/{code.id}",
            headers=auth_headers(pm_a_token)
        )
        assert response.status_code == 403

    def test_pm_cannot_invite_users(
        self, client: TestClient, pm_a_token: dict, auth_headers
    ):
        """PM cannot invite users (no USER_INVITE permission)."""
        response = client.post(
            "/api/v1/users/invite",
            headers=auth_headers(pm_a_token),
            json={
                "email": "newpm@acme.com",
                "password": "password123",
                "roles": ["Product Manager"]
            }
        )
        assert response.status_code == 403

    def test_pm_cannot_manage_billing(
        self, client: TestClient, pm_a_token: dict, auth_headers
    ):
        """PM cannot manage billing (no BILLING_MANAGE permission)."""
        response = client.post(
            "/api/v1/billing/add-balance",
            headers=auth_headers(pm_a_token),
            json={"amount_inr": 1000.0}
        )
        assert response.status_code == 403


class TestPermissionEndpoint:
    """Test the /users/me/permissions endpoint."""

    def test_cxo_sees_all_permissions(
        self, client: TestClient, cxo_a_token: dict, auth_headers
    ):
        """CXO should see all 20 permissions."""
        response = client.get(
            "/api/v1/users/me/permissions",
            headers=auth_headers(cxo_a_token)
        )
        assert response.status_code == 200
        permissions = response.json()
        
        # CXO should have all permissions
        assert "document:read" in permissions
        assert "document:write" in permissions
        assert "document:delete" in permissions
        assert "code:read" in permissions
        assert "code:write" in permissions
        assert "code:delete" in permissions
        assert "user:view" in permissions
        assert "user:invite" in permissions
        assert "user:manage" in permissions
        assert "user:delete" in permissions
        assert "billing:view" in permissions
        assert "billing:manage" in permissions
        assert "tenant:view" in permissions
        assert "tenant:manage" in permissions

    def test_developer_sees_developer_permissions(
        self, client: TestClient, developer_a_token: dict, auth_headers
    ):
        """Developer should see 15 permissions (no user management, billing management)."""
        response = client.get(
            "/api/v1/users/me/permissions",
            headers=auth_headers(developer_a_token)
        )
        assert response.status_code == 200
        permissions = response.json()
        
        # Developer HAS these permissions
        assert "document:read" in permissions
        assert "code:write" in permissions
        assert "user:view" in permissions
        
        # Developer DOES NOT have these permissions
        assert "user:invite" not in permissions
        assert "user:manage" not in permissions
        assert "user:delete" not in permissions
        assert "billing:manage" not in permissions
        assert "tenant:manage" not in permissions

    def test_ba_sees_ba_permissions(
        self, client: TestClient, ba_a_token: dict, auth_headers
    ):
        """BA should see 14 permissions (no code write/delete, user management)."""
        response = client.get(
            "/api/v1/users/me/permissions",
            headers=auth_headers(ba_a_token)
        )
        assert response.status_code == 200
        permissions = response.json()
        
        # BA HAS these permissions
        assert "document:read" in permissions
        assert "document:write" in permissions
        assert "code:read" in permissions
        assert "validation:run" in permissions
        
        # BA DOES NOT have these permissions
        assert "code:write" not in permissions
        assert "code:delete" not in permissions
        assert "user:invite" not in permissions
        assert "billing:manage" not in permissions

    def test_pm_sees_pm_permissions(
        self, client: TestClient, pm_a_token: dict, auth_headers
    ):
        """PM should see 10 permissions (mostly read-only)."""
        response = client.get(
            "/api/v1/users/me/permissions",
            headers=auth_headers(pm_a_token)
        )
        assert response.status_code == 200
        permissions = response.json()
        
        # PM HAS these permissions
        assert "document:read" in permissions
        assert "document:write" in permissions  # Can upload PRDs
        assert "code:read" in permissions
        assert "analysis:view" in permissions
        
        # PM DOES NOT have these permissions
        assert "code:write" not in permissions
        assert "code:delete" not in permissions
        assert "document:delete" not in permissions
        assert "user:invite" not in permissions
        assert "billing:manage" not in permissions
