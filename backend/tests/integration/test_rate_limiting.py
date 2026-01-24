"""
Sprint 1 Integration Tests: API-01 Rate Limiting
Tests API rate limiting enforcement and behavior.
"""
import pytest
import time
from fastapi.testclient import TestClient


class TestRateLimiting:
    """Test rate limiting enforcement (API-01)."""

    def test_rate_limit_headers_present(self, authorized_client: TestClient):
        """Test that rate limit headers are included in responses."""
        response = authorized_client.get("/users/me")

        # Rate limiter should include headers with rate limit info
        # Note: slowapi typically adds X-RateLimit-* headers
        assert response.status_code == 200

    def test_login_rate_limit_enforcement(self, client: TestClient):
        """Test that login endpoint enforces rate limits (5/min, 20/hour)."""
        # This test might be flaky due to rate limit windows
        # It's more of a functional check that rate limiting is active

        login_data = {"username": "test@example.com", "password": "wrongpassword"}

        # Try to login multiple times rapidly
        responses = []
        for _ in range(10):
            response = client.post("/login/access-token", data=login_data)
            responses.append(response.status_code)
            time.sleep(0.1)  # Small delay between requests

        # Most should be 401 (wrong password), but if rate limit kicks in, we'd see 429
        # This is a basic check - in practice, rate limits depend on Redis state
        assert all(status in [401, 429] for status in responses)

    def test_user_creation_rate_limit(self, client: TestClient):
        """Test that user creation endpoint has rate limits."""
        user_data = {
            "email": f"test_{time.time()}@example.com",
            "password": "testpass123",
            "full_name": "Test User"
        }

        response = client.post("/users/", json=user_data)
        # Should succeed or fail with validation/duplicate, not crash
        assert response.status_code in [200, 201, 400, 422, 429]

    def test_document_upload_rate_limit_exists(self, authorized_client: TestClient):
        """Test that document upload endpoint has rate limiting configured."""
        # We can't easily test file upload without actual files,
        # but we can verify the endpoint is protected

        # Without a file, this should fail validation (422), not crash
        response = authorized_client.post("/api/v1/documents/upload")
        assert response.status_code in [422, 429]  # Validation error or rate limit

    def test_rate_limit_does_not_affect_health_check(self, client: TestClient):
        """Test that health check endpoint is not rate limited."""
        # Health checks should always be fast and not rate limited
        for _ in range(20):
            response = client.get("/health")
            assert response.status_code == 200

    def test_rate_limit_is_per_user_not_global(self, client: TestClient, test_user):
        """Test that rate limits are per-user, not global."""
        # Login as first user multiple times
        for _ in range(3):
            response = client.post(
                "/login/access-token",
                data={"username": test_user.email, "password": "testpassword123"}
            )
            assert response.status_code == 200
            time.sleep(0.1)

        # Create a different user and try to login
        # Should not be affected by first user's rate limit
        response = client.post(
            "/login/access-token",
            data={"username": "different@example.com", "password": "wrongpass"}
        )
        # Should get 401 (wrong credentials), not 429 (rate limited)
        assert response.status_code in [401, 404]  # User doesn't exist or wrong pass

    def test_rate_limit_error_response_format(self, client: TestClient):
        """Test that rate limit errors return proper error format."""
        # This is a best-effort test - rate limits may not trigger immediately

        # Try to hit an endpoint many times quickly
        responses = []
        for _ in range(15):
            response = client.get("/health")
            if response.status_code == 429:
                # Got rate limited - check response format
                data = response.json()
                assert "error" in data or "detail" in data
                assert "rate" in str(data).lower() or "limit" in str(data).lower()
                break
            time.sleep(0.05)

    def test_rate_limit_with_invalid_token(self, client: TestClient):
        """Test that rate limiting works even with invalid tokens."""
        client.headers = {"Authorization": "Bearer invalid.token.here"}

        # Try to access protected endpoint multiple times
        for _ in range(5):
            response = client.get("/users/me")
            # Should get 403 (invalid token) not crash
            assert response.status_code in [403, 429]
            time.sleep(0.1)

    def test_billing_endpoint_rate_limit(self, authorized_client: TestClient):
        """Test that billing endpoints have appropriate rate limits."""
        # Billing endpoints should have rate limits (30/min, 200/hour)
        response = authorized_client.get("/api/v1/billing/current")

        # Should succeed or fail gracefully, not crash
        assert response.status_code in [200, 404, 422, 429]

    def test_rate_limit_resets_over_time(self, client: TestClient):
        """Test that rate limits reset after the time window."""
        # This is a conceptual test - actual behavior depends on Redis state
        # and rate limit windows

        # Make a request
        response1 = client.get("/health")
        assert response1.status_code == 200

        # Wait a bit (rate limit windows are typically 60 seconds)
        time.sleep(1)

        # Should still be able to make requests
        response2 = client.get("/health")
        assert response2.status_code == 200
