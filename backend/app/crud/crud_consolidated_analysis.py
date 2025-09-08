from typing import Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models import ConsolidatedAnalysis


class CRUDConsolidatedAnalysis(CRUDBase[ConsolidatedAnalysis, dict, dict]):
    def get_by_document(self, db: Session, *, document_id: int) -> Optional[ConsolidatedAnalysis]:
        return (
            db.query(ConsolidatedAnalysis)
            .filter(ConsolidatedAnalysis.document_id == document_id)
            .first()
        )

    def upsert(self, db: Session, *, document_id: int, data: dict) -> ConsolidatedAnalysis:
        existing = self.get_by_document(db, document_id=document_id)
        if existing:
            existing.data = data
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing
        created = ConsolidatedAnalysis(document_id=document_id, data=data)
        db.add(created)
        db.commit()
        db.refresh(created)
        return created


crud_consolidated_analysis = CRUDConsolidatedAnalysis(ConsolidatedAnalysis)


