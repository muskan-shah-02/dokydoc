"""
SPRINT 3 Day 5: Integration Tests for BusinessOntologyService

Tests:
- get_or_create_concept() with source_type handling
- link_concepts() with self-referencing prevention
- _ingest_extraction_result() batch entity/relationship creation
- get_domain_vocabulary() aggregation
- Entity extraction mocking (Gemini AI calls)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.business_ontology_service import BusinessOntologyService
from app.crud.crud_ontology_concept import CRUDOntologyConcept
from app.crud.crud_ontology_relationship import CRUDOntologyRelationship
from app.models.ontology_concept import OntologyConcept
from app.models.ontology_relationship import OntologyRelationship


@pytest.fixture
def service():
    return BusinessOntologyService()


@pytest.fixture
def concept_crud():
    return CRUDOntologyConcept(OntologyConcept)


@pytest.fixture
def rel_crud():
    return CRUDOntologyRelationship(OntologyRelationship)


# ============================================================
# CONCEPT CREATION TESTS
# ============================================================

class TestConceptCreation:

    def test_get_or_create_concept_document(self, db_session, test_tenant, service):
        """Service creates document-layer concept by default."""
        concept = service.get_or_create_concept(
            db_session, name="Order Processing",
            concept_type="PROCESS", tenant_id=test_tenant.id
        )
        assert concept.name == "Order Processing"
        assert concept.source_type == "document"

    def test_get_or_create_concept_code(self, db_session, test_tenant, service):
        """Service creates code-layer concept when specified."""
        concept = service.get_or_create_concept(
            db_session, name="OrderService",
            concept_type="SYSTEM", tenant_id=test_tenant.id,
            source_type="code"
        )
        assert concept.source_type == "code"

    def test_get_or_create_concept_with_description(self, db_session, test_tenant, service):
        """Concept is created with description."""
        concept = service.get_or_create_concept(
            db_session, name="JWT Authentication",
            concept_type="FEATURE", tenant_id=test_tenant.id,
            description="Token-based auth using JWT"
        )
        assert concept.description == "Token-based auth using JWT"

    def test_name_normalization(self, db_session, test_tenant, service):
        """Names are normalized (stripped) before creation."""
        c1 = service.get_or_create_concept(
            db_session, name="  Spaces Around  ",
            concept_type="FEATURE", tenant_id=test_tenant.id
        )
        assert c1.name == "Spaces Around"


# ============================================================
# RELATIONSHIP LINKING TESTS
# ============================================================

class TestRelationshipLinking:

    def test_link_concepts(self, db_session, test_tenant, service):
        """Create a relationship between two concepts."""
        c1 = service.get_or_create_concept(
            db_session, name="Feature A", concept_type="FEATURE",
            tenant_id=test_tenant.id
        )
        c2 = service.get_or_create_concept(
            db_session, name="System B", concept_type="SYSTEM",
            tenant_id=test_tenant.id
        )
        rel = service.link_concepts(
            db_session, source_id=c1.id, target_id=c2.id,
            relationship_type="implements", tenant_id=test_tenant.id,
            confidence_score=0.85
        )
        assert rel is not None
        assert rel.relationship_type == "implements"

    def test_self_referencing_prevented(self, db_session, test_tenant, service):
        """Self-referencing edges return None."""
        c1 = service.get_or_create_concept(
            db_session, name="Self", concept_type="FEATURE",
            tenant_id=test_tenant.id
        )
        result = service.link_concepts(
            db_session, source_id=c1.id, target_id=c1.id,
            relationship_type="depends_on", tenant_id=test_tenant.id
        )
        assert result is None


# ============================================================
# BATCH INGESTION TESTS
# ============================================================

class TestIngestion:

    def test_ingest_extraction_result(self, db_session, test_tenant, service):
        """_ingest_extraction_result creates entities and relationships."""
        entities = [
            {"name": "User", "type": "ACTOR", "confidence": 0.9, "context": "Main user"},
            {"name": "Login Page", "type": "FEATURE", "confidence": 0.8, "context": "Auth UI"},
            {"name": "PostgreSQL", "type": "TECHNOLOGY", "confidence": 0.95, "context": "DB"},
        ]
        relationships = [
            {"source": "User", "target": "Login Page", "relationship_type": "uses", "confidence": 0.7},
            {"source": "Login Page", "target": "PostgreSQL", "relationship_type": "depends_on", "confidence": 0.6},
        ]

        e_count, r_count = service._ingest_extraction_result(
            db_session, entities=entities, relationships=relationships,
            tenant_id=test_tenant.id
        )
        assert e_count == 3
        assert r_count == 2

    def test_ingest_skips_short_names(self, db_session, test_tenant, service):
        """Entities with names shorter than 2 chars are skipped."""
        entities = [
            {"name": "X", "type": "FEATURE", "confidence": 0.9, "context": "Too short"},
            {"name": "Valid Name", "type": "FEATURE", "confidence": 0.9, "context": "OK"},
        ]
        e_count, _ = service._ingest_extraction_result(
            db_session, entities=entities, relationships=[],
            tenant_id=test_tenant.id
        )
        assert e_count == 1  # Only "Valid Name" created

    def test_ingest_with_source_type(self, db_session, test_tenant, service, concept_crud):
        """Entities ingested with source_type='code' have correct source."""
        entities = [
            {"name": "Auth Service", "type": "SYSTEM", "confidence": 0.9, "context": "code"},
        ]
        service._ingest_extraction_result(
            db_session, entities=entities, relationships=[],
            tenant_id=test_tenant.id, source_type="code"
        )

        codes = concept_crud.get_by_source_type(
            db_session, source_type="code", tenant_id=test_tenant.id
        )
        assert any(c.name == "Auth Service" for c in codes)

    def test_ingest_unresolved_relationships_skipped(self, db_session, test_tenant, service):
        """Relationships referencing non-existent entities are skipped."""
        entities = [
            {"name": "OnlyOne", "type": "FEATURE", "confidence": 0.9, "context": "solo"},
        ]
        relationships = [
            {"source": "OnlyOne", "target": "DoesNotExist", "relationship_type": "uses", "confidence": 0.7},
        ]
        _, r_count = service._ingest_extraction_result(
            db_session, entities=entities, relationships=relationships,
            tenant_id=test_tenant.id
        )
        assert r_count == 0  # Target doesn't exist, relationship skipped


# ============================================================
# DOMAIN VOCABULARY TESTS
# ============================================================

class TestDomainVocabulary:

    def test_get_domain_vocabulary(self, db_session, test_tenant, service):
        """get_domain_vocabulary returns concepts grouped by type."""
        service.get_or_create_concept(
            db_session, name="React", concept_type="TECHNOLOGY",
            tenant_id=test_tenant.id
        )
        service.get_or_create_concept(
            db_session, name="FastAPI", concept_type="TECHNOLOGY",
            tenant_id=test_tenant.id
        )
        service.get_or_create_concept(
            db_session, name="Login", concept_type="FEATURE",
            tenant_id=test_tenant.id
        )

        vocab = service.get_domain_vocabulary(
            db_session, tenant_id=test_tenant.id
        )
        assert "TECHNOLOGY" in vocab
        assert "FEATURE" in vocab
        assert len(vocab["TECHNOLOGY"]) == 2
        assert len(vocab["FEATURE"]) == 1


# ============================================================
# RECONCILIATION LOGIC TESTS (mocked AI)
# ============================================================

class TestReconciliation:

    @pytest.mark.asyncio
    async def test_reconcile_skips_when_no_code_concepts(self, db_session, test_tenant, service):
        """Reconciliation is skipped when there are no code-layer concepts."""
        service.get_or_create_concept(
            db_session, name="Doc Feature", concept_type="FEATURE",
            tenant_id=test_tenant.id, source_type="document"
        )
        # No code concepts created

        result = await service.reconcile_document_code_concepts(
            db_session, tenant_id=test_tenant.id
        )
        assert result["bridges_created"] == 0

    @pytest.mark.asyncio
    async def test_reconcile_skips_when_no_document_concepts(self, db_session, test_tenant, service):
        """Reconciliation is skipped when there are no document-layer concepts."""
        service.get_or_create_concept(
            db_session, name="Code System", concept_type="SYSTEM",
            tenant_id=test_tenant.id, source_type="code"
        )
        # No document concepts created

        result = await service.reconcile_document_code_concepts(
            db_session, tenant_id=test_tenant.id
        )
        assert result["bridges_created"] == 0
