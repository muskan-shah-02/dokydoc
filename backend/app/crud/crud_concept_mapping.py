"""
ConceptMapping CRUD — Cross-Graph Mapping Operations

Provides data access for the ConceptMapping table which stores
explicit links between document-graph and code-graph concepts.
"""

from typing import List, Optional, Dict
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func

from app.crud.base import CRUDBase
from app.models.concept_mapping import ConceptMapping
from app.models.ontology_concept import OntologyConcept
from app.schemas.concept_mapping import ConceptMappingCreate, ConceptMappingUpdate


class CRUDConceptMapping(CRUDBase[ConceptMapping, ConceptMappingCreate, ConceptMappingUpdate]):

    def create_mapping(
        self, db: Session, *,
        document_concept_id: int,
        code_concept_id: int,
        mapping_method: str,
        confidence_score: float,
        tenant_id: int,
        relationship_type: str = "implements",
        status: str = "candidate",
        ai_reasoning: str = None,
    ) -> ConceptMapping:
        """
        Create a cross-graph mapping. Idempotent — returns existing if
        the same doc+code pair already exists for this tenant.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for create_mapping()")

        existing = db.query(self.model).filter(
            self.model.document_concept_id == document_concept_id,
            self.model.code_concept_id == code_concept_id,
            self.model.tenant_id == tenant_id,
        ).first()

        if existing:
            # Update confidence if higher
            if confidence_score > existing.confidence_score:
                existing.confidence_score = confidence_score
                existing.mapping_method = mapping_method
                if ai_reasoning:
                    existing.ai_reasoning = ai_reasoning
                db.commit()
                db.refresh(existing)
            return existing

        db_obj = self.model(
            document_concept_id=document_concept_id,
            code_concept_id=code_concept_id,
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

    def get_by_document_concept(
        self, db: Session, *, document_concept_id: int, tenant_id: int
    ) -> List[ConceptMapping]:
        """Get all code mappings for a document concept."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        return db.query(self.model).filter(
            self.model.document_concept_id == document_concept_id,
            self.model.tenant_id == tenant_id,
        ).options(
            joinedload(self.model.code_concept)
        ).all()

    def get_by_code_concept(
        self, db: Session, *, code_concept_id: int, tenant_id: int
    ) -> List[ConceptMapping]:
        """Get all document mappings for a code concept."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        return db.query(self.model).filter(
            self.model.code_concept_id == code_concept_id,
            self.model.tenant_id == tenant_id,
        ).options(
            joinedload(self.model.document_concept)
        ).all()

    def get_by_status(
        self, db: Session, *, status: str, tenant_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[ConceptMapping]:
        """Get mappings by status (candidate, confirmed, rejected)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        return db.query(self.model).filter(
            self.model.status == status,
            self.model.tenant_id == tenant_id,
        ).options(
            joinedload(self.model.document_concept),
            joinedload(self.model.code_concept),
        ).offset(skip).limit(limit).all()

    def get_confirmed(
        self, db: Session, *, tenant_id: int
    ) -> List[ConceptMapping]:
        """Get all confirmed mappings for a tenant."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        return db.query(self.model).filter(
            self.model.status == "confirmed",
            self.model.tenant_id == tenant_id,
        ).options(
            joinedload(self.model.document_concept),
            joinedload(self.model.code_concept),
        ).all()

    def get_contradictions(
        self, db: Session, *, tenant_id: int
    ) -> List[ConceptMapping]:
        """Get all contradiction mappings for a tenant."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        return db.query(self.model).filter(
            self.model.relationship_type == "contradicts",
            self.model.tenant_id == tenant_id,
        ).options(
            joinedload(self.model.document_concept),
            joinedload(self.model.code_concept),
        ).all()

    def get_unmapped_document_concepts(
        self, db: Session, *, tenant_id: int
    ) -> List[OntologyConcept]:
        """
        Get document concepts that have NO mapping to any code concept.
        These are "gaps" — requirements with no implementation.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")

        mapped_doc_ids = db.query(self.model.document_concept_id).filter(
            self.model.tenant_id == tenant_id,
            self.model.status != "rejected",
        ).subquery()

        return db.query(OntologyConcept).filter(
            OntologyConcept.tenant_id == tenant_id,
            OntologyConcept.source_type == "document",
            OntologyConcept.is_active == True,
            ~OntologyConcept.id.in_(mapped_doc_ids),
        ).all()

    def get_unmapped_code_concepts(
        self, db: Session, *, tenant_id: int
    ) -> List[OntologyConcept]:
        """
        Get code concepts that have NO mapping to any document concept.
        These are "undocumented" — features with no BRD/SRS backing.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")

        mapped_code_ids = db.query(self.model.code_concept_id).filter(
            self.model.tenant_id == tenant_id,
            self.model.status != "rejected",
        ).subquery()

        return db.query(OntologyConcept).filter(
            OntologyConcept.tenant_id == tenant_id,
            OntologyConcept.source_type == "code",
            OntologyConcept.is_active == True,
            ~OntologyConcept.id.in_(mapped_code_ids),
        ).all()

    def confirm_mapping(
        self, db: Session, *, mapping_id: int, tenant_id: int
    ) -> Optional[ConceptMapping]:
        """Confirm a candidate mapping."""
        mapping = self.get(db=db, id=mapping_id, tenant_id=tenant_id)
        if mapping and mapping.status == "candidate":
            mapping.status = "confirmed"
            db.commit()
            db.refresh(mapping)
        return mapping

    def reject_mapping(
        self, db: Session, *, mapping_id: int, tenant_id: int
    ) -> Optional[ConceptMapping]:
        """Reject a candidate mapping."""
        mapping = self.get(db=db, id=mapping_id, tenant_id=tenant_id)
        if mapping and mapping.status == "candidate":
            mapping.status = "rejected"
            db.commit()
            db.refresh(mapping)
        return mapping

    def submit_feedback(
        self, db: Session, *,
        mapping_id: int,
        tenant_id: int,
        action: str,
        user_id: int,
        comment: Optional[str] = None,
    ) -> Optional[ConceptMapping]:
        """Submit feedback (confirm/reject) with optional comment and user tracking."""
        mapping = self.get(db=db, id=mapping_id, tenant_id=tenant_id)
        if not mapping:
            return None

        if action == "confirm":
            mapping.status = "confirmed"
        elif action == "reject":
            mapping.status = "rejected"
        else:
            return None

        mapping.feedback_by_id = user_id
        mapping.feedback_comment = comment
        mapping.feedback_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(mapping)
        return mapping

    def get_feedback_stats(
        self, db: Session, *, tenant_id: int
    ) -> Dict:
        """Get aggregated feedback statistics for threshold tuning."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")

        all_with_feedback = db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.feedback_by_id.isnot(None),
        ).all()

        total_feedback = len(all_with_feedback)
        confirmed_count = sum(1 for m in all_with_feedback if m.status == "confirmed")
        rejected_count = sum(1 for m in all_with_feedback if m.status == "rejected")

        # Avg confidence by method for confirmed vs rejected
        stats_by_method = {}
        for method in ("exact", "fuzzy", "ai_validated"):
            method_mappings = [m for m in all_with_feedback if m.mapping_method == method]
            if method_mappings:
                confirmed_scores = [m.confidence_score for m in method_mappings if m.status == "confirmed"]
                rejected_scores = [m.confidence_score for m in method_mappings if m.status == "rejected"]
                stats_by_method[method] = {
                    "total": len(method_mappings),
                    "confirmed": len(confirmed_scores),
                    "rejected": len(rejected_scores),
                    "avg_confirmed_confidence": round(sum(confirmed_scores) / len(confirmed_scores), 3) if confirmed_scores else None,
                    "avg_rejected_confidence": round(sum(rejected_scores) / len(rejected_scores), 3) if rejected_scores else None,
                }

        return {
            "total_feedback": total_feedback,
            "confirmed": confirmed_count,
            "rejected": rejected_count,
            "acceptance_rate": round(confirmed_count / total_feedback, 3) if total_feedback > 0 else None,
            "by_method": stats_by_method,
        }

    def count_by_tenant(self, db: Session, *, tenant_id: int) -> int:
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
        ).count()

    def delete_all_for_tenant(self, db: Session, *, tenant_id: int) -> int:
        """Delete all mappings for a tenant (used before full re-mapping)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")
        count = db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
        ).delete()
        db.commit()
        return count


concept_mapping = CRUDConceptMapping(ConceptMapping)
