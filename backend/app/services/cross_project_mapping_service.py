"""
CrossProjectMappingService — Inter-Project Concept Mapping

Reuses the 3-tier cost-optimized approach (exact → fuzzy → AI) but runs
BETWEEN two projects instead of between document and code layers.

  Tier 1: EXACT match   — normalized name equality        — FREE ($0)
  Tier 2: FUZZY match   — token overlap + Levenshtein     — FREE ($0)
  Tier 3: AI validation — only ambiguous pairs from Tier 2 — ~$0.001/pair

Typical cost: ~$0.02-0.05 per cross-project mapping run.
"""

import re
import time
import json
import asyncio
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session

from app import crud
from app.models.ontology_concept import OntologyConcept
from app.core.logging import LoggerMixin


# Reuse normalization utilities from mapping_service
def _normalize(name: str) -> str:
    n = name.strip().lower()
    n = re.sub(r'[_\-.]', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def _tokenize(name: str) -> set:
    normalized = _normalize(name)
    return {t for t in normalized.split() if len(t) > 1}


def _levenshtein_distance(s1: str, s2: str) -> int:
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
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return 1.0 - (_levenshtein_distance(s1, s2) / max_len)


class CrossProjectMappingService(LoggerMixin):
    """
    Maps concepts between different projects to discover cross-project
    relationships (shared APIs, duplicated concepts, dependencies).
    """

    FUZZY_HIGH_CONFIDENCE = 0.50
    FUZZY_MEDIUM_CONFIDENCE = 0.25
    LEVENSHTEIN_THRESHOLD = 0.70

    def __init__(self):
        super().__init__()
        self.logger.info("CrossProjectMappingService initialized")

    def run_cross_project_mapping(
        self, db: Session, *,
        initiative_a_id: int,
        initiative_b_id: int,
        tenant_id: int,
        use_ai_fallback: bool = True
    ) -> Dict:
        """
        Run 3-tier mapping between two projects.

        Gets concepts strictly belonging to each project (NOT shared/NULL),
        then runs exact → fuzzy → AI matching between them.
        """
        self.logger.info(
            f"Starting cross-project mapping: project {initiative_a_id} ↔ project {initiative_b_id}"
        )

        # Get concepts STRICTLY belonging to each project (not shared/unscoped)
        concepts_a = self._get_project_concepts(db, initiative_a_id, tenant_id)
        concepts_b = self._get_project_concepts(db, initiative_b_id, tenant_id)

        if not concepts_a or not concepts_b:
            self.logger.info(
                f"Cross-project mapping skipped: "
                f"{len(concepts_a)} concepts in project A, "
                f"{len(concepts_b)} concepts in project B — need both."
            )
            return {
                "initiative_a_id": initiative_a_id,
                "initiative_b_id": initiative_b_id,
                "exact_matches": 0, "fuzzy_matches": 0, "ai_validated": 0,
                "total_mappings": 0, "ai_cost_inr": 0.0,
            }

        # Clear previous mappings between these projects
        crud.cross_project_mapping.delete_between_initiatives(
            db=db, initiative_a_id=initiative_a_id,
            initiative_b_id=initiative_b_id, tenant_id=tenant_id
        )

        exact_count = 0
        fuzzy_count = 0
        ai_count = 0
        ai_cost = 0.0
        mapped_a_ids = set()
        mapped_b_ids = set()

        # Build normalized lookup for project B
        b_by_normalized = {}
        for cb in concepts_b:
            key = _normalize(cb.name)
            b_by_normalized.setdefault(key, []).append(cb)

        # ============================
        # TIER 1: EXACT MATCH (FREE)
        # ============================
        for ca in concepts_a:
            ca_norm = _normalize(ca.name)
            if ca_norm in b_by_normalized:
                for cb in b_by_normalized[ca_norm]:
                    if cb.id in mapped_b_ids:
                        continue
                    crud.cross_project_mapping.create_mapping(
                        db=db,
                        concept_a_id=ca.id,
                        concept_b_id=cb.id,
                        initiative_a_id=initiative_a_id,
                        initiative_b_id=initiative_b_id,
                        mapping_method="exact",
                        confidence_score=1.0,
                        status="confirmed",
                        relationship_type="shares_concept",
                        tenant_id=tenant_id,
                    )
                    mapped_a_ids.add(ca.id)
                    mapped_b_ids.add(cb.id)
                    exact_count += 1

        self.logger.info(f"Tier 1 (exact): {exact_count} cross-project matches")

        # ============================
        # TIER 2: FUZZY MATCH (FREE)
        # ============================
        unmapped_a = [ca for ca in concepts_a if ca.id not in mapped_a_ids]
        unmapped_b = [cb for cb in concepts_b if cb.id not in mapped_b_ids]
        ambiguous_pairs = []

        for ca in unmapped_a:
            ca_tokens = _tokenize(ca.name)
            ca_norm = _normalize(ca.name)
            best_match = None
            best_score = 0.0

            for cb in unmapped_b:
                if cb.id in mapped_b_ids:
                    continue

                cb_tokens = _tokenize(cb.name)
                cb_norm = _normalize(cb.name)

                # Token overlap
                if ca_tokens and cb_tokens:
                    overlap = len(ca_tokens & cb_tokens)
                    union = len(ca_tokens | cb_tokens)
                    token_score = overlap / union if union > 0 else 0.0
                else:
                    token_score = 0.0

                # Levenshtein
                lev_score = _levenshtein_similarity(ca_norm, cb_norm)
                combined = max(token_score, lev_score)

                if combined > best_score:
                    best_score = combined
                    best_match = cb

            if best_match and best_score >= self.FUZZY_HIGH_CONFIDENCE:
                status = "confirmed" if best_score >= 0.70 else "candidate"
                crud.cross_project_mapping.create_mapping(
                    db=db,
                    concept_a_id=ca.id,
                    concept_b_id=best_match.id,
                    initiative_a_id=initiative_a_id,
                    initiative_b_id=initiative_b_id,
                    mapping_method="fuzzy",
                    confidence_score=round(best_score, 3),
                    status=status,
                    relationship_type="shares_concept",
                    tenant_id=tenant_id,
                )
                mapped_a_ids.add(ca.id)
                mapped_b_ids.add(best_match.id)
                fuzzy_count += 1
            elif best_match and best_score >= self.FUZZY_MEDIUM_CONFIDENCE:
                ambiguous_pairs.append((ca, best_match, best_score))

        self.logger.info(
            f"Tier 2 (fuzzy): {fuzzy_count} matches, "
            f"{len(ambiguous_pairs)} ambiguous pairs queued for AI"
        )

        # ============================
        # TIER 3: AI VALIDATION (PAID)
        # ============================
        if use_ai_fallback and ambiguous_pairs:
            ai_count, ai_cost = self._validate_ambiguous_pairs(
                db=db, pairs=ambiguous_pairs, tenant_id=tenant_id,
                initiative_a_id=initiative_a_id,
                initiative_b_id=initiative_b_id,
                mapped_a_ids=mapped_a_ids, mapped_b_ids=mapped_b_ids,
            )

        total_mappings = exact_count + fuzzy_count + ai_count

        self.logger.info(
            f"Cross-project mapping complete: project {initiative_a_id} ↔ {initiative_b_id}: "
            f"{exact_count} exact + {fuzzy_count} fuzzy + {ai_count} AI = {total_mappings} total. "
            f"AI cost: INR {ai_cost:.4f}"
        )

        return {
            "initiative_a_id": initiative_a_id,
            "initiative_b_id": initiative_b_id,
            "exact_matches": exact_count,
            "fuzzy_matches": fuzzy_count,
            "ai_validated": ai_count,
            "total_mappings": total_mappings,
            "ai_cost_inr": ai_cost,
        }

    def _get_project_concepts(
        self, db: Session, initiative_id: int, tenant_id: int
    ) -> List[OntologyConcept]:
        """Get concepts strictly belonging to a project (NOT shared/NULL)."""
        return db.query(OntologyConcept).filter(
            OntologyConcept.tenant_id == tenant_id,
            OntologyConcept.initiative_id == initiative_id,
            OntologyConcept.is_active == True
        ).all()

    def _validate_ambiguous_pairs(
        self, db: Session, pairs: List[Tuple], tenant_id: int,
        initiative_a_id: int, initiative_b_id: int,
        mapped_a_ids: set, mapped_b_ids: set,
    ) -> Tuple[int, float]:
        """Tier 3: AI validation for ambiguous cross-project pairs."""
        ai_count = 0
        total_cost = 0.0

        try:
            from app.services.ai.gemini import gemini_service
            from app.services.cost_service import cost_service
            from app.services.analysis_service import repair_json_response
        except Exception as e:
            self.logger.warning(f"AI service unavailable for Tier 3: {e}")
            return 0, 0.0

        pair_data = []
        for ca, cb, score in pairs:
            pair_data.append({
                "concept_a": ca.name,
                "type_a": ca.concept_type,
                "desc_a": (ca.description or "")[:100],
                "concept_b": cb.name,
                "type_b": cb.concept_type,
                "desc_b": (cb.description or "")[:100],
                "fuzzy_score": round(score, 3),
            })

        if not pair_data:
            return 0, 0.0

        prompt = f"""You are a software architect. These concept pairs come from DIFFERENT projects in the same organization.
For each pair, determine if they refer to the same thing or are related across projects.

For each pair, respond with:
- "match": true/false
- "relationship": "shares_concept" | "calls_api" | "shares_data" | "depends_on" | "duplicates" | "extends" | "unrelated"
- "confidence": 0.0-1.0
- "reasoning": 1 sentence

RESPONSE FORMAT (valid JSON array):
[
  {{"pair_index": 0, "match": true, "relationship": "shares_concept", "confidence": 0.85, "reasoning": "..."}}
]

PAIRS TO VALIDATE:
{json.dumps(pair_data, indent=2)}"""

        time.sleep(4)

        try:
            response = asyncio.run(gemini_service.generate_content(prompt))
            cleaned = repair_json_response(response.text)
            results = json.loads(cleaned)

            tokens = gemini_service.extract_token_usage(response)
            cost_data = cost_service.calculate_cost_from_actual_tokens(
                input_tokens=tokens['input_tokens'],
                output_tokens=tokens['output_tokens'],
                thinking_tokens=tokens['thinking_tokens'],
            )
            total_cost = cost_data.get("cost_inr", 0)

            for r in results:
                idx = r.get("pair_index", -1)
                if idx < 0 or idx >= len(pairs):
                    continue

                ca, cb, _ = pairs[idx]
                is_match = r.get("match", False)
                confidence = r.get("confidence", 0.0)
                relationship = r.get("relationship", "unrelated")
                reasoning = r.get("reasoning", "")

                if is_match and confidence >= 0.5:
                    status = "confirmed" if confidence >= 0.75 else "candidate"
                    crud.cross_project_mapping.create_mapping(
                        db=db,
                        concept_a_id=ca.id,
                        concept_b_id=cb.id,
                        initiative_a_id=initiative_a_id,
                        initiative_b_id=initiative_b_id,
                        mapping_method="ai_validated",
                        confidence_score=confidence,
                        status=status,
                        relationship_type=relationship,
                        ai_reasoning=reasoning,
                        tenant_id=tenant_id,
                    )
                    mapped_a_ids.add(ca.id)
                    mapped_b_ids.add(cb.id)
                    ai_count += 1

        except Exception as e:
            self.logger.error(f"Cross-project Tier 3 AI validation failed: {e}")

        self.logger.info(f"Tier 3 (AI): {ai_count} validated, cost: INR {total_cost:.4f}")
        return ai_count, total_cost


# Global instance
cross_project_mapping_service = CrossProjectMappingService()
