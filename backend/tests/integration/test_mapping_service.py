"""
Integration Tests — MappingService (3-Tier Algorithmic Mapping)

Tests the cost-optimized cross-graph mapping service:
  - Tier 1: Exact match (FREE)
  - Tier 2: Fuzzy match via token overlap + Levenshtein (FREE)
  - Tier 3: AI validation (not tested here — requires Gemini)
  - Mismatch detection (gaps, undocumented, contradictions)

AI Tier 3 is tested separately or in E2E tests.
"""
import pytest
from app import crud
from app.services.mapping_service import (
    MappingService,
    _normalize,
    _tokenize,
    _levenshtein_distance,
    _levenshtein_similarity,
)


# ============================================================
# Helper Function Tests
# ============================================================

class TestNormalize:
    def test_basic(self):
        assert _normalize("User Authentication") == "user authentication"

    def test_underscores(self):
        assert _normalize("user_authentication") == "user authentication"

    def test_hyphens_dots(self):
        assert _normalize("user-auth.service") == "user auth service"

    def test_extra_whitespace(self):
        assert _normalize("  user   auth  ") == "user auth"


class TestTokenize:
    def test_splits_words(self):
        tokens = _tokenize("User Authentication Service")
        assert tokens == {"user", "authentication", "service"}

    def test_ignores_single_chars(self):
        tokens = _tokenize("a b cd ef")
        assert tokens == {"cd", "ef"}

    def test_handles_underscores(self):
        tokens = _tokenize("user_auth_service")
        assert tokens == {"user", "auth", "service"}


class TestLevenshtein:
    def test_identical(self):
        assert _levenshtein_distance("abc", "abc") == 0

    def test_one_edit(self):
        assert _levenshtein_distance("abc", "ab") == 1

    def test_two_edits(self):
        assert _levenshtein_distance("kitten", "sitting") == 3

    def test_similarity_identical(self):
        assert _levenshtein_similarity("abc", "abc") == 1.0

    def test_similarity_partial(self):
        sim = _levenshtein_similarity("user auth", "user authentication")
        assert 0.4 < sim < 0.8

    def test_similarity_empty(self):
        assert _levenshtein_similarity("", "") == 1.0


# ============================================================
# Tier 1: Exact Match Tests
# ============================================================

class TestTier1ExactMatch:
    def test_exact_name_match_creates_confirmed_mapping(self, db_session, test_tenant):
        """When doc and code concepts have the same normalized name, auto-confirm."""
        crud.ontology_concept.get_or_create(
            db=db_session, name="Payment Gateway",
            concept_type="FEATURE", tenant_id=test_tenant.id, source_type="document",
        )
        crud.ontology_concept.get_or_create(
            db=db_session, name="Payment Gateway",
            concept_type="SYSTEM", tenant_id=test_tenant.id, source_type="code",
        )

        svc = MappingService()
        result = svc.run_full_mapping(db=db_session, tenant_id=test_tenant.id, use_ai_fallback=False)

        assert result["exact_matches"] == 1
        assert result["fuzzy_matches"] == 0
        assert result["total_mappings"] == 1

        confirmed = crud.concept_mapping.get_confirmed(db=db_session, tenant_id=test_tenant.id)
        assert len(confirmed) == 1
        assert confirmed[0].mapping_method == "exact"
        assert confirmed[0].confidence_score == 1.0

    def test_exact_match_promotes_to_both(self, db_session, test_tenant):
        """Exact matches should promote both concepts to source_type='both'."""
        doc = crud.ontology_concept.get_or_create(
            db=db_session, name="User Service",
            concept_type="FEATURE", tenant_id=test_tenant.id, source_type="document",
        )
        code = crud.ontology_concept.get_or_create(
            db=db_session, name="User Service",
            concept_type="SYSTEM", tenant_id=test_tenant.id, source_type="code",
        )

        svc = MappingService()
        svc.run_full_mapping(db=db_session, tenant_id=test_tenant.id, use_ai_fallback=False)

        db_session.refresh(doc)
        db_session.refresh(code)
        assert doc.source_type == "both"
        assert code.source_type == "both"

    def test_case_insensitive_exact(self, db_session, test_tenant):
        """Normalization should make 'user_auth' == 'User Auth'."""
        crud.ontology_concept.get_or_create(
            db=db_session, name="user_auth",
            concept_type="FEATURE", tenant_id=test_tenant.id, source_type="document",
        )
        crud.ontology_concept.get_or_create(
            db=db_session, name="User Auth",
            concept_type="SYSTEM", tenant_id=test_tenant.id, source_type="code",
        )

        svc = MappingService()
        result = svc.run_full_mapping(db=db_session, tenant_id=test_tenant.id, use_ai_fallback=False)
        assert result["exact_matches"] == 1


# ============================================================
# Tier 2: Fuzzy Match Tests
# ============================================================

