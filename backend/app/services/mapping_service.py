"""
MappingService — 3-Tier Algorithmic Cross-Graph Mapping

Replaces the expensive AI reconciliation pass with a cost-optimized
3-tier approach:

  Tier 1: EXACT match   — normalized name equality        — FREE ($0)
  Tier 2: FUZZY match   — token overlap + Levenshtein     — FREE ($0)
  Tier 3: AI validation — only ambiguous pairs from Tier 2 — ~$0.001/pair

Cost at scale (500 doc concepts × 500 code concepts):
  Old reconciliation: $2-5 per run (sends ALL concepts to AI)
  New 3-tier mapping:  $0.05 per run (AI for ~50 ambiguous pairs only)
  Savings: ~97%

Also provides mismatch detection via pure graph comparison (FREE):
  - Gaps: document concepts with no code mapping
  - Undocumented: code concepts with no document mapping
  - Contradictions: mappings with relationship_type == "contradicts"
"""

import re
import time
import json
import asyncio
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session

from app import crud
from app.models.ontology_concept import OntologyConcept
from app.core.logging import LoggerMixin


def _normalize(name: str) -> str:
    """Normalize a concept name for comparison: lowercase, strip, remove punctuation."""
    n = name.strip().lower()
    # Replace underscores, hyphens, dots with spaces
    n = re.sub(r'[_\-.]', ' ', n)
    # Remove extra whitespace
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def _tokenize(name: str) -> set:
    """Split a normalized name into tokens for overlap comparison."""
    normalized = _normalize(name)
    # Split on spaces and remove very short tokens (1 char)
    tokens = {t for t in normalized.split() if len(t) > 1}
    return tokens


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def _levenshtein_similarity(s1: str, s2: str) -> float:
    """Normalized Levenshtein similarity (0.0 to 1.0)."""
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return 1.0 - (_levenshtein_distance(s1, s2) / max_len)


