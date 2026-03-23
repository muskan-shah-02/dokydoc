"""
SPRINT 3 Day 5: Integration Tests for Ontology CRUD Operations

Tests:
- OntologyConcept CRUD (get_or_create, search, filter by type, source_type)
- OntologyRelationship CRUD (create_if_not_exists, graph queries)
- Tenant isolation (cross-tenant data invisible)
- Layer-scoped deduplication (document vs code concepts)
- promote_to_both() only works via explicit call
"""

import pytest
from app.crud.crud_ontology_concept import CRUDOntologyConcept
from app.crud.crud_ontology_relationship import CRUDOntologyRelationship
from app.models.ontology_concept import OntologyConcept
from app.models.ontology_relationship import OntologyRelationship


@pytest.fixture
def concept_crud():
    return CRUDOntologyConcept(OntologyConcept)


@pytest.fixture
def rel_crud():
    return CRUDOntologyRelationship(OntologyRelationship)


# ============================================================
# CONCEPT CRUD TESTS
# ============================================================

class TestOntologyConceptCRUD:

    def test_get_or_create_new_concept(self, db_session, test_tenant, concept_crud):
        """Creating a new concept returns a fresh record."""
        concept = concept_crud.get_or_create(
            db_session,
            name="User Authentication",
            concept_type="FEATURE",
            tenant_id=test_tenant.id,
            description="Login flow",
            confidence_score=0.9,
        )
        assert concept.id is not None
        assert concept.name == "User Authentication"
        assert concept.concept_type == "FEATURE"
        assert concept.source_type == "document"
        assert concept.confidence_score == 0.9
        assert concept.tenant_id == test_tenant.id

    def test_get_or_create_idempotent(self, db_session, test_tenant, concept_crud):
        """Calling get_or_create twice with the same name+type returns the same record."""
        c1 = concept_crud.get_or_create(
            db_session, name="Payment Gateway", concept_type="SYSTEM",
            tenant_id=test_tenant.id, confidence_score=0.7
        )
        c2 = concept_crud.get_or_create(
            db_session, name="payment gateway", concept_type="SYSTEM",
            tenant_id=test_tenant.id, confidence_score=0.6
        )
        assert c1.id == c2.id  # Same record, case-insensitive match

    def test_get_or_create_updates_higher_confidence(self, db_session, test_tenant, concept_crud):
        """Confidence score is updated if the new score is higher."""
        c1 = concept_crud.get_or_create(
            db_session, name="Redis Cache", concept_type="TECHNOLOGY",
            tenant_id=test_tenant.id, confidence_score=0.6
        )
        c2 = concept_crud.get_or_create(
            db_session, name="redis cache", concept_type="TECHNOLOGY",
            tenant_id=test_tenant.id, confidence_score=0.95
        )
        assert c2.confidence_score == 0.95

    def test_get_or_create_does_not_downgrade_confidence(self, db_session, test_tenant, concept_crud):
        """Confidence score is NOT updated if the new score is lower."""
        c1 = concept_crud.get_or_create(
            db_session, name="Docker", concept_type="TECHNOLOGY",
            tenant_id=test_tenant.id, confidence_score=0.9
        )
        c2 = concept_crud.get_or_create(
            db_session, name="docker", concept_type="TECHNOLOGY",
            tenant_id=test_tenant.id, confidence_score=0.5
        )
        assert c2.confidence_score == 0.9

    def test_layer_scoped_dedup(self, db_session, test_tenant, concept_crud):
        """Document and code concepts with the same name are SEPARATE."""
        doc = concept_crud.get_or_create(
            db_session, name="User Authentication", concept_type="FEATURE",
            tenant_id=test_tenant.id, source_type="document"
        )
        code = concept_crud.get_or_create(
            db_session, name="User Authentication", concept_type="FEATURE",
            tenant_id=test_tenant.id, source_type="code"
        )
        assert doc.id != code.id
        assert doc.source_type == "document"
        assert code.source_type == "code"

    def test_promote_to_both(self, db_session, test_tenant, concept_crud):
        """promote_to_both() explicitly changes source_type."""
        concept = concept_crud.get_or_create(
            db_session, name="Payment Processing", concept_type="PROCESS",
            tenant_id=test_tenant.id, source_type="document"
        )
        assert concept.source_type == "document"

        promoted = concept_crud.promote_to_both(
            db_session, concept_id=concept.id, tenant_id=test_tenant.id
        )
        assert promoted.source_type == "both"

    def test_promote_to_both_idempotent(self, db_session, test_tenant, concept_crud):
        """Promoting a concept that's already 'both' is a no-op."""
        concept = concept_crud.get_or_create(
            db_session, name="Analytics", concept_type="FEATURE",
            tenant_id=test_tenant.id
        )
        concept_crud.promote_to_both(db_session, concept_id=concept.id, tenant_id=test_tenant.id)
        promoted_again = concept_crud.promote_to_both(
            db_session, concept_id=concept.id, tenant_id=test_tenant.id
        )
        assert promoted_again.source_type == "both"

    def test_get_by_source_type(self, db_session, test_tenant, concept_crud):
        """Filter concepts by source_type."""
        concept_crud.get_or_create(
            db_session, name="BRD Feature", concept_type="FEATURE",
            tenant_id=test_tenant.id, source_type="document"
        )
        concept_crud.get_or_create(
            db_session, name="Auth Service", concept_type="SYSTEM",
            tenant_id=test_tenant.id, source_type="code"
        )

        docs = concept_crud.get_by_source_type(
            db_session, source_type="document", tenant_id=test_tenant.id
        )
        codes = concept_crud.get_by_source_type(
            db_session, source_type="code", tenant_id=test_tenant.id
        )
        assert len(docs) >= 1
        assert len(codes) >= 1
        assert all(c.source_type == "document" for c in docs)
        assert all(c.source_type == "code" for c in codes)

    def test_search_by_name(self, db_session, test_tenant, concept_crud):
        """Search concepts by partial name match."""
        concept_crud.get_or_create(
            db_session, name="User Authentication", concept_type="FEATURE",
            tenant_id=test_tenant.id
        )
        concept_crud.get_or_create(
            db_session, name="User Profile Management", concept_type="FEATURE",
            tenant_id=test_tenant.id
        )
        concept_crud.get_or_create(
            db_session, name="Payment Processing", concept_type="PROCESS",
            tenant_id=test_tenant.id
        )

        results = concept_crud.search_by_name(
            db_session, query="user", tenant_id=test_tenant.id
        )
        assert len(results) == 2
        assert all("user" in c.name.lower() for c in results)

    def test_get_by_type(self, db_session, test_tenant, concept_crud):
        """Filter concepts by type."""
        concept_crud.get_or_create(
            db_session, name="React", concept_type="TECHNOLOGY",
            tenant_id=test_tenant.id
        )
        concept_crud.get_or_create(
            db_session, name="FastAPI", concept_type="TECHNOLOGY",
            tenant_id=test_tenant.id
        )
        concept_crud.get_or_create(
            db_session, name="Login Flow", concept_type="PROCESS",
            tenant_id=test_tenant.id
        )

        techs = concept_crud.get_by_type(
            db_session, concept_type="TECHNOLOGY", tenant_id=test_tenant.id
        )
        assert len(techs) == 2

    def test_count_by_tenant(self, db_session, test_tenant, concept_crud):
        """Count active concepts for a tenant."""
        concept_crud.get_or_create(
            db_session, name="A", concept_type="FEATURE", tenant_id=test_tenant.id
        )
        concept_crud.get_or_create(
            db_session, name="B", concept_type="FEATURE", tenant_id=test_tenant.id
        )
        count = concept_crud.count_by_tenant(db_session, tenant_id=test_tenant.id)
        assert count == 2

    def test_get_concept_types(self, db_session, test_tenant, concept_crud):
        """Get distinct concept types."""
        concept_crud.get_or_create(
            db_session, name="A", concept_type="FEATURE", tenant_id=test_tenant.id
        )
        concept_crud.get_or_create(
            db_session, name="B", concept_type="TECHNOLOGY", tenant_id=test_tenant.id
        )
        types = concept_crud.get_concept_types(db_session, tenant_id=test_tenant.id)
        assert "FEATURE" in types
        assert "TECHNOLOGY" in types

    def test_tenant_isolation(self, db_session, concept_crud):
        """Concepts from one tenant are invisible to another."""
        from app.models.tenant import Tenant

        t1 = Tenant(name="Tenant A", subdomain="a", status="active", tier="professional",
                     billing_type="prepaid", max_users=5, max_documents=50, settings={})
        t2 = Tenant(name="Tenant B", subdomain="b", status="active", tier="professional",
                     billing_type="prepaid", max_users=5, max_documents=50, settings={})
        db_session.add_all([t1, t2])
        db_session.commit()

        concept_crud.get_or_create(
            db_session, name="Secret Feature", concept_type="FEATURE",
            tenant_id=t1.id
        )
        results = concept_crud.search_by_name(
            db_session, query="Secret", tenant_id=t2.id
        )
        assert len(results) == 0

    def test_tenant_id_required(self, db_session, concept_crud):
        """Operations without tenant_id raise ValueError."""
        with pytest.raises(ValueError, match="tenant_id is REQUIRED"):
            concept_crud.get_or_create(
                db_session, name="X", concept_type="FEATURE", tenant_id=None
            )

        with pytest.raises(ValueError, match="tenant_id is REQUIRED"):
            concept_crud.search_by_name(db_session, query="X", tenant_id=None)


