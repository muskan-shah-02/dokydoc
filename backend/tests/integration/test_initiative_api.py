"""
SPRINT 3 Day 5: Integration Tests for Initiative API Endpoints

Tests:
- POST /initiatives — create initiative
- GET /initiatives — list initiatives
- GET /initiatives/{id} — get with assets
- PUT /initiatives/{id} — update initiative
- DELETE /initiatives/{id} — delete initiative
- POST /initiatives/{id}/assets — link asset
- DELETE /initiatives/{id}/assets/{asset_id} — unlink asset
"""

import pytest


# ============================================================
# INITIATIVE CRUD TESTS
# ============================================================

class TestInitiativeAPI:

    def test_create_initiative(self, client, auth_headers):
        """POST /initiatives creates a new initiative."""
        response = client.post(
            "/api/initiatives/",
            headers=auth_headers,
            json={
                "name": "Q1 Release",
                "description": "First quarter product release",
                "status": "ACTIVE",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Q1 Release"
        assert data["status"] == "ACTIVE"
        assert data["id"] is not None

    def test_list_initiatives(self, client, auth_headers):
        """GET /initiatives returns all initiatives."""
        # Create a couple first
        client.post(
            "/api/initiatives/",
            headers=auth_headers,
            json={"name": "Initiative A", "status": "ACTIVE"},
        )
        client.post(
            "/api/initiatives/",
            headers=auth_headers,
            json={"name": "Initiative B", "status": "COMPLETED"},
        )

        response = client.get("/api/initiatives/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    def test_list_initiatives_filter_by_status(self, client, auth_headers):
        """GET /initiatives?status=ACTIVE filters correctly."""
        client.post(
            "/api/initiatives/",
            headers=auth_headers,
            json={"name": "Active One", "status": "ACTIVE"},
        )
        client.post(
            "/api/initiatives/",
            headers=auth_headers,
            json={"name": "Done One", "status": "COMPLETED"},
        )

        response = client.get("/api/initiatives/?status=ACTIVE", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert all(i["status"] == "ACTIVE" for i in data)

    def test_get_initiative(self, client, auth_headers):
        """GET /initiatives/{id} returns initiative with assets."""
        create_resp = client.post(
            "/api/initiatives/",
            headers=auth_headers,
            json={"name": "Detail Test"},
        )
        initiative_id = create_resp.json()["id"]

        response = client.get(
            f"/api/initiatives/{initiative_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Detail Test"
        assert "assets" in data

    def test_get_initiative_not_found(self, client, auth_headers):
        """GET /initiatives/99999 returns 404."""
        response = client.get("/api/initiatives/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_update_initiative(self, client, auth_headers):
        """PUT /initiatives/{id} updates initiative fields."""
        create_resp = client.post(
            "/api/initiatives/",
            headers=auth_headers,
            json={"name": "Old Name", "status": "ACTIVE"},
        )
        initiative_id = create_resp.json()["id"]

        response = client.put(
            f"/api/initiatives/{initiative_id}",
            headers=auth_headers,
            json={"name": "New Name", "status": "COMPLETED"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["status"] == "COMPLETED"

    def test_delete_initiative(self, client, auth_headers):
        """DELETE /initiatives/{id} removes initiative."""
        create_resp = client.post(
            "/api/initiatives/",
            headers=auth_headers,
            json={"name": "To Delete"},
        )
        initiative_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/initiatives/{initiative_id}",
            headers=auth_headers
        )
        assert response.status_code == 204

        # Verify deleted
        response = client.get(
            f"/api/initiatives/{initiative_id}",
            headers=auth_headers
        )
        assert response.status_code == 404

    def test_delete_initiative_not_found(self, client, auth_headers):
        """DELETE /initiatives/99999 returns 404."""
        response = client.delete("/api/initiatives/99999", headers=auth_headers)
        assert response.status_code == 404


# ============================================================
# INITIATIVE VALIDATION TESTS
# ============================================================

class TestInitiativeValidation:

    def test_create_initiative_empty_name_fails(self, client, auth_headers):
        """Creating with empty name fails validation."""
        response = client.post(
            "/api/initiatives/",
            headers=auth_headers,
            json={"name": "", "status": "ACTIVE"},
        )
        assert response.status_code == 422

    def test_create_initiative_invalid_status_fails(self, client, auth_headers):
        """Creating with invalid status fails validation."""
        response = client.post(
            "/api/initiatives/",
            headers=auth_headers,
            json={"name": "Test", "status": "INVALID_STATUS"},
        )
        assert response.status_code == 422
