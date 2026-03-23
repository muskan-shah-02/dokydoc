"""
CrossProjectMapping Model — Cross-Project Concept Links

Maps concepts BETWEEN projects (initiatives) to show how different
projects in an organization relate to each other. Separate table
from ConceptMapping because:
  - ConceptMapping is locked to document↔code semantics
  - Cross-project maps ANY concept to ANY concept across projects
  - Different relationship types: calls_api, shares_data, depends_on, etc.

Mapping Methods (reuses 3-tier approach):
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
from app.db.base_class import Base


class CrossProjectMapping(Base):
    __tablename__ = "cross_project_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # The two concepts being mapped (from different projects)
    concept_a_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ontology_concepts.id"), nullable=False, index=True
    )
    concept_b_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ontology_concepts.id"), nullable=False, index=True
    )

    # Denormalized initiative IDs for fast cross-project queries
    initiative_a_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("initiatives.id"), nullable=False, index=True
    )
    initiative_b_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("initiatives.id"), nullable=False, index=True
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

    # Cross-project relationship type
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="shares_concept"
    )  # "calls_api", "shares_data", "depends_on", "duplicates", "extends", "shares_concept"

    # AI reasoning (only populated for ai_validated mappings)
    ai_reasoning: Mapped[str] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    concept_a = relationship("OntologyConcept", foreign_keys=[concept_a_id])
    concept_b = relationship("OntologyConcept", foreign_keys=[concept_b_id])
    initiative_a = relationship("Initiative", foreign_keys=[initiative_a_id])
    initiative_b = relationship("Initiative", foreign_keys=[initiative_b_id])

    def __repr__(self):
        return (
            f"<CrossProjectMapping(id={self.id}, "
            f"concept_a={self.concept_a_id}@project_{self.initiative_a_id}, "
            f"concept_b={self.concept_b_id}@project_{self.initiative_b_id}, "
            f"method='{self.mapping_method}', status='{self.status}')>"
        )
