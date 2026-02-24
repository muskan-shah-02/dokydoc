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
        source_type: str = "document", initiative_id: int = None
    ) -> OntologyConcept:
        """
        Idempotent concept creation within a SINGLE source layer.

        Deduplication matches on name + type + tenant + source_type + initiative_id.
        This keeps document-layer and code-layer concepts SEPARATE:
        - "User Authentication" (FEATURE, document) is a different concept from
          "User Authentication" (SYSTEM, code)
        - They live in different layers and are connected via bridge relationships
          created by the reconciliation pass, NOT by auto-merging.

        Within the SAME layer AND project, if a concept with the same name+type
        already exists, update confidence if higher.

        Cross-referencing between layers is handled by reconcile_document_code_concepts(),
        NOT here. This prevents:
        - Type collisions (FEATURE vs SYSTEM for the same name)
        - Description overwrites (losing provenance)
        - False matches across abstraction levels
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_or_create()")

        normalized_name = name.strip().lower()

        # Match within the SAME source layer AND project
        query = db.query(self.model).filter(
            func.lower(self.model.name) == normalized_name,
            self.model.concept_type == concept_type,
            self.model.tenant_id == tenant_id,
            self.model.source_type == source_type
        )
        if initiative_id is not None:
            query = query.filter(self.model.initiative_id == initiative_id)
        else:
            query = query.filter(self.model.initiative_id.is_(None))

        existing = query.first()

        if existing:
            # Update confidence if new score is higher
            if confidence_score and (existing.confidence_score is None or confidence_score > existing.confidence_score):
                existing.confidence_score = confidence_score
                db.commit()
                db.refresh(existing)
            return existing

        db_obj = self.model(
            name=name.strip(),
            concept_type=concept_type,
            description=description,
            confidence_score=confidence_score,
            source_type=source_type,
            tenant_id=tenant_id,
            initiative_id=initiative_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def promote_to_both(
        self, db: Session, *, concept_id: int, tenant_id: int
    ) -> Optional[OntologyConcept]:
        """
        Explicitly promote a concept to source_type='both'.
        Only called by the reconciliation pass when AI confirms a concept
        is genuinely the same thing in both document and code.
        """
        concept = db.query(self.model).filter(
            self.model.id == concept_id,
            self.model.tenant_id == tenant_id
        ).first()
        if concept and concept.source_type != "both":
            concept.source_type = "both"
            db.commit()
            db.refresh(concept)
        return concept

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
        self, db: Session, *, tenant_id: int, initiative_id: int = None
    ) -> List[OntologyConcept]:
        """
        Get all active concepts for a tenant (for graph building).
        If initiative_id is provided, returns concepts for that project
        PLUS shared/unscoped concepts (initiative_id IS NULL).
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_all_active()")

        query = db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.is_active == True
        )
        if initiative_id is not None:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    self.model.initiative_id == initiative_id,
                    self.model.initiative_id.is_(None)
                )
            )
        return query.all()

    def get_by_initiative(
        self, db: Session, *, initiative_id: int, tenant_id: int,
        skip: int = 0, limit: int = 500
    ) -> List[OntologyConcept]:
        """
        Get concepts scoped to a specific project.
        Returns project-specific concepts + shared/unscoped concepts (initiative_id IS NULL).
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_initiative()")

        from sqlalchemy import or_
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.is_active == True,
            or_(
                self.model.initiative_id == initiative_id,
                self.model.initiative_id.is_(None)
            )
        ).offset(skip).limit(limit).all()

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

    def count_by_tenant(self, db: Session, *, tenant_id: int, initiative_id: int = None) -> int:
        """Count all active concepts for a tenant, optionally scoped to a project."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for count_by_tenant()")

        query = db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.is_active == True
        )
        if initiative_id is not None:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    self.model.initiative_id == initiative_id,
                    self.model.initiative_id.is_(None)
                )
            )
        return query.count()


ontology_concept = CRUDOntologyConcept(OntologyConcept)
