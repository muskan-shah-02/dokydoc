from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_

from app.crud.base import CRUDBase
from app.models.ontology_relationship import OntologyRelationship
from app.models.ontology_concept import OntologyConcept
from app.schemas.ontology import OntologyRelationshipCreate, OntologyRelationshipUpdate


class CRUDOntologyRelationship(CRUDBase[OntologyRelationship, OntologyRelationshipCreate, OntologyRelationshipUpdate]):

    def create_if_not_exists(
        self, db: Session, *, source_concept_id: int, target_concept_id: int,
        relationship_type: str, tenant_id: int,
        description: str = None, confidence_score: float = None
    ) -> OntologyRelationship:
        """
        Idempotent relationship creation. Returns existing if source+target+type+tenant match.
        Prevents duplicate edges in the graph.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for create_if_not_exists()")

        existing = db.query(self.model).filter(
            self.model.source_concept_id == source_concept_id,
            self.model.target_concept_id == target_concept_id,
            self.model.relationship_type == relationship_type,
            self.model.tenant_id == tenant_id
        ).first()

        if existing:
            if confidence_score and (existing.confidence_score is None or confidence_score > existing.confidence_score):
                existing.confidence_score = confidence_score
                db.commit()
                db.refresh(existing)
            return existing

        db_obj = self.model(
            source_concept_id=source_concept_id,
            target_concept_id=target_concept_id,
            relationship_type=relationship_type,
            description=description,
            confidence_score=confidence_score,
            tenant_id=tenant_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_concept(
        self, db: Session, *, concept_id: int, tenant_id: int
    ) -> List[OntologyRelationship]:
        """Get all relationships where the concept is either source or target."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_concept()")

        return db.query(self.model).filter(
            or_(
                self.model.source_concept_id == concept_id,
                self.model.target_concept_id == concept_id
            ),
            self.model.tenant_id == tenant_id
        ).options(
            joinedload(self.model.source_concept),
            joinedload(self.model.target_concept)
        ).all()

    def get_outgoing(
        self, db: Session, *, concept_id: int, tenant_id: int
    ) -> List[OntologyRelationship]:
        """Get all outgoing relationships from a concept."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_outgoing()")

        return db.query(self.model).filter(
            self.model.source_concept_id == concept_id,
            self.model.tenant_id == tenant_id
        ).options(
            joinedload(self.model.target_concept)
        ).all()

    def get_incoming(
        self, db: Session, *, concept_id: int, tenant_id: int
    ) -> List[OntologyRelationship]:
        """Get all incoming relationships to a concept."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_incoming()")

        return db.query(self.model).filter(
            self.model.target_concept_id == concept_id,
            self.model.tenant_id == tenant_id
        ).options(
            joinedload(self.model.source_concept)
        ).all()

    def get_by_type(
        self, db: Session, *, relationship_type: str, tenant_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[OntologyRelationship]:
        """Get all relationships of a specific type."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_type()")

        return db.query(self.model).filter(
            self.model.relationship_type == relationship_type,
            self.model.tenant_id == tenant_id
        ).options(
            joinedload(self.model.source_concept),
            joinedload(self.model.target_concept)
        ).offset(skip).limit(limit).all()

    def get_full_graph(
        self, db: Session, *, tenant_id: int
    ) -> List[OntologyRelationship]:
        """Get the entire relationship graph for a tenant (for visualization)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_full_graph()")

        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id
        ).options(
            joinedload(self.model.source_concept),
            joinedload(self.model.target_concept)
        ).all()

    def delete_by_concept(
        self, db: Session, *, concept_id: int, tenant_id: int
    ) -> int:
        """Delete all relationships involving a concept (for cascade cleanup)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for delete_by_concept()")

        num_deleted = db.query(self.model).filter(
            or_(
                self.model.source_concept_id == concept_id,
                self.model.target_concept_id == concept_id
            ),
            self.model.tenant_id == tenant_id
        ).delete()
        db.commit()
        return num_deleted

    def count_by_tenant(self, db: Session, *, tenant_id: int) -> int:
        """Count all relationships for a tenant."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for count_by_tenant()")

        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id
        ).count()


ontology_relationship = CRUDOntologyRelationship(OntologyRelationship)
