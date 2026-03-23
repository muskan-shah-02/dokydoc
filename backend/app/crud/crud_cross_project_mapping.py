"""
CrossProjectMapping CRUD — Cross-Project Mapping Operations

Provides data access for the cross_project_mappings table which stores
explicit links between concepts in different projects.
"""

from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.crud.base import CRUDBase
from app.models.cross_project_mapping import CrossProjectMapping
from app.schemas.cross_project_mapping import CrossProjectMappingCreate, CrossProjectMappingUpdate


class CRUDCrossProjectMapping(CRUDBase[CrossProjectMapping, CrossProjectMappingCreate, CrossProjectMappingUpdate]):

    def create_mapping(
        self, db: Session, *,
        concept_a_id: int,
        concept_b_id: int,
        initiative_a_id: int,
        initiative_b_id: int,
        mapping_method: str,
        confidence_score: float,
        tenant_id: int,
        relationship_type: str = "shares_concept",
        status: str = "candidate",
        ai_reasoning: str = None,
    ) -> CrossProjectMapping:
        """
        Create a cross-project mapping. Idempotent — returns existing if
        the same concept pair already exists (in either direction).
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")

        # Check both directions (A→B or B→A)
        existing = db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            or_(
                (self.model.concept_a_id == concept_a_id) & (self.model.concept_b_id == concept_b_id),
                (self.model.concept_a_id == concept_b_id) & (self.model.concept_b_id == concept_a_id),
            )
        ).first()

        if existing:
            if confidence_score > existing.confidence_score:
                existing.confidence_score = confidence_score
                existing.mapping_method = mapping_method
                if ai_reasoning:
                    existing.ai_reasoning = ai_reasoning
                db.commit()
                db.refresh(existing)
            return existing

        db_obj = self.model(
            concept_a_id=concept_a_id,
            concept_b_id=concept_b_id,
            initiative_a_id=initiative_a_id,
            initiative_b_id=initiative_b_id,
            mapping_method=mapping_method,
            confidence_score=confidence_score,
            status=status,
            relationship_type=relationship_type,
            ai_reasoning=ai_reasoning,
            tenant_id=tenant_id,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_initiative_pair(
        self, db: Session, *, initiative_a_id: int, initiative_b_id: int,
        tenant_id: int, skip: int = 0, limit: int = 200
    ) -> List[CrossProjectMapping]:
        """Get all mappings between two specific projects."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            or_(
                (self.model.initiative_a_id == initiative_a_id) & (self.model.initiative_b_id == initiative_b_id),
                (self.model.initiative_a_id == initiative_b_id) & (self.model.initiative_b_id == initiative_a_id),
            )
        ).options(
            joinedload(self.model.concept_a),
            joinedload(self.model.concept_b),
        ).offset(skip).limit(limit).all()

    def get_by_initiative(
        self, db: Session, *, initiative_id: int, tenant_id: int,
        skip: int = 0, limit: int = 200
    ) -> List[CrossProjectMapping]:
        """Get all cross-project mappings involving a specific project."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            or_(
                self.model.initiative_a_id == initiative_id,
                self.model.initiative_b_id == initiative_id,
            )
        ).options(
            joinedload(self.model.concept_a),
            joinedload(self.model.concept_b),
        ).offset(skip).limit(limit).all()

    def get_all_for_tenant(
        self, db: Session, *, tenant_id: int, skip: int = 0, limit: int = 500
    ) -> List[CrossProjectMapping]:
        """Get all cross-project mappings for the entire tenant (for meta-graph)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
        ).options(
            joinedload(self.model.concept_a),
            joinedload(self.model.concept_b),
        ).offset(skip).limit(limit).all()

    def get_by_status(
        self, db: Session, *, status: str, tenant_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[CrossProjectMapping]:
        """Get cross-project mappings by status."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        return db.query(self.model).filter(
            self.model.status == status,
            self.model.tenant_id == tenant_id,
        ).options(
            joinedload(self.model.concept_a),
            joinedload(self.model.concept_b),
        ).offset(skip).limit(limit).all()

    def confirm_mapping(
        self, db: Session, *, mapping_id: int, tenant_id: int
    ) -> Optional[CrossProjectMapping]:
        """Confirm a candidate cross-project mapping."""
        mapping = self.get(db=db, id=mapping_id, tenant_id=tenant_id)
        if mapping and mapping.status == "candidate":
            mapping.status = "confirmed"
            db.commit()
            db.refresh(mapping)
        return mapping

    def reject_mapping(
        self, db: Session, *, mapping_id: int, tenant_id: int
    ) -> Optional[CrossProjectMapping]:
        """Reject a candidate cross-project mapping."""
        mapping = self.get(db=db, id=mapping_id, tenant_id=tenant_id)
        if mapping and mapping.status == "candidate":
            mapping.status = "rejected"
            db.commit()
            db.refresh(mapping)
        return mapping

    def count_by_tenant(self, db: Session, *, tenant_id: int) -> int:
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
        ).count()

    def delete_between_initiatives(
        self, db: Session, *, initiative_a_id: int, initiative_b_id: int,
        tenant_id: int
    ) -> int:
        """Delete all mappings between two projects (for re-run)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        count = db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            or_(
                (self.model.initiative_a_id == initiative_a_id) & (self.model.initiative_b_id == initiative_b_id),
                (self.model.initiative_a_id == initiative_b_id) & (self.model.initiative_b_id == initiative_a_id),
            )
        ).delete(synchronize_session=False)
        db.commit()
        return count


cross_project_mapping = CRUDCrossProjectMapping(CrossProjectMapping)
