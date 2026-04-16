"""
BOEContext — Business Ontology Engine Shared Context Object
P4-02: Phase 4 BOE-Aware Validation Engine

Purpose
-------
BOEContext is an immutable, per-document snapshot of all CONFIRMED concept
mappings built from the tenant's ontology graph. The validation engine loads
it once per document at the start of a scan, then uses it to skip Gemini calls
for atoms whose concepts are already confirmed as matching in the BOE.

This is the core cost-reduction mechanism:
  - "confirmed" mappings (confidence >= AUTO_APPROVE_THRESHOLD) skip Gemini → 0 AI cost
  - "document_only" concepts are auto-flagged as MISSING_IMPLEMENTATION gaps
  - Validation results feed back to calibrate confidence scores (P4-05/P4-06)

O(1) Lookup
-----------
`_mapping_index` is a lowercased dict keyed by concept name fragments.
`is_auto_approved(concept_name)` checks in O(1) whether a concept can be
skipped without calling Gemini.

Usage
-----
    ctx = BOEContext.build(db=db, document_id=doc.id,
                           component_id=link.code_component_id,
                           tenant_id=tenant_id)
    if ctx.is_auto_approved("user authentication"):
        # skip this atom — BOE already confirmed it matches
        pass
"""

import time
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.logging import logger as _logger


