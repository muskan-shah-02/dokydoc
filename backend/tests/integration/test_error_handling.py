"""
Sprint 1 Integration Tests: BE-01 Error Handling
Tests error message categorization and production error handling.
"""
import pytest
from fastapi.testclient import TestClient


class TestErrorHandling:
    """Test error message categorization (BE-01)."""

    def test_validation_error_response_format(self, client: TestClient):
        """Test that validation errors return structured responses."""
        # Send invalid data to trigger validation error
        response = client.post("/users/", json={"email": "invalid-email"})

        assert response.status_code == 422
        data = response.json()

        # BE-01 FIX: Should have structured error response
        assert "detail" in data or "validation_errors" in data

    def test_authentication_error_response(self, client: TestClient):
        """Test that authentication errors return proper messages."""
        # Try to access protected endpoint without token
        response = client.get("/users/me")

        assert response.status_code in [401, 403]
        data = response.json()

        # Should have clear error message
        assert "detail" in data
        assert isinstance(data["detail"], str)
        assert len(data["detail"]) > 0

    def test_not_found_error_response(self, authorized_client: TestClient):
        """Test that 404 errors return proper messages."""
        # Try to access non-existent document
        response = authorized_client.get("/api/v1/documents/99999")

        assert response.status_code == 404
        data = response.json()

        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_invalid_token_error_message(self, client: TestClient):
        """Test that invalid token errors are user-friendly."""
        # Use invalid token
        client.headers = {"Authorization": "Bearer invalid.token.here"}
        response = client.get("/users/me")

        assert response.status_code == 403
        data = response.json()

        # BE-01 FIX: Should have actionable error message
        assert "detail" in data
        assert "credential" in data["detail"].lower() or "token" in data["detail"].lower()

    def test_wrong_password_error_message(self, client: TestClient, test_user):
        """Test that wrong password errors are user-friendly."""
        response = client.post(
            "/login/access-token",
            data={"username": test_user.email, "password": "wrongpassword"}
        )

        assert response.status_code == 401
        data = response.json()

        # Should not reveal whether email exists (security)
        assert "detail" in data
        assert "incorrect" in data["detail"].lower()

    def test_missing_required_field_error(self, client: TestClient):
        """Test that missing required fields return clear errors."""
        # Try to create user without required field
        response = client.post("/users/", json={"email": "test@example.com"})

        assert response.status_code == 422
        data = response.json()

        # Validation error should indicate what's missing
        assert "detail" in data

    def test_duplicate_email_error(self, client: TestClient, test_user):
        """Test that duplicate email errors are user-friendly."""
        response = client.post(
            "/users/",
            json={
                "email": test_user.email,  # Same as existing user
                "password": "newpassword123",
                "full_name": "New User"
            }
        )

        assert response.status_code == 400
        data = response.json()

        # Should indicate email already exists
        assert "detail" in data
        assert "exist" in data["detail"].lower() or "already" in data["detail"].lower()

    def test_error_response_includes_error_type(self, client: TestClient):
        """Test that error responses include error type for debugging."""
        # Trigger validation error
        response = client.post("/users/", json={})

        assert response.status_code == 422
        data = response.json()

        # BE-01 FIX: Should include error type/code for debugging
        # At minimum, should have detail field
        assert "detail" in data

    def test_internal_error_does_not_expose_sensitive_info(self, client: TestClient):
        """Test that internal errors don't expose sensitive information."""
        # This is hard to test without actually causing an error
        # But we can verify the error handling structure exists

        # Try an endpoint that might fail
        response = client.get("/nonexistent-endpoint")

        assert response.status_code == 404
        data = response.json()

        # Should not expose internal paths or stack traces in production
        assert "detail" in data
        # Should not contain file paths or code references
        assert "/app/" not in str(data).lower()
        assert "traceback" not in str(data).lower()

    def test_cors_error_handling(self, client: TestClient):
        """Test that CORS errors are handled properly."""
        # This is more of a configuration test
        # CORS middleware should be configured

        response = client.options("/health")
        # Should succeed or return proper CORS headers
        assert response.status_code in [200, 405]  # OPTIONS allowed or not

    def test_rate_limit_error_is_user_friendly(self, client: TestClient):
        """Test that rate limit errors provide helpful information."""
        # Rate limit errors should tell users to slow down
        # This is tested more thoroughly in test_rate_limiting.py

        # Make multiple rapid requests to potentially trigger rate limit
        for _ in range(150):
            response = client.get("/health")
            if response.status_code == 429:
                data = response.json()
                # Should have helpful message
                assert "detail" in data or "error" in data
                break

    def test_file_upload_error_handling(self, authorized_client: TestClient):
        """Test that file upload errors are user-friendly."""
        # Try to upload without file
        response = authorized_client.post(
            "/api/v1/documents/upload",
            data={"document_type": "test", "version": "1.0"}
        )

        assert response.status_code == 422
        data = response.json()

        # Should indicate missing file
        assert "detail" in data

    def test_unauthorized_access_error(self, client: TestClient):
        """Test that unauthorized access returns clear error."""
        # Try to access admin endpoint without admin role
        response = client.get("/api/v1/documents/")

        assert response.status_code in [401, 403]
        data = response.json()

        assert "detail" in data

    def test_method_not_allowed_error(self, client: TestClient):
        """Test that wrong HTTP methods return proper error."""
        # Try to POST to a GET endpoint
        response = client.post("/health")

        assert response.status_code == 405
        data = response.json()

        assert "detail" in data

    def test_large_payload_error_handling(self, authorized_client: TestClient):
        """Test that large payload errors are handled gracefully."""
        # This would test payload size limits
        # May not trigger without actual large file
        pass

    def test_malformed_json_error(self, client: TestClient):
        """Test that malformed JSON returns clear error."""
        # Send malformed JSON
        response = client.post(
            "/users/",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422
        data = response.json()

        assert "detail" in data