class TestTier2FuzzyMatch:
    def test_high_overlap_creates_mapping(self, db_session, test_tenant):
        """Token overlap >= 50% should create a fuzzy mapping."""
        crud.ontology_concept.get_or_create(
            db=db_session, name="User Authentication Service",
            concept_type="FEATURE", tenant_id=test_tenant.id, source_type="document",
        )
        crud.ontology_concept.get_or_create(
            db=db_session, name="Authentication Service Handler",
            concept_type="SYSTEM", tenant_id=test_tenant.id, source_type="code",
        )

        svc = MappingService()
        result = svc.run_full_mapping(db=db_session, tenant_id=test_tenant.id, use_ai_fallback=False)

        assert result["fuzzy_matches"] >= 1
        assert result["total_mappings"] >= 1

    def test_no_match_for_unrelated(self, db_session, test_tenant):
        """Completely unrelated concepts should NOT be mapped."""
        crud.ontology_concept.get_or_create(
            db=db_session, name="Payment Processing Flow",
            concept_type="PROCESS", tenant_id=test_tenant.id, source_type="document",
        )
        crud.ontology_concept.get_or_create(
            db=db_session, name="Logging Middleware",
            concept_type="SYSTEM", tenant_id=test_tenant.id, source_type="code",
        )

        svc = MappingService()
        result = svc.run_full_mapping(db=db_session, tenant_id=test_tenant.id, use_ai_fallback=False)
        assert result["total_mappings"] == 0
        assert result["total_gaps"] == 1
        assert result["total_undocumented"] == 1


# ============================================================
# Mismatch Detection Tests
# ============================================================

class TestMismatchDetection:
    def test_gaps_detected(self, db_session, test_tenant):
        """Document concepts with no code mapping should be detected as gaps."""
        crud.ontology_concept.get_or_create(
            db=db_session, name="Feature A",
            concept_type="FEATURE", tenant_id=test_tenant.id, source_type="document",
        )
        crud.ontology_concept.get_or_create(
            db=db_session, name="Feature B",
            concept_type="FEATURE", tenant_id=test_tenant.id, source_type="document",
        )
        # Only one code concept
        crud.ontology_concept.get_or_create(
            db=db_session, name="Feature A",
            concept_type="SYSTEM", tenant_id=test_tenant.id, source_type="code",
        )

        svc = MappingService()
        svc.run_full_mapping(db=db_session, tenant_id=test_tenant.id, use_ai_fallback=False)

        mismatches = svc.get_mismatches(db=db_session, tenant_id=test_tenant.id)
        assert mismatches["total_gaps"] == 1
        gap_names = [g["name"] for g in mismatches["gaps"]]
        assert "Feature B" in gap_names

    def test_undocumented_detected(self, db_session, test_tenant):
        """Code concepts with no doc mapping should be undocumented."""
        crud.ontology_concept.get_or_create(
            db=db_session, name="Billing Service",
            concept_type="FEATURE", tenant_id=test_tenant.id, source_type="document",
        )
        crud.ontology_concept.get_or_create(
            db=db_session, name="Billing Service",
            concept_type="SYSTEM", tenant_id=test_tenant.id, source_type="code",
        )
        crud.ontology_concept.get_or_create(
            db=db_session, name="Internal Cache Layer",
            concept_type="SYSTEM", tenant_id=test_tenant.id, source_type="code",
        )

        svc = MappingService()
        svc.run_full_mapping(db=db_session, tenant_id=test_tenant.id, use_ai_fallback=False)

        mismatches = svc.get_mismatches(db=db_session, tenant_id=test_tenant.id)
        assert mismatches["total_undocumented"] == 1
        undoc_names = [u["name"] for u in mismatches["undocumented"]]
        assert "Internal Cache Layer" in undoc_names


# ============================================================
# Incremental Mapping Tests
# ============================================================

class TestIncrementalMapping:
    def test_incremental_maps_new_code_concept(self, db_session, test_tenant):
        """Adding a new code concept should incrementally map it to matching doc concept."""
        doc = crud.ontology_concept.get_or_create(
            db=db_session, name="Search Feature",
            concept_type="FEATURE", tenant_id=test_tenant.id, source_type="document",
        )
        code = crud.ontology_concept.get_or_create(
            db=db_session, name="Search Feature",
            concept_type="SYSTEM", tenant_id=test_tenant.id, source_type="code",
        )

        svc = MappingService()
        result = svc.run_incremental_mapping(
            db=db_session, concept_ids=[code.id], tenant_id=test_tenant.id,
        )
        assert result["new_mappings"] == 1


# ============================================================
# Edge Cases
# ============================================================

class TestEdgeCases:
    def test_empty_graphs(self, db_session, test_tenant):
        """No concepts at all should return zeros."""
        svc = MappingService()
        result = svc.run_full_mapping(db=db_session, tenant_id=test_tenant.id, use_ai_fallback=False)
        assert result["total_mappings"] == 0
        assert result["total_gaps"] == 0
        assert result["total_undocumented"] == 0

    def test_only_doc_concepts(self, db_session, test_tenant):
        """Only document concepts (no code) should skip mapping."""
        crud.ontology_concept.get_or_create(
            db=db_session, name="Feature X",
            concept_type="FEATURE", tenant_id=test_tenant.id, source_type="document",
        )
        svc = MappingService()
        result = svc.run_full_mapping(db=db_session, tenant_id=test_tenant.id, use_ai_fallback=False)
        assert result["total_mappings"] == 0

    def test_only_code_concepts(self, db_session, test_tenant):
        """Only code concepts (no doc) should skip mapping."""
        crud.ontology_concept.get_or_create(
            db=db_session, name="Service Y",
            concept_type="SYSTEM", tenant_id=test_tenant.id, source_type="code",
        )
        svc = MappingService()
        result = svc.run_full_mapping(db=db_session, tenant_id=test_tenant.id, use_ai_fallback=False)
        assert result["total_mappings"] == 0