@dataclass
class BOEContext:
    """
    Immutable snapshot of confirmed concept mappings for a single
    (document_id, component_id) validation pair.

    Fields
    ------
    tenant_id             Tenant the context belongs to
    document_id           BRD/SRS document being validated
    component_id          Code component being validated against
    confirmed_mappings    List of raw mapping dicts: {mapping_id, doc_concept,
                          code_concept, confidence, relationship_type}
    document_only_concepts  Concept names in document graph with NO code mapping
                            (auto-become MISSING_IMPLEMENTATION mismatches)
    code_only_concepts    Concept names in code graph with NO document mapping
                          (reverse-pass gaps — code built without BRD backing)
    built_at              Unix timestamp when context was built
    cache_key             SHA-256 of (tenant_id, document_id, component_id) for
                          external caching if needed
    AUTO_APPROVE_THRESHOLD  Mappings with confidence >= this skip Gemini
    """

    tenant_id: int
    document_id: int
    component_id: int
    confirmed_mappings: List[Dict] = field(default_factory=list)
    document_only_concepts: List[str] = field(default_factory=list)
    code_only_concepts: List[str] = field(default_factory=list)

    # Internal O(1) lookup structures — not shown in repr
    _auto_approved_set: set = field(default_factory=set, repr=False)
    _mapping_index: Dict[str, Dict] = field(default_factory=dict, repr=False)

    built_at: float = field(default_factory=time.time)
    cache_key: str = ""

    # Confidence threshold above which we skip Gemini for this concept
    AUTO_APPROVE_THRESHOLD: float = 0.92

    # ──────────────────────────────────────────────────────────────────────────
    # Class-level factory
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def build(
        cls,
        db: Session,
        document_id: int,
        component_id: int,
        tenant_id: int,
    ) -> "BOEContext":
        """
        Build a BOEContext from the DB for one (document, component, tenant) triple.

        Steps:
          1. Load all CONFIRMED concept mappings for this tenant
          2. Separate into "document" vs "code" concept sets
          3. Build _auto_approved_set (concepts with confidence >= threshold)
          4. Build _mapping_index for O(1) lookup by concept name fragment
          5. Collect document_only / code_only gap lists

        Returns a fully initialised BOEContext (never raises — returns empty
        context on any DB error so validation always proceeds).
        """
        cache_key = hashlib.sha256(
            f"{tenant_id}:{document_id}:{component_id}".encode()
        ).hexdigest()[:16]

        try:
            from app.models.concept_mapping import ConceptMapping
            from app.models.ontology_concept import OntologyConcept

            # Step 1: Load all confirmed mappings for this tenant
            confirmed_rows = (
                db.query(ConceptMapping)
                .filter(
                    ConceptMapping.tenant_id == tenant_id,
                    ConceptMapping.status == "confirmed",
                )
                .all()
            )

            confirmed_mappings: List[Dict] = []
            auto_approved_set: set = set()
            mapping_index: Dict[str, Dict] = {}

            for cm in confirmed_rows:
                # Eagerly load concept names (may need explicit joins if not lazy-loaded)
                doc_concept_name = ""
                code_concept_name = ""

                try:
                    doc_concept_name = (cm.document_concept.name or "").lower().strip()
                    code_concept_name = (cm.code_concept.name or "").lower().strip()
                except Exception:
                    # If relationship not loaded, skip this mapping
                    continue

                mapping_dict = {
                    "mapping_id": cm.id,
                    "doc_concept": doc_concept_name,
                    "code_concept": code_concept_name,
                    "confidence": cm.confidence_score,
                    "relationship_type": cm.relationship_type,
                    "mapping_method": cm.mapping_method,
                }
                confirmed_mappings.append(mapping_dict)

                # Build O(1) index by both concept names
                mapping_index[doc_concept_name] = mapping_dict
                mapping_index[code_concept_name] = mapping_dict

                # Index word tokens for partial match lookup
                for token in doc_concept_name.split():
                    if len(token) > 3:  # skip stop-words
                        mapping_index.setdefault(token, mapping_dict)
                for token in code_concept_name.split():
                    if len(token) > 3:
                        mapping_index.setdefault(token, mapping_dict)

                # Auto-approve if confidence is above threshold
                if cm.confidence_score >= cls.AUTO_APPROVE_THRESHOLD:
                    auto_approved_set.add(doc_concept_name)
                    auto_approved_set.add(code_concept_name)

            # Step 2: Document-only gaps (concept exists in doc graph but has no code mapping)
            try:
                from app.crud.crud_concept_mapping import concept_mapping as cm_crud
                unmapped_doc = cm_crud.get_unmapped_document_concepts(
                    db=db, tenant_id=tenant_id
                )
                document_only = [c.name for c in unmapped_doc if c.is_active][:50]  # cap at 50
            except Exception:
                document_only = []

            # Step 3: Code-only gaps
            try:
                unmapped_code = cm_crud.get_unmapped_code_concepts(
                    db=db, tenant_id=tenant_id
                )
                code_only = [c.name for c in unmapped_code if c.is_active][:50]
            except Exception:
                code_only = []

            ctx = cls(
                tenant_id=tenant_id,
                document_id=document_id,
                component_id=component_id,
                confirmed_mappings=confirmed_mappings,
                document_only_concepts=document_only,
                code_only_concepts=code_only,
                cache_key=cache_key,
            )
            # Inject internal structures (dataclass won't accept them in __init__ cleanly)
            object.__setattr__(ctx, "_auto_approved_set", auto_approved_set)
            object.__setattr__(ctx, "_mapping_index", mapping_index)

            _logger.info(
                f"[BOEContext] Built for tenant={tenant_id} doc={document_id} "
                f"component={component_id}: {len(confirmed_mappings)} confirmed mappings, "
                f"{len(auto_approved_set)} auto-approvable, "
                f"{len(document_only)} doc-only gaps, {len(code_only)} code-only gaps"
            )
            return ctx

        except Exception as e:
            _logger.warning(
                f"[BOEContext] Build failed for tenant={tenant_id} doc={document_id} "
                f"— returning empty context (validation continues normally). Error: {e}"
            )
            # Return empty context — validation always proceeds even without BOE
            return cls(
                tenant_id=tenant_id,
                document_id=document_id,
                component_id=component_id,
                cache_key=cache_key,
            )

    # ──────────────────────────────────────────────────────────────────────────
    # GAP-P4-07: Confidence decay on atom change
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def apply_staleness_decay(
        cls,
        db: Session,
        tenant_id: int,
        affected_concept_names: List[str],
        decay_factor: float = 0.70,
    ) -> int:
        """
        GAP-P4-07: Downgrade ConceptMapping.confidence_score by decay_factor
        (default 30% reduction) for all confirmed mappings whose concept name
        matches any of the affected names.

        Called by AtomDiffService after detecting MODIFIED or DELETED atoms
        so that stale high-confidence mappings are forced back through Gemini.

        Args:
            db                   SQLAlchemy session
            tenant_id            Tenant scope
            affected_concept_names  Concept names extracted from modified/deleted atoms
            decay_factor         Multiplier applied to current score (0.70 = 30% drop)

        Returns:
            Number of ConceptMapping rows updated.
        """
        if not affected_concept_names:
            return 0
        try:
            from app.models.concept_mapping import ConceptMapping
            from app.models.concept import Concept
            from sqlalchemy import text as sa_text

            # Normalise names for case-insensitive matching
            names_lower = {n.lower().strip() for n in affected_concept_names if n}

            # Load mappings whose document or code concept name overlaps
            mappings = (
                db.query(ConceptMapping)
                .join(Concept, ConceptMapping.document_concept_id == Concept.id)
                .filter(
                    ConceptMapping.tenant_id == tenant_id,
                    ConceptMapping.confidence_score >= cls.AUTO_APPROVE_THRESHOLD,
                )
                .all()
            )

            decayed = 0
            for cm in mappings:
                try:
                    doc_name = (cm.document_concept.name or "").lower().strip()
                    code_name = (cm.code_concept.name or "").lower().strip()
                    if doc_name in names_lower or code_name in names_lower:
                        old_score = cm.confidence_score
                        cm.confidence_score = round(old_score * decay_factor, 4)
                        decayed += 1
                        _logger.info(
                            f"[GAP-P4-07] Decayed mapping {cm.id} "
                            f"({doc_name!r}↔{code_name!r}): "
                            f"{old_score:.3f} → {cm.confidence_score:.3f}"
                        )
                except Exception:
                    continue

            if decayed:
                db.commit()
            _logger.info(
                f"[GAP-P4-07] Staleness decay applied: {decayed} mappings "
                f"downgraded for tenant {tenant_id}"
            )
            return decayed
        except Exception as e:
            _logger.warning(f"[GAP-P4-07] Staleness decay failed (non-fatal): {e}")
            return 0

    # ──────────────────────────────────────────────────────────────────────────
    # O(1) lookup methods
    # ──────────────────────────────────────────────────────────────────────────

    def is_auto_approved(self, concept_name: str) -> bool:
        """
        Return True if this concept has a confirmed mapping with confidence
        >= AUTO_APPROVE_THRESHOLD — meaning we can skip Gemini for this atom.

        Checks full concept name AND individual tokens (partial match).
        """
        name_lower = (concept_name or "").lower().strip()
        if not name_lower:
            return False

        # Direct match
        if name_lower in self._auto_approved_set:
            return True

        # Token-level match — any significant word in the concept hits the set
        tokens = [t for t in name_lower.split() if len(t) > 4]
        if tokens and all(t in self._auto_approved_set for t in tokens[:3]):
            return True

        return False

    def get_mapping_for_concept(self, concept_name: str) -> Optional[Dict]:
        """
        O(1) lookup of the confirmed mapping dict for a concept name.
        Returns None if not found.
        """
        name_lower = (concept_name or "").lower().strip()
        return self._mapping_index.get(name_lower)

    # ──────────────────────────────────────────────────────────────────────────
    # Computed properties
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def coverage_pct(self) -> float:
        """
        Percentage of confirmed mappings that are above the auto-approve threshold.
        Indicates overall BOE readiness for cost-free validation.
        """
        if not self.confirmed_mappings:
            return 0.0
        high_conf = sum(
            1 for m in self.confirmed_mappings
            if m["confidence"] >= self.AUTO_APPROVE_THRESHOLD
        )
        return round(high_conf / len(self.confirmed_mappings) * 100, 1)

    @property
    def auto_approved_count(self) -> int:
        """Number of unique concept names that can be auto-approved."""
        return len(self._auto_approved_set)

    @property
    def is_empty(self) -> bool:
        """True if this context has no confirmed mappings — BOE not yet populated."""
        return len(self.confirmed_mappings) == 0

    def __repr__(self) -> str:
        return (
            f"BOEContext(tenant={self.tenant_id}, doc={self.document_id}, "
            f"component={self.component_id}, mappings={len(self.confirmed_mappings)}, "
            f"auto_approved={self.auto_approved_count}, "
            f"doc_gaps={len(self.document_only_concepts)}, "
            f"coverage={self.coverage_pct}%)"
        )