class MappingService(LoggerMixin):
    """
    Cost-optimized cross-graph mapping between document and code concepts.
    """

    # Thresholds
    FUZZY_HIGH_CONFIDENCE = 0.50   # Token overlap >= 50% → high confidence
    FUZZY_MEDIUM_CONFIDENCE = 0.25  # Token overlap 25-50% → medium (needs AI)
    LEVENSHTEIN_THRESHOLD = 0.70   # Normalized string similarity >= 70% → candidate
    AI_VALIDATION_THRESHOLD = 0.25  # Only send to AI if fuzzy score is in ambiguous range

    def __init__(self):
        super().__init__()
        self.logger.info("MappingService initialized")

    def run_full_mapping(
        self, db: Session, *, tenant_id: int, use_ai_fallback: bool = True
    ) -> Dict:
        """
        Run the complete 3-tier mapping pipeline for a tenant.

        1. Fetch all document-layer and code-layer concepts
        2. Tier 1: Exact name matches
        3. Tier 2: Fuzzy matches (token overlap + Levenshtein)
        4. Tier 3: AI validation for ambiguous pairs (optional)
        5. Auto-confirm high-confidence matches
        6. Detect gaps and undocumented features

        Returns mapping run statistics.
        """
        self.logger.info(f"Starting 3-tier mapping for tenant {tenant_id}")

        doc_concepts = crud.ontology_concept.get_by_source_type(
            db=db, source_type="document", tenant_id=tenant_id, limit=1000
        )
        code_concepts = crud.ontology_concept.get_by_source_type(
            db=db, source_type="code", tenant_id=tenant_id, limit=1000
        )

        if not doc_concepts or not code_concepts:
            self.logger.info(
                f"Mapping skipped: {len(doc_concepts or [])} doc concepts, "
                f"{len(code_concepts or [])} code concepts — need both."
            )
            return {
                "exact_matches": 0, "fuzzy_matches": 0, "ai_validated": 0,
                "total_mappings": 0, "total_gaps": 0, "total_undocumented": 0,
                "ai_cost_inr": 0.0
            }

        exact_count = 0
        fuzzy_count = 0
        ai_count = 0
        ai_cost = 0.0

        # Track which concepts got mapped
        mapped_doc_ids = set()
        mapped_code_ids = set()

        # Build lookup for code concepts
        code_by_normalized = {}
        for cc in code_concepts:
            key = _normalize(cc.name)
            code_by_normalized.setdefault(key, []).append(cc)

        # ============================
        # TIER 1: EXACT MATCH (FREE)
        # ============================
        for dc in doc_concepts:
            dc_norm = _normalize(dc.name)
            if dc_norm in code_by_normalized:
                for cc in code_by_normalized[dc_norm]:
                    if cc.id in mapped_code_ids:
                        continue
                    crud.concept_mapping.create_mapping(
                        db=db,
                        document_concept_id=dc.id,
                        code_concept_id=cc.id,
                        mapping_method="exact",
                        confidence_score=1.0,
                        status="confirmed",  # Exact matches auto-confirm
                        relationship_type="implements",
                        tenant_id=tenant_id,
                    )
                    mapped_doc_ids.add(dc.id)
                    mapped_code_ids.add(cc.id)
                    exact_count += 1
                    # Promote both concepts to "both" since exact name match
                    crud.ontology_concept.promote_to_both(
                        db=db, concept_id=dc.id, tenant_id=tenant_id
                    )
                    crud.ontology_concept.promote_to_both(
                        db=db, concept_id=cc.id, tenant_id=tenant_id
                    )

        self.logger.info(f"Tier 1 (exact): {exact_count} matches")

        # ============================
        # TIER 2: FUZZY MATCH (FREE)
        # ============================
        unmapped_docs = [dc for dc in doc_concepts if dc.id not in mapped_doc_ids]
        unmapped_codes = [cc for cc in code_concepts if cc.id not in mapped_code_ids]
        ambiguous_pairs = []  # For Tier 3

        for dc in unmapped_docs:
            dc_tokens = _tokenize(dc.name)
            dc_norm = _normalize(dc.name)
            best_match = None
            best_score = 0.0

            for cc in unmapped_codes:
                if cc.id in mapped_code_ids:
                    continue

                cc_tokens = _tokenize(cc.name)
                cc_norm = _normalize(cc.name)

                # Token overlap score
                if dc_tokens and cc_tokens:
                    overlap = len(dc_tokens & cc_tokens)
                    union = len(dc_tokens | cc_tokens)
                    token_score = overlap / union if union > 0 else 0.0
                else:
                    token_score = 0.0

                # Levenshtein similarity
                lev_score = _levenshtein_similarity(dc_norm, cc_norm)

                # Combined score (weighted)
                combined = max(token_score, lev_score)

                if combined > best_score:
                    best_score = combined
                    best_match = cc

            if best_match and best_score >= self.FUZZY_HIGH_CONFIDENCE:
                # High confidence fuzzy — auto-create as candidate (will confirm if > 0.7)
                status = "confirmed" if best_score >= 0.70 else "candidate"
                crud.concept_mapping.create_mapping(
                    db=db,
                    document_concept_id=dc.id,
                    code_concept_id=best_match.id,
                    mapping_method="fuzzy",
                    confidence_score=round(best_score, 3),
                    status=status,
                    relationship_type="implements",
                    tenant_id=tenant_id,
                )
                mapped_doc_ids.add(dc.id)
                mapped_code_ids.add(best_match.id)
                fuzzy_count += 1

                if status == "confirmed" and best_score >= 0.80:
                    crud.ontology_concept.promote_to_both(
                        db=db, concept_id=dc.id, tenant_id=tenant_id
                    )
                    crud.ontology_concept.promote_to_both(
                        db=db, concept_id=best_match.id, tenant_id=tenant_id
                    )

            elif best_match and best_score >= self.FUZZY_MEDIUM_CONFIDENCE:
                # Ambiguous — queue for AI validation (Tier 3)
                ambiguous_pairs.append((dc, best_match, best_score))

        self.logger.info(
            f"Tier 2 (fuzzy): {fuzzy_count} matches, "
            f"{len(ambiguous_pairs)} ambiguous pairs queued for AI"
        )

        # ============================
        # TIER 3: AI VALIDATION (PAID — only for ambiguous pairs)
        # ============================
        ai_input_tokens = 0
        ai_output_tokens = 0
        if use_ai_fallback and ambiguous_pairs:
            ai_count, ai_cost, ai_input_tokens, ai_output_tokens = self._validate_ambiguous_pairs(
                db=db, pairs=ambiguous_pairs, tenant_id=tenant_id,
                mapped_doc_ids=mapped_doc_ids, mapped_code_ids=mapped_code_ids
            )

        # ============================
        # MISMATCH DETECTION (FREE)
        # ============================
        total_gaps = len([dc for dc in doc_concepts if dc.id not in mapped_doc_ids])
        total_undocumented = len([cc for cc in code_concepts if cc.id not in mapped_code_ids])

        total_mappings = exact_count + fuzzy_count + ai_count

        self.logger.info(
            f"Mapping complete for tenant {tenant_id}: "
            f"{exact_count} exact + {fuzzy_count} fuzzy + {ai_count} AI = "
            f"{total_mappings} total. "
            f"{total_gaps} gaps, {total_undocumented} undocumented. "
            f"AI cost: INR {ai_cost:.4f}"
        )

        return {
            "exact_matches": exact_count,
            "fuzzy_matches": fuzzy_count,
            "ai_validated": ai_count,
            "total_mappings": total_mappings,
            "total_gaps": total_gaps,
            "total_undocumented": total_undocumented,
            "ai_cost_inr": ai_cost,
            "ai_input_tokens": ai_input_tokens,
            "ai_output_tokens": ai_output_tokens,
        }

    def run_incremental_mapping(
        self, db: Session, *, concept_ids: List[int], tenant_id: int
    ) -> Dict:
        """
        Incremental mapping: Only re-map specific concepts (after a file change).

        Instead of re-mapping all concepts, this only checks the given concept IDs
        against the opposite graph. Used after incremental analysis updates the
        code graph with new/changed concepts.
        """
        self.logger.info(
            f"Incremental mapping for {len(concept_ids)} concepts, tenant {tenant_id}"
        )

        mapped_count = 0

        for concept_id in concept_ids:
            concept = crud.ontology_concept.get(
                db=db, id=concept_id, tenant_id=tenant_id
            )
            if not concept:
                continue

            # Determine which graph to search against
            if concept.source_type == "code":
                targets = crud.ontology_concept.get_by_source_type(
                    db=db, source_type="document", tenant_id=tenant_id, limit=1000
                )
            elif concept.source_type == "document":
                targets = crud.ontology_concept.get_by_source_type(
                    db=db, source_type="code", tenant_id=tenant_id, limit=1000
                )
            else:
                continue

            concept_norm = _normalize(concept.name)
            concept_tokens = _tokenize(concept.name)
            best_match = None
            best_score = 0.0

            for target in targets:
                target_norm = _normalize(target.name)

                # Exact check
                if concept_norm == target_norm:
                    best_match = target
                    best_score = 1.0
                    break

                # Fuzzy check
                target_tokens = _tokenize(target.name)
                if concept_tokens and target_tokens:
                    overlap = len(concept_tokens & target_tokens)
                    union = len(concept_tokens | target_tokens)
                    token_score = overlap / union if union > 0 else 0.0
                else:
                    token_score = 0.0

                lev_score = _levenshtein_similarity(concept_norm, target_norm)
                combined = max(token_score, lev_score)

                if combined > best_score:
                    best_score = combined
                    best_match = target

            if best_match and best_score >= self.FUZZY_HIGH_CONFIDENCE:
                doc_id = concept.id if concept.source_type == "document" else best_match.id
                code_id = concept.id if concept.source_type == "code" else best_match.id
                method = "exact" if best_score >= 0.99 else "fuzzy"
                status = "confirmed" if best_score >= 0.70 else "candidate"

                crud.concept_mapping.create_mapping(
                    db=db,
                    document_concept_id=doc_id,
                    code_concept_id=code_id,
                    mapping_method=method,
                    confidence_score=round(best_score, 3),
                    status=status,
                    relationship_type="implements",
                    tenant_id=tenant_id,
                )
                mapped_count += 1

        self.logger.info(f"Incremental mapping: {mapped_count} new mappings created")
        return {"new_mappings": mapped_count}

    def get_mismatches(self, db: Session, *, tenant_id: int) -> Dict:
        """
        Pure graph comparison — detect gaps, undocumented features, contradictions.
        This is FREE (no AI calls).
        """
        gaps_concepts = crud.concept_mapping.get_unmapped_document_concepts(
            db=db, tenant_id=tenant_id
        )
        undocumented_concepts = crud.concept_mapping.get_unmapped_code_concepts(
            db=db, tenant_id=tenant_id
        )
        contradiction_mappings = crud.concept_mapping.get_contradictions(
            db=db, tenant_id=tenant_id
        )

        gaps = [
            {"id": c.id, "name": c.name, "type": c.concept_type,
             "description": c.description or ""}
            for c in gaps_concepts
        ]
        undocumented = [
            {"id": c.id, "name": c.name, "type": c.concept_type,
             "description": c.description or ""}
            for c in undocumented_concepts
        ]
        contradictions = [
            {
                "mapping_id": m.id,
                "document_concept": m.document_concept.name if m.document_concept else "?",
                "code_concept": m.code_concept.name if m.code_concept else "?",
                "reasoning": m.ai_reasoning or "",
                "confidence": m.confidence_score,
            }
            for m in contradiction_mappings
        ]

        return {
            "gaps": gaps,
            "undocumented": undocumented,
            "contradictions": contradictions,
            "total_gaps": len(gaps),
            "total_undocumented": len(undocumented),
            "total_contradictions": len(contradictions),
        }

    def _validate_ambiguous_pairs(
        self, db: Session, pairs: List[Tuple], tenant_id: int,
        mapped_doc_ids: set, mapped_code_ids: set,
    ) -> Tuple[int, float, int, int]:
        """
        Tier 3: Send ambiguous pairs to AI for validation.
        Each pair is a tiny prompt (~200 tokens) — NOT the full graph.
        Returns: (ai_count, total_cost_inr, ai_input_tokens, ai_output_tokens)
        """
        ai_count = 0
        total_cost = 0.0
        ai_input_tokens = 0
        ai_output_tokens = 0

        try:
            from app.services.ai.gemini import gemini_service
            from app.services.cost_service import cost_service
            from app.services.analysis_service import repair_json_response
        except Exception as e:
            self.logger.warning(f"AI service unavailable for Tier 3: {e}")
            return 0, 0.0, 0, 0

        if not gemini_service:
            return 0, 0.0, 0, 0

        # Batch ambiguous pairs into a single AI call for efficiency
        pair_data = []
        for dc, cc, score in pairs:
            pair_data.append({
                "doc_name": dc.name,
                "doc_type": dc.concept_type,
                "doc_desc": (dc.description or "")[:100],
                "code_name": cc.name,
                "code_type": cc.concept_type,
                "code_desc": (cc.description or "")[:100],
                "fuzzy_score": round(score, 3),
            })

        if not pair_data:
            return 0, 0.0

        prompt = f"""You are a software architect. For each pair below, determine if the document concept and code concept refer to the same thing.

For each pair, respond with:
- "match": true/false
- "relationship": "implements" | "partially_implements" | "contradicts" | "extends" | "unrelated"
- "confidence": 0.0-1.0
- "reasoning": 1 sentence

RESPONSE FORMAT (valid JSON array):
[
  {{"pair_index": 0, "match": true, "relationship": "implements", "confidence": 0.85, "reasoning": "..."}}
]

PAIRS TO VALIDATE:
{json.dumps(pair_data, indent=2)}"""

        time.sleep(4)  # Rate limiting

        try:
            response = asyncio.run(gemini_service.generate_content(prompt))
            cleaned = repair_json_response(response.text)
            results = json.loads(cleaned)

            # Calculate cost using actual API token counts (including thinking tokens)
            tokens = gemini_service.extract_token_usage(response)
            cost_data = cost_service.calculate_cost_from_actual_tokens(
                input_tokens=tokens['input_tokens'],
                output_tokens=tokens['output_tokens'],
                thinking_tokens=tokens['thinking_tokens'],
            )
            total_cost = cost_data.get("cost_inr", 0)
            ai_input_tokens = tokens['input_tokens']
            ai_output_tokens = tokens['output_tokens'] + tokens['thinking_tokens']

            for r in results:
                idx = r.get("pair_index", -1)
                if idx < 0 or idx >= len(pairs):
                    continue

                dc, cc, _ = pairs[idx]
                is_match = r.get("match", False)
                confidence = r.get("confidence", 0.0)
                relationship = r.get("relationship", "unrelated")
                reasoning = r.get("reasoning", "")

                if is_match and confidence >= 0.5:
                    status = "confirmed" if confidence >= 0.75 else "candidate"
                    crud.concept_mapping.create_mapping(
                        db=db,
                        document_concept_id=dc.id,
                        code_concept_id=cc.id,
                        mapping_method="ai_validated",
                        confidence_score=confidence,
                        status=status,
                        relationship_type=relationship,
                        ai_reasoning=reasoning,
                        tenant_id=tenant_id,
                    )
                    mapped_doc_ids.add(dc.id)
                    mapped_code_ids.add(cc.id)
                    ai_count += 1

                    if status == "confirmed" and confidence >= 0.85:
                        crud.ontology_concept.promote_to_both(
                            db=db, concept_id=dc.id, tenant_id=tenant_id
                        )
                        crud.ontology_concept.promote_to_both(
                            db=db, concept_id=cc.id, tenant_id=tenant_id
                        )

        except Exception as e:
            self.logger.error(f"Tier 3 AI validation failed: {e}")

        self.logger.info(f"Tier 3 (AI): {ai_count} validated, cost: INR {total_cost:.4f}")
        return ai_count, total_cost, ai_input_tokens, ai_output_tokens


# Global instance
mapping_service = MappingService()
