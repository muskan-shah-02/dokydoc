"""
SPRINT 3 Day 5: Integration Tests for Repository API Endpoints

Tests:
- POST /repositories — onboard repository
- GET /repositories — list repositories
- GET /repositories/{id} — get with progress
- PUT /repositories/{id} — update metadata
- DELETE /repositories/{id} — delete repository
- POST /repositories/{id}/analyze — trigger analysis (validation only)
- GET /repositories/stats/summary — stats
- Duplicate URL detection (409)
"""

import pytest


# ============================================================
# REPOSITORY CRUD TESTS
# ============================================================

class TestRepositoryAPI:

    def test_onboard_repository(self, client, auth_headers):
        """POST /repositories onboards a new repository."""
        response = client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={
                "name": "dokydoc-backend",
                "url": "https://github.com/example/dokydoc-backend",
                "default_branch": "main",
                "description": "Backend monorepo",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "dokydoc-backend"
        assert data["url"] == "https://github.com/example/dokydoc-backend"
        assert data["analysis_status"] == "pending"
        assert data["total_files"] == 0

    def test_duplicate_url_rejected(self, client, auth_headers):
        """POST /repositories with duplicate URL returns 409."""
        url = "https://github.com/example/unique-repo"
        client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "Repo 1", "url": url},
        )
        response = client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "Repo 2", "url": url},
        )
        assert response.status_code == 409

    def test_list_repositories(self, client, auth_headers):
        """GET /repositories returns all repositories."""
        client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "Repo A", "url": "https://github.com/example/repo-a"},
        )
        client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "Repo B", "url": "https://github.com/example/repo-b"},
        )

        response = client.get("/api/repositories/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    def test_get_repository_with_progress(self, client, auth_headers):
        """GET /repositories/{id} returns progress details."""
        create_resp = client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "Progress Test", "url": "https://github.com/example/progress"},
        )
        repo_id = create_resp.json()["id"]

        response = client.get(
            f"/api/repositories/{repo_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Progress Test"
        assert "progress_percent" in data

    def test_get_repository_not_found(self, client, auth_headers):
        """GET /repositories/99999 returns 404."""
        response = client.get("/api/repositories/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_update_repository(self, client, auth_headers):
        """PUT /repositories/{id} updates metadata."""
        create_resp = client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "Old Repo", "url": "https://github.com/example/old"},
        )
        repo_id = create_resp.json()["id"]

        response = client.put(
            f"/api/repositories/{repo_id}",
            headers=auth_headers,
            json={"name": "Updated Repo", "description": "New description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Repo"
        assert data["description"] == "New description"

    def test_delete_repository(self, client, auth_headers):
        """DELETE /repositories/{id} removes repository."""
        create_resp = client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "To Delete", "url": "https://github.com/example/delete"},
        )
        repo_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/repositories/{repo_id}",
            headers=auth_headers
        )
        assert response.status_code == 204

        # Verify deleted
        response = client.get(
            f"/api/repositories/{repo_id}",
            headers=auth_headers
        )
        assert response.status_code == 404

    def test_delete_repository_not_found(self, client, auth_headers):
        """DELETE /repositories/99999 returns 404."""
        response = client.delete("/api/repositories/99999", headers=auth_headers)
        assert response.status_code == 404


# ============================================================
# ANALYSIS TRIGGER TESTS
# ============================================================

class TestRepositoryAnalysis:

    def test_trigger_analysis_empty_file_list(self, client, auth_headers):
        """POST /repositories/{id}/analyze with empty list returns 400."""
        create_resp = client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "Empty Test", "url": "https://github.com/example/empty"},
        )
        repo_id = create_resp.json()["id"]

        response = client.post(
            f"/api/repositories/{repo_id}/analyze",
            headers=auth_headers,
            json=[],
        )
        assert response.status_code == 400

    def test_trigger_analysis_invalid_file_structure(self, client, auth_headers):
        """POST /repositories/{id}/analyze with invalid file objects returns 422."""
        create_resp = client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "Invalid Test", "url": "https://github.com/example/invalid"},
        )
        repo_id = create_resp.json()["id"]

        response = client.post(
            f"/api/repositories/{repo_id}/analyze",
            headers=auth_headers,
            json=[{"only_path": "missing_url_field"}],
        )
        assert response.status_code == 422

    def test_trigger_analysis_repo_not_found(self, client, auth_headers):
        """POST /repositories/99999/analyze returns 404."""
        response = client.post(
            "/api/repositories/99999/analyze",
            headers=auth_headers,
            json=[{"path": "a.py", "url": "https://example.com/a.py"}],
        )
        assert response.status_code == 404


# ============================================================
# STATS TESTS
# ============================================================

class TestRepositoryStats:

    def test_get_stats(self, client, auth_headers):
        """GET /repositories/stats/summary returns stat counters."""
        # Create a repo first
        client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "Stats Repo", "url": "https://github.com/example/stats"},
        )

        response = client.get("/api/repositories/stats/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_repositories" in data
        assert "completed" in data
        assert "analyzing" in data
        assert "failed" in data
        assert "pending" in data
        assert data["total_repositories"] >= 1


# ============================================================
# VALIDATION TESTS
# ============================================================

class TestRepositoryValidation:

    def test_create_repository_empty_url_fails(self, client, auth_headers):
        """Creating with empty URL fails validation."""
        response = client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "Test", "url": ""},
        )
        assert response.status_code == 422

    def test_create_repository_empty_name_fails(self, client, auth_headers):
        """Creating with empty name fails validation."""
        response = client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "", "url": "https://github.com/example/x"},
        )
        assert response.status_code == 422

    def test_create_repository_invalid_url_format(self, client, auth_headers):
        """Creating with invalid URL format fails validation."""
        response = client.post(
            "/api/repositories/",
            headers=auth_headers,
            json={"name": "Test", "url": "not-a-valid-url"},
        )
        assert response.status_code == 422
