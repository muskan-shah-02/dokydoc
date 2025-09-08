"""
Ontology Relationship Model

Represents relationships between concepts in the business ontology (e.g., "User Authentication" -> "implements" -> "Security Requirements").
These are the edges in the knowledge graph.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class OntologyRelationship(Base):
    __tablename__ = "ontology_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_concept_id: Mapped[int] = mapped_column(Integer, ForeignKey("ontology_concepts.id"), nullable=False)
    target_concept_id: Mapped[int] = mapped_column(Integer, ForeignKey("ontology_concepts.id"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "implements", "depends_on", "conflicts_with"
    description: Mapped[str] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=True)  # AI confidence in this relationship
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    source_concept = relationship("OntologyConcept", foreign_keys=[source_concept_id], back_populates="outgoing_relationships")
    target_concept = relationship("OntologyConcept", foreign_keys=[target_concept_id], back_populates="incoming_relationships")

    def __repr__(self):
        return f"<OntologyRelationship(id={self.id}, source={self.source_concept_id}, target={self.target_concept_id}, type='{self.relationship_type}')>"
