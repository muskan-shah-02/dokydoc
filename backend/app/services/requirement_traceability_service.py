"""
Requirement Traceability Service

Automatically builds requirement traces from document structured_data
and links them to code concepts via the existing mapping pipeline.

Layer 2 of the 3-layer hybrid validation system:
- Layer 1: Graph Mapping (coverage scan) — existing mapping_service.py
- Layer 2: Requirement Tracing (granular linking) — THIS SERVICE
- Layer 3: Logic Validation (AI correctness) — existing validation_service.py
"""

from typing import List, Dict
from sqlalchemy.orm import Session

from app import crud
from app.core.logging import LoggerMixin


class RequirementTraceabilityService(LoggerMixin):

    def __init__(self):
        super().__init__()

    def build_traces_for_document(
        self, db: Session, *, document_id: int, tenant_id: int
    ) -> Dict:
        """
        Extract requirements from document structured_data and create
        RequirementTrace records. Then match each requirement to code
        concepts using name matching and graph mapping data.
        """
        self.logger.info(f"Building requirement traces for document {document_id}")

        # Get document analysis results
        analysis_results = crud.analysis_result.get_multi_by_document(
            db=db, document_id=document_id, tenant_id=tenant_id
        )
        if not analysis_results:
            return {"traces_created": 0, "traces_linked": 0}

        # Resolve initiative
        initiative_id = self._resolve_initiative(db, document_id, tenant_id)

        # Extract requirements from structured_data
        requirements = []
        req_counter = 0
        for result in analysis_results:
            data = result.structured_data
            if not data or not isinstance(data, dict):
                continue

            # Collect from all requirement-like fields
            for field in ["requirements", "functional_requirements", "business_rules",
                          "acceptance_criteria", "user_stories"]:
                for item in data.get(field, []):
                    req_counter += 1
                    if isinstance(item, dict):
                        key = (item.get("id") or item.get("rule_id") or
                               item.get("name") or f"REQ-{req_counter:03d}")
                        text = (item.get("description") or item.get("text") or
                                item.get("criterion") or item.get("story") or
                                item.get("name") or "")
                    elif isinstance(item, str):
                        key = f"REQ-{req_counter:03d}"
                        text = item
                    else:
                        continue

                    if text and len(text.strip()) >= 5:
                        requirements.append({"key": str(key).strip(), "text": text.strip()})

        if not requirements:
            self.logger.info(f"No extractable requirements found in document {document_id}")
            return {"traces_created": 0, "traces_linked": 0}

        # Get all code concepts for this tenant (for matching)
        code_concepts = crud.ontology_concept.get_by_source_type(
            db=db, source_type="code", tenant_id=tenant_id, limit=1000
        )
        # Also get "both" type concepts (promoted from exact matching)
        both_concepts = crud.ontology_concept.get_by_source_type(
            db=db, source_type="both", tenant_id=tenant_id, limit=1000
        )
        all_code = list(code_concepts or []) + list(both_concepts or [])

        # Build lookup for matching
        code_lookup = {}
        for c in all_code:
            key = c.name.strip().lower()
            if key not in code_lookup:
                code_lookup[key] = []
            code_lookup[key].append(c)

        # Create/update traces
        traces_created = 0
        traces_linked = 0

        for req in requirements:
            matched_concept_ids = []
            matched_component_ids = []

            # Match requirement text against code concept names
            req_words = set(req["text"].lower().split())
            for concept_key, concepts in code_lookup.items():
                concept_words = set(concept_key.split())
                # If significant word overlap, consider it a match
                overlap = req_words & concept_words
                if len(overlap) >= 2 or (len(concept_words) >= 2 and overlap == concept_words):
                    for c in concepts:
                        if c.id not in matched_concept_ids:
                            matched_concept_ids.append(c.id)
                        if c.source_component_id and c.source_component_id not in matched_component_ids:
                            matched_component_ids.append(c.source_component_id)

            # Determine coverage status
            if matched_concept_ids:
                coverage = "fully_covered" if len(matched_concept_ids) >= 2 else "partially_covered"
                traces_linked += 1
            else:
                coverage = "not_covered"

            crud.requirement_trace.upsert(
                db=db,
                tenant_id=tenant_id,
                document_id=document_id,
                requirement_key=req["key"],
                requirement_text=req["text"][:2000],
                initiative_id=initiative_id,
                code_concept_ids=matched_concept_ids,
                code_component_ids=matched_component_ids,
                coverage_status=coverage,
            )
            traces_created += 1

        db.commit()

        self.logger.info(
            f"Requirement traces built for document {document_id}: "
            f"{traces_created} traces, {traces_linked} linked to code"
        )

        return {
            "traces_created": traces_created,
            "traces_linked": traces_linked,
        }

    @staticmethod
    def _resolve_initiative(db: Session, document_id: int, tenant_id: int):
        try:
            from app.models.initiative_asset import InitiativeAsset
            asset = db.query(InitiativeAsset).filter(
                InitiativeAsset.tenant_id == tenant_id,
                InitiativeAsset.asset_type == "DOCUMENT",
                InitiativeAsset.asset_id == document_id,
                InitiativeAsset.is_active == True
            ).first()
            return asset.initiative_id if asset else None
        except Exception:
            return None


requirement_traceability_service = RequirementTraceabilityService()
