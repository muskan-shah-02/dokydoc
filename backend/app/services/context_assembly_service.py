"""
ContextAssemblyService — Builds Context Envelopes from BOE

When a file changes, the AI needs system-level understanding without
re-reading the entire repository. This service assembles a "context envelope"
from the Business Ontology Engine and stored analyses — giving the AI
Claude-Code-level understanding for ~3000 tokens instead of millions.

Context Envelope contents:
  1. Previous analysis of the file          (from CodeComponent.structured_analysis)
  2. BOE concepts linked to this file       (from ontology graph)
  3. Business rules from documents          (from document graph mappings)
  4. Neighbor file summaries                (from related CodeComponents)
  5. Git diff of what changed               (passed by caller)

Cost: $0 — all data comes from database queries, no AI calls.
"""

import json
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import crud
from app.models.code_component import CodeComponent
from app.models.ontology_concept import OntologyConcept
from app.core.logging import LoggerMixin


class ContextEnvelope:
    """
    A compact package of system context for AI analysis of a single file.
    Typically ~3000-5000 tokens — replaces sending the entire repo.
    """

    def __init__(self):
        self.file_path: str = ""
        self.previous_analysis: Optional[Dict] = None
        self.previous_summary: str = ""
        self.related_concepts: List[Dict] = []
        self.business_rules: List[Dict] = []
        self.neighbor_summaries: List[Dict] = []
        self.mapped_document_concepts: List[Dict] = []

    def to_prompt_context(self) -> str:
        """Format the envelope as a prompt section for AI consumption."""
        sections = []

        if self.previous_summary:
            sections.append(
                f"PREVIOUS UNDERSTANDING OF THIS FILE:\n{self.previous_summary}"
            )

        if self.related_concepts:
            concept_lines = [
                f"  - {c['name']} ({c['type']}): {c.get('description', '')[:80]}"
                for c in self.related_concepts[:15]
            ]
            sections.append(
                "CODE GRAPH CONCEPTS (from this file's domain):\n"
                + "\n".join(concept_lines)
            )

        if self.mapped_document_concepts:
            doc_lines = [
                f"  - {c['name']} ({c['type']}): {c.get('description', '')[:80]}"
                for c in self.mapped_document_concepts[:10]
            ]
            sections.append(
                "MAPPED DOCUMENT REQUIREMENTS:\n"
                + "\n".join(doc_lines)
            )

        if self.business_rules:
            rule_lines = [
                f"  - [{r.get('rule_type', 'rule')}] {r.get('description', '')[:100]}"
                for r in self.business_rules[:10]
            ]
            sections.append(
                "BUSINESS RULES (from BRD/SRS documents):\n"
                + "\n".join(rule_lines)
            )

        if self.neighbor_summaries:
            neighbor_lines = [
                f"  - {n['name']}: {n['summary'][:100]}"
                for n in self.neighbor_summaries[:8]
            ]
            sections.append(
                "RELATED FILES IN THIS REPOSITORY:\n"
                + "\n".join(neighbor_lines)
            )

        if not sections:
            return "No prior context available for this file."

        return "\n\n".join(sections)

    def token_estimate(self) -> int:
        """Rough token estimate (1 token ≈ 4 chars)."""
        return len(self.to_prompt_context()) // 4