# ============================================================
# RELATIONSHIP CRUD TESTS
# ============================================================

class TestOntologyRelationshipCRUD:

    def test_create_relationship(self, db_session, test_tenant, concept_crud, rel_crud):
        """Create a relationship between two concepts."""
        c1 = concept_crud.get_or_create(
            db_session, name="Login Feature", concept_type="FEATURE",
            tenant_id=test_tenant.id
        )
        c2 = concept_crud.get_or_create(
            db_session, name="JWT Library", concept_type="TECHNOLOGY",
            tenant_id=test_tenant.id
        )

        rel = rel_crud.create_if_not_exists(
            db_session,
            source_concept_id=c1.id,
            target_concept_id=c2.id,
            relationship_type="uses",
            tenant_id=test_tenant.id,
            confidence_score=0.85,
        )
        assert rel.id is not None
        assert rel.relationship_type == "uses"
        assert rel.source_concept_id == c1.id
        assert rel.target_concept_id == c2.id

    def test_create_if_not_exists_idempotent(self, db_session, test_tenant, concept_crud, rel_crud):
        """Creating the same relationship twice returns the same record."""
        c1 = concept_crud.get_or_create(
            db_session, name="A", concept_type="FEATURE", tenant_id=test_tenant.id
        )
        c2 = concept_crud.get_or_create(
            db_session, name="B", concept_type="SYSTEM", tenant_id=test_tenant.id
        )

        r1 = rel_crud.create_if_not_exists(
            db_session, source_concept_id=c1.id, target_concept_id=c2.id,
            relationship_type="implements", tenant_id=test_tenant.id
        )
        r2 = rel_crud.create_if_not_exists(
            db_session, source_concept_id=c1.id, target_concept_id=c2.id,
            relationship_type="implements", tenant_id=test_tenant.id
        )
        assert r1.id == r2.id

    def test_get_by_concept(self, db_session, test_tenant, concept_crud, rel_crud):
        """Get all relationships involving a concept."""
        c1 = concept_crud.get_or_create(
            db_session, name="Hub", concept_type="SYSTEM", tenant_id=test_tenant.id
        )
        c2 = concept_crud.get_or_create(
            db_session, name="Spoke1", concept_type="FEATURE", tenant_id=test_tenant.id
        )
        c3 = concept_crud.get_or_create(
            db_session, name="Spoke2", concept_type="FEATURE", tenant_id=test_tenant.id
        )

        rel_crud.create_if_not_exists(
            db_session, source_concept_id=c1.id, target_concept_id=c2.id,
            relationship_type="depends_on", tenant_id=test_tenant.id
        )
        rel_crud.create_if_not_exists(
            db_session, source_concept_id=c3.id, target_concept_id=c1.id,
            relationship_type="uses", tenant_id=test_tenant.id
        )

        rels = rel_crud.get_by_concept(
            db_session, concept_id=c1.id, tenant_id=test_tenant.id
        )
        assert len(rels) == 2  # c1 is source in one, target in another

    def test_get_full_graph(self, db_session, test_tenant, concept_crud, rel_crud):
        """Get the full graph returns all relationships for a tenant."""
        c1 = concept_crud.get_or_create(
            db_session, name="X", concept_type="FEATURE", tenant_id=test_tenant.id
        )
        c2 = concept_crud.get_or_create(
            db_session, name="Y", concept_type="SYSTEM", tenant_id=test_tenant.id
        )
        rel_crud.create_if_not_exists(
            db_session, source_concept_id=c1.id, target_concept_id=c2.id,
            relationship_type="implements", tenant_id=test_tenant.id
        )

        graph = rel_crud.get_full_graph(db_session, tenant_id=test_tenant.id)
        assert len(graph) >= 1

    def test_delete_by_concept(self, db_session, test_tenant, concept_crud, rel_crud):
        """Deleting relationships by concept removes all edges."""
        c1 = concept_crud.get_or_create(
            db_session, name="D1", concept_type="FEATURE", tenant_id=test_tenant.id
        )
        c2 = concept_crud.get_or_create(
            db_session, name="D2", concept_type="SYSTEM", tenant_id=test_tenant.id
        )
        rel_crud.create_if_not_exists(
            db_session, source_concept_id=c1.id, target_concept_id=c2.id,
            relationship_type="uses", tenant_id=test_tenant.id
        )

        deleted = rel_crud.delete_by_concept(
            db_session, concept_id=c1.id, tenant_id=test_tenant.id
        )
        assert deleted >= 1

        remaining = rel_crud.get_by_concept(
            db_session, concept_id=c1.id, tenant_id=test_tenant.id
        )
        assert len(remaining) == 0

    def test_count_by_tenant(self, db_session, test_tenant, concept_crud, rel_crud):
        """Count relationships for a tenant."""
        c1 = concept_crud.get_or_create(
            db_session, name="C1", concept_type="FEATURE", tenant_id=test_tenant.id
        )
        c2 = concept_crud.get_or_create(
            db_session, name="C2", concept_type="SYSTEM", tenant_id=test_tenant.id
        )
        rel_crud.create_if_not_exists(
            db_session, source_concept_id=c1.id, target_concept_id=c2.id,
            relationship_type="implements", tenant_id=test_tenant.id
        )
        count = rel_crud.count_by_tenant(db_session, tenant_id=test_tenant.id)
        assert count >= 1
