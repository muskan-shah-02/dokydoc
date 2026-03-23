from typing import Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models import ConsolidatedAnalysis


class CRUDConsolidatedAnalysis(CRUDBase[ConsolidatedAnalysis, dict, dict]):
    def get_by_document(self, db: Session, *, document_id: int, tenant_id: int) -> Optional[ConsolidatedAnalysis]:
        """
        Get consolidated analysis for a specific document.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_document()")

        return (
            db.query(ConsolidatedAnalysis)
            .filter(
                ConsolidatedAnalysis.document_id == document_id,
                ConsolidatedAnalysis.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
            )
            .first()
        )

    def upsert(self, db: Session, *, document_id: int, data: dict, tenant_id: int) -> ConsolidatedAnalysis:
        """
        Create or update consolidated analysis for a document.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for upsert()")

        existing = self.get_by_document(db, document_id=document_id, tenant_id=tenant_id)
        if existing:
            existing.data = data
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing
        created = ConsolidatedAnalysis(document_id=document_id, data=data, tenant_id=tenant_id)
        db.add(created)
        db.commit()
        db.refresh(created)
        return created


crud_consolidated_analysis = CRUDConsolidatedAnalysis(ConsolidatedAnalysis)