class ContextAssemblyService(LoggerMixin):
    """
    Assembles context envelopes from the BOE and stored analyses.
    All operations are database queries — zero AI cost.
    """

    def __init__(self):
        super().__init__()
        self.logger.info("ContextAssemblyService initialized")

    def build_envelope(
        self, db: Session, *,
        component_id: int,
        tenant_id: int,
        repo_id: int = None,
    ) -> ContextEnvelope:
        """
        Build a context envelope for a code component.

        Gathers:
        1. Previous analysis of this file
        2. Related BOE concepts (code-layer)
        3. Mapped document concepts (via ConceptMapping)
        4. Business rules from enhanced analysis of neighbors
        5. Summaries of related files in the same repo
        """
        envelope = ContextEnvelope()

        # 1. Get the component and its previous analysis
        component = crud.code_component.get(
            db=db, id=component_id, tenant_id=tenant_id
        )
        if not component:
            self.logger.warning(f"Component {component_id} not found")
            return envelope

        envelope.file_path = component.location or component.name
        envelope.previous_analysis = component.structured_analysis
        envelope.previous_summary = component.summary or ""

        # 2. Get code-layer concepts related to this file's domain
        # We search by keyword overlap between file name/summary and concept names
        envelope.related_concepts = self._find_related_concepts(
            db=db, component=component, tenant_id=tenant_id
        )

        # 3. Get mapped document concepts (via ConceptMapping table)
        envelope.mapped_document_concepts = self._find_mapped_documents(
            db=db, code_concepts=envelope.related_concepts, tenant_id=tenant_id
        )

        # 4. Extract business rules from neighbors' enhanced analyses
        if repo_id or component.repository_id:
            rid = repo_id or component.repository_id
            envelope.neighbor_summaries = self._get_neighbor_summaries(
                db=db, repo_id=rid, component_id=component_id, tenant_id=tenant_id
            )
            envelope.business_rules = self._extract_business_rules_from_neighbors(
                db=db, repo_id=rid, tenant_id=tenant_id
            )

        self.logger.info(
            f"Context envelope built for component {component_id}: "
            f"~{envelope.token_estimate()} tokens, "
            f"{len(envelope.related_concepts)} concepts, "
            f"{len(envelope.neighbor_summaries)} neighbors"
        )
        return envelope

    def build_envelope_for_file(
        self, db: Session, *,
        file_name: str,
        repo_id: int,
        tenant_id: int,
    ) -> ContextEnvelope:
        """
        Build a context envelope by file name within a repo.
        Used when we know the file but not the component ID.
        """
        component = db.query(CodeComponent).filter(
            CodeComponent.repository_id == repo_id,
            CodeComponent.name == file_name,
            CodeComponent.tenant_id == tenant_id,
        ).first()

        if component:
            return self.build_envelope(
                db=db, component_id=component.id,
                tenant_id=tenant_id, repo_id=repo_id
            )

        # No existing component — return minimal envelope
        envelope = ContextEnvelope()
        envelope.file_path = file_name
        return envelope

    def _find_related_concepts(
        self, db: Session, component: CodeComponent, tenant_id: int
    ) -> List[Dict]:
        """
        Find code-layer ontology concepts related to this file.
        Uses keyword matching between file name/summary and concept names.
        """
        # Extract keywords from the file name and summary
        keywords = set()
        name_parts = component.name.replace(".", " ").replace("_", " ").replace("-", " ").split()
        keywords.update(w.lower() for w in name_parts if len(w) > 2)

        if component.summary:
            summary_words = component.summary.split()
            # Take meaningful words (>3 chars, not common stop words)
            stop_words = {"the", "and", "for", "this", "that", "with", "from", "are", "was", "has", "been"}
            keywords.update(
                w.lower().strip(".,;:()") for w in summary_words
                if len(w) > 3 and w.lower() not in stop_words
            )

        if not keywords:
            return []

        # Find concepts whose names overlap with these keywords
        all_code_concepts = crud.ontology_concept.get_by_source_type(
            db=db, source_type="code", tenant_id=tenant_id, limit=500
        )
        # Also include "both" concepts
        both_concepts = crud.ontology_concept.get_by_source_type(
            db=db, source_type="both", tenant_id=tenant_id, limit=200
        )
        all_concepts = (all_code_concepts or []) + (both_concepts or [])

        related = []
        for concept in all_concepts:
            concept_words = set(
                w.lower() for w in concept.name.replace("_", " ").replace("-", " ").split()
                if len(w) > 2
            )
            overlap = keywords & concept_words
            if overlap:
                related.append({
                    "id": concept.id,
                    "name": concept.name,
                    "type": concept.concept_type,
                    "description": concept.description or "",
                    "relevance": len(overlap),
                })

        # Sort by relevance (most keyword overlap first)
        related.sort(key=lambda x: x["relevance"], reverse=True)
        return related[:15]

    def _find_mapped_documents(
        self, db: Session, code_concepts: List[Dict], tenant_id: int
    ) -> List[Dict]:
        """
        For the code concepts related to this file, find their mapped
        document concepts via the ConceptMapping table.
        """
        if not code_concepts:
            return []

        doc_concepts = []
        seen_ids = set()

        for cc in code_concepts[:10]:
            mappings = crud.concept_mapping.get_by_code_concept(
                db=db, code_concept_id=cc["id"], tenant_id=tenant_id
            )
            for mapping in mappings:
                if mapping.status == "rejected":
                    continue
                dc = mapping.document_concept
                if dc and dc.id not in seen_ids:
                    seen_ids.add(dc.id)
                    doc_concepts.append({
                        "id": dc.id,
                        "name": dc.name,
                        "type": dc.concept_type,
                        "description": dc.description or "",
                        "mapping_confidence": mapping.confidence_score,
                    })

        return doc_concepts[:10]

    def _get_neighbor_summaries(
        self, db: Session, repo_id: int, component_id: int, tenant_id: int
    ) -> List[Dict]:
        """
        Get summaries of other files in the same repository.
        These give the AI understanding of the broader codebase.
        """
        neighbors = db.query(CodeComponent).filter(
            CodeComponent.repository_id == repo_id,
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.id != component_id,
            CodeComponent.analysis_status == "completed",
            CodeComponent.summary.isnot(None),
        ).limit(10).all()

        return [
            {"name": n.name, "summary": n.summary or ""}
            for n in neighbors
            if n.summary
        ]

    def _extract_business_rules_from_neighbors(
        self, db: Session, repo_id: int, tenant_id: int
    ) -> List[Dict]:
        """
        Extract business_rules from enhanced analyses of files in this repo.
        These are the actual rules extracted by AI-02 enhanced analysis.
        """
        components = db.query(CodeComponent).filter(
            CodeComponent.repository_id == repo_id,
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.analysis_status == "completed",
            CodeComponent.structured_analysis.isnot(None),
        ).limit(20).all()

        rules = []
        for comp in components:
            sa = comp.structured_analysis
            if isinstance(sa, dict):
                file_rules = sa.get("business_rules", [])
                for rule in file_rules:
                    if isinstance(rule, dict):
                        rules.append({
                            "file": comp.name,
                            "rule_type": rule.get("rule_type", "unknown"),
                            "description": rule.get("description", ""),
                            "code_location": rule.get("code_location", ""),
                        })

        return rules[:10]


# Global instance
context_assembly_service = ContextAssemblyService()
