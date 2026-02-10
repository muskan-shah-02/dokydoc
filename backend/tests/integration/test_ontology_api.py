"""
SPRINT 3 Day 5: Integration Tests for Ontology API Endpoints

Tests:
- GET /ontology/concepts — list, filter by type
- POST /ontology/concepts — create
- GET /ontology/concepts/{id} — get with relationships
- GET /ontology/concepts/search — search by name
- DELETE /ontology/concepts/{id} — cascade delete
- POST /ontology/relationships — create
- GET /ontology/graph — full graph
- GET /ontology/stats — stats
"""

import pytest
from app.crud.crud_ontology_concept import CRUDOntologyConcept
from app.models.ontology_concept import OntologyConcept


@pytest.fixture
def seed_concepts(db_session, test_tenant):
    """Seed some concepts directly in DB for testing API reads."""
    crud = CRUDOntologyConcept(OntologyConcept)
    c1 = crud.get_or_create(
        db_session, name="User Auth", concept_type="FEATURE",
        tenant_id=test_tenant.id, confidence_score=0.9
    )
    c2 = crud.get_or_create(
        db_session, name="PostgreSQL", concept_type="TECHNOLOGY",
        tenant_id=test_tenant.id, confidence_score=0.95
    )
    c3 = crud.get_or_create(
        db_session, name="Order Flow", concept_type="PROCESS",
        tenant_id=test_tenant.id, confidence_score=0.8
    )
    return c1, c2, c3


# ============================================================
# CONCEPT ENDPOINT TESTS
# ============================================================

class TestOntologyConceptAPI:

    def test_list_concepts(self, client, auth_headers, seed_concepts):
        """GET /ontology/concepts returns all concepts."""
        response = client.get("/api/ontology/concepts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3

    def test_list_concepts_filter_by_type(self, client, auth_headers, seed_concepts):
        """GET /ontology/concepts?concept_type=FEATURE filters correctly."""
        response = client.get(
            "/api/ontology/concepts?concept_type=FEATURE",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert all(c["concept_type"] == "FEATURE" for c in data)

    def test_create_concept(self, client, auth_headers, test_tenant):
        """POST /ontology/concepts creates a new concept."""
        response = client.post(
            "/api/ontology/concepts",
            headers=auth_headers,
            json={
                "name": "New Concept",
                "concept_type": "FEATURE",
                "description": "Test description",
                "confidence_score": 0.75,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Concept"
        assert data["concept_type"] == "FEATURE"
        assert data["source_type"] == "document"

    def test_get_concept_with_relationships(self, client, auth_headers, seed_concepts):
        """GET /ontology/concepts/{id} returns concept with relationships."""
        c1, c2, _ = seed_concepts
        response = client.get(
            f"/api/ontology/concepts/{c1.id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "User Auth"
        assert "outgoing_relationships" in data
        assert "incoming_relationships" in data

    def test_get_concept_not_found(self, client, auth_headers):
        """GET /ontology/concepts/99999 returns 404."""
        response = client.get("/api/ontology/concepts/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_search_concepts(self, client, auth_headers, seed_concepts):
        """GET /ontology/concepts/search?q=user finds matching concepts."""
        response = client.get(
            "/api/ontology/concepts/search?q=user",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any("user" in c["name"].lower() for c in data)

    def test_delete_concept(self, client, auth_headers, seed_concepts):
        """DELETE /ontology/concepts/{id} removes concept."""
        c1, _, _ = seed_concepts
        response = client.delete(
            f"/api/ontology/concepts/{c1.id}",
            headers=auth_headers
        )
        assert response.status_code == 204

        # Verify deleted
        response = client.get(
            f"/api/ontology/concepts/{c1.id}",
            headers=auth_headers
        )
        assert response.status_code == 404

    def test_list_concept_types(self, client, auth_headers, seed_concepts):
        """GET /ontology/concepts/types returns distinct types."""
        response = client.get("/api/ontology/concepts/types", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "FEATURE" in data
        assert "TECHNOLOGY" in data


# ============================================================
# RELATIONSHIP ENDPOINT TESTS
# ============================================================

class TestOntologyRelationshipAPI:

    def test_create_relationship(self, client, auth_headers, seed_concepts):
        """POST /ontology/relationships creates a new relationship."""
        c1, c2, _ = seed_concepts
        response = client.post(
            "/api/ontology/relationships",
            headers=auth_headers,
            json={
                "source_concept_id": c1.id,
                "target_concept_id": c2.id,
                "relationship_type": "uses",
                "confidence_score": 0.8,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["relationship_type"] == "uses"

    def test_create_self_referencing_relationship_fails(self, client, auth_headers, seed_concepts):
        """POST /ontology/relationships with same source and target returns 400."""
        c1, _, _ = seed_concepts
        response = client.post(
            "/api/ontology/relationships",
            headers=auth_headers,
            json={
                "source_concept_id": c1.id,
                "target_concept_id": c1.id,
                "relationship_type": "depends_on",
            },
        )
        assert response.status_code == 400

    def test_create_relationship_invalid_concept(self, client, auth_headers):
        """POST /ontology/relationships with non-existent concept returns 404."""
        response = client.post(
            "/api/ontology/relationships",
            headers=auth_headers,
            json={
                "source_concept_id": 99999,
                "target_concept_id": 99998,
                "relationship_type": "implements",
            },
        )
        assert response.status_code == 404


# ============================================================
# GRAPH & STATS ENDPOINT TESTS
# ============================================================

class TestOntologyGraphAPI:

    def test_get_graph(self, client, auth_headers, seed_concepts):
        """GET /ontology/graph returns nodes and edges."""
        response = client.get("/api/ontology/graph", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert "total_nodes" in data
        assert data["total_nodes"] >= 3

    def test_get_stats(self, client, auth_headers, seed_concepts):
        """GET /ontology/stats returns concept and relationship counts."""
        response = client.get("/api/ontology/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_concepts" in data
        assert "total_relationships" in data
        assert "concept_types" in data
        assert data["total_concepts"] >= 3
