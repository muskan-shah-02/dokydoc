"""
Ontology Concept Model

Represents a concept in the business ontology (e.g., "User Authentication", "Payment Processing").
These are the nodes in the knowledge graph.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class OntologyConcept(Base):
    __tablename__ = "ontology_concepts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    concept_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "FEATURE", "TECHNOLOGY", "PROCESS"
    description: Mapped[str] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(nullable=True)  # AI confidence in this concept
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    outgoing_relationships = relationship("OntologyRelationship", foreign_keys="OntologyRelationship.source_concept_id", back_populates="source_concept")
    incoming_relationships = relationship("OntologyRelationship", foreign_keys="OntologyRelationship.target_concept_id", back_populates="target_concept")

    def __repr__(self):
        return f"<OntologyConcept(id={self.id}, name='{self.name}', type='{self.concept_type}')>"
