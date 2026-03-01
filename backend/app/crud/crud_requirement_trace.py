"""
CRUD operations for RequirementTrace.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.requirement_trace import RequirementTrace


class CRUDRequirementTrace:

    def __init__(self):
        self.model = RequirementTrace

    def get_by_document(
        self, db: Session, *, document_id: int, tenant_id: int
    ) -> List[RequirementTrace]:
        """Get all requirement traces for a document."""
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.document_id == document_id,
        ).order_by(self.model.requirement_key).all()

    def get_by_initiative(
        self, db: Session, *, initiative_id: int, tenant_id: int
    ) -> List[RequirementTrace]:
        """Get all requirement traces for an initiative/project."""
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.initiative_id == initiative_id,
        ).order_by(self.model.document_id, self.model.requirement_key).all()

    def upsert(
        self, db: Session, *, tenant_id: int, document_id: int,
        requirement_key: str, requirement_text: str,
        initiative_id: int = None,
        code_concept_ids: list = None,
        code_component_ids: list = None,
        coverage_status: str = "not_covered",
        validation_status: str = "pending",
        validation_details: dict = None,
    ) -> RequirementTrace:
        """Create or update a requirement trace."""
        existing = db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.document_id == document_id,
            self.model.requirement_key == requirement_key,
        ).first()

        if existing:
            existing.requirement_text = requirement_text
            existing.code_concept_ids = code_concept_ids or []
            existing.code_component_ids = code_component_ids or []
            existing.coverage_status = coverage_status
            existing.validation_status = validation_status
            if validation_details is not None:
                existing.validation_details = validation_details
            db.add(existing)
            db.flush()
            return existing

        trace = self.model(
            tenant_id=tenant_id,
            initiative_id=initiative_id,
            document_id=document_id,
            requirement_key=requirement_key,
            requirement_text=requirement_text,
            code_concept_ids=code_concept_ids or [],
            code_component_ids=code_component_ids or [],
            coverage_status=coverage_status,
            validation_status=validation_status,
            validation_details=validation_details,
        )
        db.add(trace)
        db.flush()
        return trace

    def get_coverage_summary(
        self, db: Session, *, document_id: int, tenant_id: int
    ) -> dict:
        """Get coverage summary stats for a document."""
        traces = self.get_by_document(db, document_id=document_id, tenant_id=tenant_id)
        total = len(traces)
        if total == 0:
            return {"total": 0, "covered": 0, "partial": 0, "not_covered": 0, "contradicted": 0, "coverage_pct": 0}

        covered = sum(1 for t in traces if t.coverage_status == "fully_covered")
        partial = sum(1 for t in traces if t.coverage_status == "partially_covered")
        not_covered = sum(1 for t in traces if t.coverage_status == "not_covered")
        contradicted = sum(1 for t in traces if t.coverage_status == "contradicted")

        return {
            "total": total,
            "covered": covered,
            "partial": partial,
            "not_covered": not_covered,
            "contradicted": contradicted,
            "coverage_pct": round((covered + partial * 0.5) / total * 100, 1) if total > 0 else 0,
        }


requirement_trace = CRUDRequirementTrace()
