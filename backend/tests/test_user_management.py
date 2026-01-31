"""
Tests for User Management API endpoints.

Tests cover:
- User listing (tenant isolation)
- User invitation
- Role updates
- Permission checks
- Multi-tenancy
"""
import pytest


class TestListUsers:
    """Tests for GET /api/v1/users/"""

    def test_list_users_requires_auth(self, client):
        """Listing users without authentication should return 401."""
        response = client.get("/api/v1/users/")
        assert response.status_code == 401

    def test_list_users_with_auth(self, client, auth_headers, test_admin_user):
        """Authenticated user can list users in their tenant."""
        response = client.get("/api/v1/users/", headers=auth_headers)
        assert response.status_code == 200
        
        users = response.json()
        assert isinstance(users, list)
        assert len(users) >= 1
        
        # Should include the admin user
        emails = [u["email"] for u in users]
        assert test_admin_user.email in emails

    def test_list_users_shows_correct_fields(self, client, auth_headers):
        """User response should include all required fields."""
        response = client.get("/api/v1/users/", headers=auth_headers)
        assert response.status_code == 200
        
        users = response.json()
        if users:
            user = users[0]
            assert "id" in user
            assert "email" in user
            assert "roles" in user
            assert "is_active" in user
            assert "tenant_id" in user
            assert "created_at" in user
            # Should NOT include password
            assert "password" not in user
            assert "hashed_password" not in user


class TestInviteUser:
    """Tests for POST /api/v1/users/invite"""

    def test_invite_user_requires_auth(self, client):
        """Inviting a user without authentication should return 401."""
        response = client.post(
            "/api/v1/users/invite",
            json={"email": "newuser@test.com", "password": "Test123!", "roles": ["Developer"]}
        )
        assert response.status_code == 401

    def test_invite_user_requires_cxo_permission(self, client, developer_token):
        """Only CXO users can invite others."""
        headers = {"Authorization": f"Bearer {developer_token}"}
        response = client.post(
            "/api/v1/users/invite",
            headers=headers,
            json={"email": "newuser@test.com", "password": "Test123!", "roles": ["Developer"]}
        )
        # Should return 403 (Forbidden) due to lack of USER_INVITE permission
        assert response.status_code == 403

    def test_invite_user_success(self, client, auth_headers, test_tenant):
        """CXO can successfully invite a new user."""
        response = client.post(
            "/api/v1/users/invite",
            headers=auth_headers,
            json={
                "email": "newdev@testco.com",
                "password": "NewDev123!",
                "roles": ["Developer"]
            }
        )
        assert response.status_code == 201
        
        user = response.json()
        assert user["email"] == "newdev@testco.com"
        assert "Developer" in user["roles"]
        assert user["tenant_id"] == test_tenant.id
        assert user["is_active"] is True

    def test_invite_duplicate_email_fails(self, client, auth_headers, test_admin_user):
        """Cannot invite a user with an existing email."""
        response = client.post(
            "/api/v1/users/invite",
            headers=auth_headers,
            json={
                "email": test_admin_user.email,  # Already exists
                "password": "Test123!",
                "roles": ["Developer"]
            }
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_invite_user_with_multiple_roles(self, client, auth_headers):
        """Can invite a user with multiple roles."""
        response = client.post(
            "/api/v1/users/invite",
            headers=auth_headers,
            json={
                "email": "multiuser@testco.com",
                "password": "Multi123!",
                "roles": ["Developer", "PM"]
            }
        )
        assert response.status_code == 201
        
        user = response.json()
        assert "Developer" in user["roles"]
        assert "PM" in user["roles"]


class TestTenantIsolation:
    """Tests for multi-tenant data isolation."""

    def test_users_from_different_tenants_are_isolated(self, client, db_session):
        """Users can only see users from their own tenant."""
        from app.models.tenant import Tenant
        from app.models.user import User
        from app.core.security import get_password_hash
        
        # Create second tenant
        tenant2 = Tenant(
            name="Other Company",
            subdomain="otherco",
            status="active",
            tier="professional",
            billing_type="prepaid",
            max_users=10,
            max_documents=100,
            settings={}
        )
        db_session.add(tenant2)
        db_session.commit()
        
        # Create user in second tenant
        user2 = User(
            email="admin@otherco.com",
            hashed_password=get_password_hash("Test123!"),
            roles=["CXO"],
            is_active=True,
            tenant_id=tenant2.id
        )
        db_session.add(user2)
        db_session.commit()
        
        # Login as tenant2 user
        login_response = client.post(
            "/api/login/access-token",
            data={"username": "admin@otherco.com", "password": "Test123!"}
        )
        tenant2_token = login_response.json()["access_token"]
        tenant2_headers = {"Authorization": f"Bearer {tenant2_token}"}
        
        # Get users from tenant2
        response = client.get("/api/v1/users/", headers=tenant2_headers)
        assert response.status_code == 200
        
        users = response.json()
        emails = [u["email"] for u in users]
        
        # Should see tenant2 user
        assert "admin@otherco.com" in emails
        
        # Should NOT see tenant1 users
        assert "admin@testco.com" not in emails


class TestAuthentication:
    """Tests for authentication and authorization."""

    def test_login_success(self, client, test_admin_user):
        """User can login with correct credentials."""
        response = client.post(
            "/api/login/access-token",
            data={
                "username": test_admin_user.email,
                "password": "Test123!"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == test_admin_user.email
        assert data["tenant"]["subdomain"] == "testco"

    def test_login_wrong_password(self, client, test_admin_user):
        """Login fails with incorrect password."""
        response = client.post(
            "/api/login/access-token",
            data={
                "username": test_admin_user.email,
                "password": "WrongPassword!"
            }
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """Login fails for non-existent user."""
        response = client.post(
            "/api/login/access-token",
            data={
                "username": "nobody@test.com",
                "password": "Test123!"
            }
        )
        assert response.status_code == 401


# Run with: pytest backend/tests/test_user_management.py -v
