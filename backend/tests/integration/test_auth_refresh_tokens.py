"""
Sprint 1 Integration Tests: BE-04/AUTH-01 Refresh Token Flow
Tests the complete refresh token authentication flow.
"""
import pytest
from fastapi.testclient import TestClient


class TestRefreshTokenFlow:
    """Test refresh token authentication flow (BE-04/AUTH-01)."""

    def test_login_returns_both_tokens(self, client: TestClient, test_user):
        """Test that login returns both access and refresh tokens."""
        response = client.post(
            "/login/access-token",
            data={"username": test_user.email, "password": "testpassword123"}
        )

        assert response.status_code == 200
        data = response.json()

        # BE-04 FIX: Should return both tokens
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 50  # JWT tokens are long
        assert len(data["refresh_token"]) > 50

    def test_access_token_works_for_api_requests(self, authorized_client: TestClient):
        """Test that access token can be used for API requests."""
        response = authorized_client.get("/users/me")

        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == "test@example.com"

    def test_refresh_token_cannot_be_used_for_api_requests(self, client: TestClient, user_token: dict):
        """Test that refresh token is rejected for API requests."""
        # Try to use refresh token instead of access token
        client.headers = {"Authorization": f"Bearer {user_token['refresh_token']}"}
        response = client.get("/users/me")

        # BE-04 FIX: Should reject refresh token for API calls
        assert response.status_code == 403
        assert "Invalid token type" in response.json()["detail"]

    def test_refresh_endpoint_returns_new_tokens(self, client: TestClient, user_token: dict):
        """Test that /refresh endpoint returns new tokens."""
        response = client.post(
            "/login/refresh",
            json={"refresh_token": user_token["refresh_token"]}
        )

        assert response.status_code == 200
        data = response.json()

        # BE-04 FIX: Should return new access and refresh tokens
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["access_token"] != user_token["access_token"]  # Should be different
        assert data["refresh_token"] != user_token["refresh_token"]  # Should be different

    def test_refresh_endpoint_rejects_access_token(self, client: TestClient, user_token: dict):
        """Test that /refresh endpoint rejects access tokens."""
        response = client.post(
            "/login/refresh",
            json={"refresh_token": user_token["access_token"]}  # Using access token instead
        )

        # BE-04 FIX: Should reject access token for refresh
        assert response.status_code == 403
        assert "Invalid token type" in response.json()["detail"]

    def test_refresh_endpoint_rejects_invalid_token(self, client: TestClient):
        """Test that /refresh endpoint rejects invalid tokens."""
        response = client.post(
            "/login/refresh",
            json={"refresh_token": "invalid.token.here"}
        )

        assert response.status_code == 403
        assert "Could not validate" in response.json()["detail"]

    def test_new_access_token_works_after_refresh(self, client: TestClient, user_token: dict):
        """Test that new access token from refresh works for API calls."""
        # Get new tokens via refresh
        refresh_response = client.post(
            "/login/refresh",
            json={"refresh_token": user_token["refresh_token"]}
        )
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()

        # Use new access token for API request
        client.headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
        response = client.get("/users/me")

        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == "test@example.com"
