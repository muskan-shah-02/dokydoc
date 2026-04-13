"""
ConceptMapping Model — Cross-Graph Link Table

Maps document-layer concepts to code-layer concepts WITHOUT polluting
the ontology_relationships table. This replaces the expensive AI
reconciliation pass with an explicit, auditable mapping table.

Mapping Methods (3-tier, cost-optimized):
  - "exact":        Free — normalized name match
  - "fuzzy":        Free — token overlap / Levenshtein
  - "ai_validated": ~$0.001 — only for ambiguous pairs

Status Flow:
  candidate → confirmed (by AI or human)
  candidate → rejected  (by AI or human)
"""

from sqlalchemy import Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from typing import Optional
from app.db.base_class import Base


class ConceptMapping(Base):
    __tablename__ = "concept_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # The two concepts being mapped (document ↔ code)
    document_concept_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ontology_concepts.id"), nullable=False, index=True
    )
    code_concept_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ontology_concepts.id"), nullable=False, index=True
    )

    # How the mapping was established
    mapping_method: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "exact", "fuzzy", "ai_validated"

    # Confidence score (0.0-1.0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Mapping status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="candidate", index=True
    )  # "candidate", "confirmed", "rejected"

    # The specific relationship type between the mapped concepts
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="implements"
    )  # "implements", "partially_implements", "enforces", "contradicts", "extends"

    # AI reasoning (only populated for ai_validated mappings)
    ai_reasoning: Mapped[str] = mapped_column(Text, nullable=True)

    # Feedback fields (Sprint 5 — human confirm/reject with comment)
    feedback_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    feedback_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    feedback_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # P4-05: Validation feedback loop — write AI verdict back to BOE
    # Closes the loop: validation result → confidence_score nudge → better BOE cache
    last_validated_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    validation_verdict: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # 'MATCH' | 'PARTIAL_MATCH' | 'MISMATCH' — None means never validated

    # Timestamps
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    document_concept = relationship(
        "OntologyConcept", foreign_keys=[document_concept_id]
    )
    code_concept = relationship(
        "OntologyConcept", foreign_keys=[code_concept_id]
    )

    def __repr__(self):
        return (
            f"<ConceptMapping(id={self.id}, doc={self.document_concept_id}, "
            f"code={self.code_concept_id}, method='{self.mapping_method}', "
            f"status='{self.status}')>"
        )
