from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.crud.base import CRUDBase
from app.models.ontology_concept import OntologyConcept
from app.schemas.ontology import OntologyConceptCreate, OntologyConceptUpdate


class CRUDOntologyConcept(CRUDBase[OntologyConcept, OntologyConceptCreate, OntologyConceptUpdate]):

    def get_or_create(
        self, db: Session, *, name: str, concept_type: str, tenant_id: int,
        description: str = None, confidence_score: float = None,
        source_type: str = "document"
    ) -> OntologyConcept:
        """
        Idempotent concept creation with cross-reference promotion.

        Returns existing concept if name+type+tenant match, otherwise creates new.
        Name is normalized to lowercase+stripped.

        Cross-reference logic:
        - If concept exists from "document" and new source is "code" → promote to "both"
        - If concept exists from "code" and new source is "document" → promote to "both"
        - If already "both" → no change
        This marks concepts validated by both BRD documents AND production code.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_or_create()")

        normalized_name = name.strip().lower()

        existing = db.query(self.model).filter(
            func.lower(self.model.name) == normalized_name,
            self.model.concept_type == concept_type,
            self.model.tenant_id == tenant_id
        ).first()

        if existing:
            changed = False
            # Update confidence if new score is higher
            if confidence_score and (existing.confidence_score is None or confidence_score > existing.confidence_score):
                existing.confidence_score = confidence_score
                changed = True
            # Cross-reference promotion: document+code → both
            if existing.source_type != source_type and existing.source_type != "both":
                existing.source_type = "both"
                changed = True
            if changed:
                db.commit()
                db.refresh(existing)
            return existing

        db_obj = self.model(
            name=name.strip(),
            concept_type=concept_type,
            description=description,
            confidence_score=confidence_score,
            source_type=source_type,
            tenant_id=tenant_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_source_type(
        self, db: Session, *, source_type: str, tenant_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[OntologyConcept]:
        """Get concepts filtered by source_type (document, code, both)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_source_type()")

        return db.query(self.model).filter(
            self.model.source_type == source_type,
            self.model.tenant_id == tenant_id,
            self.model.is_active == True
        ).offset(skip).limit(limit).all()

    def search_by_name(
        self, db: Session, *, query: str, tenant_id: int, limit: int = 20
    ) -> List[OntologyConcept]:
        """Search concepts by name (case-insensitive partial match)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for search_by_name()")

        return db.query(self.model).filter(
            func.lower(self.model.name).contains(query.strip().lower()),
            self.model.tenant_id == tenant_id,
            self.model.is_active == True
        ).limit(limit).all()

    def get_by_type(
        self, db: Session, *, concept_type: str, tenant_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[OntologyConcept]:
        """Get all concepts of a specific type."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_type()")

        return db.query(self.model).filter(
            self.model.concept_type == concept_type,
            self.model.tenant_id == tenant_id,
            self.model.is_active == True
        ).offset(skip).limit(limit).all()

    def get_with_relationships(
        self, db: Session, *, id: int, tenant_id: int
    ) -> Optional[OntologyConcept]:
        """Get a concept with all its incoming and outgoing relationships eager-loaded."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_with_relationships()")

        return db.query(self.model).filter(
            self.model.id == id,
            self.model.tenant_id == tenant_id
        ).options(
            joinedload(self.model.outgoing_relationships),
            joinedload(self.model.incoming_relationships)
        ).first()

    def get_all_active(
        self, db: Session, *, tenant_id: int
    ) -> List[OntologyConcept]:
        """Get all active concepts for a tenant (for graph building)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_all_active()")

        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.is_active == True
        ).all()

    def get_concept_types(
        self, db: Session, *, tenant_id: int
    ) -> List[str]:
        """Get all distinct concept types for a tenant."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_concept_types()")

        results = db.query(self.model.concept_type).filter(
            self.model.tenant_id == tenant_id,
            self.model.is_active == True
        ).distinct().all()
        return [r[0] for r in results]

    def count_by_tenant(self, db: Session, *, tenant_id: int) -> int:
        """Count all active concepts for a tenant."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for count_by_tenant()")

        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.is_active == True
        ).count()


ontology_concept = CRUDOntologyConcept(OntologyConcept)
