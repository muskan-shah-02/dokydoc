"""
Integration Tests — ConceptMapping CRUD Operations

Tests the cross-graph mapping CRUD that links document concepts to code concepts.
Covers: create (idempotent), query methods, confirm/reject flow, gap/undocumented detection.
"""
import pytest
from app import crud
from app.models.ontology_concept import OntologyConcept
from app.models.concept_mapping import ConceptMapping


@pytest.fixture
def doc_concept(db_session, test_tenant):
    """Create a document-layer concept."""
    return crud.ontology_concept.get_or_create(
        db=db_session,
        name="User Authentication",
        concept_type="FEATURE",
        tenant_id=test_tenant.id,
        source_type="document",
        description="Login system per BRD section 3.1",
    )


@pytest.fixture
def code_concept(db_session, test_tenant):
    """Create a code-layer concept."""
    return crud.ontology_concept.get_or_create(
        db=db_session,
        name="User Authentication",
        concept_type="SYSTEM",
        tenant_id=test_tenant.id,
        source_type="code",
        description="auth_service.py login handler",
    )


@pytest.fixture
def extra_doc_concept(db_session, test_tenant):
    """A document concept with no code counterpart (gap)."""
    return crud.ontology_concept.get_or_create(
        db=db_session,
        name="Password Reset Flow",
        concept_type="PROCESS",
        tenant_id=test_tenant.id,
        source_type="document",
        description="Reset password via email",
    )


@pytest.fixture
def extra_code_concept(db_session, test_tenant):
    """A code concept with no document counterpart (undocumented)."""
    return crud.ontology_concept.get_or_create(
        db=db_session,
        name="Rate Limiter Middleware",
        concept_type="SYSTEM",
        tenant_id=test_tenant.id,
        source_type="code",
        description="rate_limiter.py middleware",
    )


class TestCreateMapping:
    def test_create_basic_mapping(self, db_session, test_tenant, doc_concept, code_concept):
        mapping = crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="exact",
            confidence_score=1.0,
            tenant_id=test_tenant.id,
        )
        assert mapping.id is not None
        assert mapping.mapping_method == "exact"
        assert mapping.confidence_score == 1.0
        assert mapping.status == "candidate"
        assert mapping.relationship_type == "implements"

    def test_create_mapping_idempotent(self, db_session, test_tenant, doc_concept, code_concept):
        """Same doc+code pair returns existing mapping."""
        m1 = crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="exact",
            confidence_score=0.8,
            tenant_id=test_tenant.id,
        )
        m2 = crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="fuzzy",
            confidence_score=0.6,
            tenant_id=test_tenant.id,
        )
        assert m1.id == m2.id
        # Confidence NOT updated since new is lower
        assert m2.confidence_score == 0.8

    def test_create_mapping_updates_higher_confidence(self, db_session, test_tenant, doc_concept, code_concept):
        """Idempotent create updates when new confidence is higher."""
        m1 = crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="fuzzy",
            confidence_score=0.6,
            tenant_id=test_tenant.id,
        )
        m2 = crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="exact",
            confidence_score=1.0,
            tenant_id=test_tenant.id,
        )
        assert m1.id == m2.id
        assert m2.confidence_score == 1.0
        assert m2.mapping_method == "exact"

    def test_create_mapping_requires_tenant(self, db_session, doc_concept, code_concept):
        with pytest.raises(ValueError, match="tenant_id is REQUIRED"):
            crud.concept_mapping.create_mapping(
                db=db_session,
                document_concept_id=doc_concept.id,
                code_concept_id=code_concept.id,
                mapping_method="exact",
                confidence_score=1.0,
                tenant_id=None,
            )


class TestQueryMethods:
    def test_get_by_document_concept(self, db_session, test_tenant, doc_concept, code_concept):
        crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="exact",
            confidence_score=1.0,
            tenant_id=test_tenant.id,
        )
        results = crud.concept_mapping.get_by_document_concept(
            db=db_session, document_concept_id=doc_concept.id, tenant_id=test_tenant.id,
        )
        assert len(results) == 1
        assert results[0].code_concept_id == code_concept.id

    def test_get_by_code_concept(self, db_session, test_tenant, doc_concept, code_concept):
        crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="exact",
            confidence_score=1.0,
            tenant_id=test_tenant.id,
        )
        results = crud.concept_mapping.get_by_code_concept(
            db=db_session, code_concept_id=code_concept.id, tenant_id=test_tenant.id,
        )
        assert len(results) == 1
        assert results[0].document_concept_id == doc_concept.id

    def test_get_by_status(self, db_session, test_tenant, doc_concept, code_concept):
        crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="exact",
            confidence_score=1.0,
            status="confirmed",
            tenant_id=test_tenant.id,
        )
        candidates = crud.concept_mapping.get_by_status(
            db=db_session, status="candidate", tenant_id=test_tenant.id,
        )
        confirmed = crud.concept_mapping.get_by_status(
            db=db_session, status="confirmed", tenant_id=test_tenant.id,
        )
        assert len(candidates) == 0
        assert len(confirmed) == 1

    def test_count_by_tenant(self, db_session, test_tenant, doc_concept, code_concept):
        assert crud.concept_mapping.count_by_tenant(db=db_session, tenant_id=test_tenant.id) == 0
        crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="exact",
            confidence_score=1.0,
            tenant_id=test_tenant.id,
        )
        assert crud.concept_mapping.count_by_tenant(db=db_session, tenant_id=test_tenant.id) == 1


class TestConfirmReject:
    def test_confirm_candidate(self, db_session, test_tenant, doc_concept, code_concept):
        mapping = crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="fuzzy",
            confidence_score=0.7,
            tenant_id=test_tenant.id,
        )
        assert mapping.status == "candidate"
        confirmed = crud.concept_mapping.confirm_mapping(
            db=db_session, mapping_id=mapping.id, tenant_id=test_tenant.id,
        )
        assert confirmed.status == "confirmed"

    def test_reject_candidate(self, db_session, test_tenant, doc_concept, code_concept):
        mapping = crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="fuzzy",
            confidence_score=0.4,
            tenant_id=test_tenant.id,
        )
        rejected = crud.concept_mapping.reject_mapping(
            db=db_session, mapping_id=mapping.id, tenant_id=test_tenant.id,
        )
        assert rejected.status == "rejected"


class TestGapDetection:
    def test_unmapped_document_concepts(
        self, db_session, test_tenant, doc_concept, code_concept, extra_doc_concept
    ):
        """extra_doc_concept has no mapping — it should appear as a gap."""
        crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="exact",
            confidence_score=1.0,
            tenant_id=test_tenant.id,
        )
        gaps = crud.concept_mapping.get_unmapped_document_concepts(
            db=db_session, tenant_id=test_tenant.id,
        )
        gap_names = [g.name for g in gaps]
        assert "Password Reset Flow" in gap_names
        assert "User Authentication" not in gap_names

    def test_unmapped_code_concepts(
        self, db_session, test_tenant, doc_concept, code_concept, extra_code_concept
    ):
        """extra_code_concept has no mapping — it should appear as undocumented."""
        crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="exact",
            confidence_score=1.0,
            tenant_id=test_tenant.id,
        )
        undocumented = crud.concept_mapping.get_unmapped_code_concepts(
            db=db_session, tenant_id=test_tenant.id,
        )
        undoc_names = [u.name for u in undocumented]
        assert "Rate Limiter Middleware" in undoc_names
        assert "User Authentication" not in undoc_names

    def test_contradictions(self, db_session, test_tenant, doc_concept, code_concept):
        crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="ai_validated",
            confidence_score=0.8,
            relationship_type="contradicts",
            ai_reasoning="Different auth mechanism: doc says OAuth, code uses JWT",
            tenant_id=test_tenant.id,
        )
        contradictions = crud.concept_mapping.get_contradictions(
            db=db_session, tenant_id=test_tenant.id,
        )
        assert len(contradictions) == 1
        assert contradictions[0].ai_reasoning == "Different auth mechanism: doc says OAuth, code uses JWT"


class TestTenantIsolation:
    def test_mappings_isolated_between_tenants(self, db_session, test_tenant, doc_concept, code_concept):
        """Mappings from one tenant should not be visible to another."""
        from app.models.tenant import Tenant

        tenant2 = Tenant(
            name="Other Corp", subdomain="other", status="active",
            tier="basic", billing_type="prepaid", max_users=5,
            max_documents=50, settings={},
        )
        db_session.add(tenant2)
        db_session.commit()
        db_session.refresh(tenant2)

        crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="exact",
            confidence_score=1.0,
            tenant_id=test_tenant.id,
        )

        count_t1 = crud.concept_mapping.count_by_tenant(db=db_session, tenant_id=test_tenant.id)
        count_t2 = crud.concept_mapping.count_by_tenant(db=db_session, tenant_id=tenant2.id)
        assert count_t1 == 1
        assert count_t2 == 0


class TestDeleteAll:
    def test_delete_all_for_tenant(self, db_session, test_tenant, doc_concept, code_concept):
        crud.concept_mapping.create_mapping(
            db=db_session,
            document_concept_id=doc_concept.id,
            code_concept_id=code_concept.id,
            mapping_method="exact",
            confidence_score=1.0,
            tenant_id=test_tenant.id,
        )
        assert crud.concept_mapping.count_by_tenant(db=db_session, tenant_id=test_tenant.id) == 1
        deleted = crud.concept_mapping.delete_all_for_tenant(
            db=db_session, tenant_id=test_tenant.id,
        )
        assert deleted == 1
        assert crud.concept_mapping.count_by_tenant(db=db_session, tenant_id=test_tenant.id) == 0
