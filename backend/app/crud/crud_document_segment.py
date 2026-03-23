from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.document_segment import DocumentSegment
from app.schemas.document_segment import DocumentSegmentCreate, DocumentSegmentUpdate


class CRUDDocumentSegment(CRUDBase[DocumentSegment, DocumentSegmentCreate, DocumentSegmentUpdate]):
    def get_multi_by_document(
        self, db: Session, *, document_id: int, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> List[DocumentSegment]:
        """
        Get all segments for a specific document.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        PERFORMANCE: Eager loads analysis_results to prevent N+1 queries.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_multi_by_document()")

        return db.query(DocumentSegment)\
            .options(joinedload(DocumentSegment.analysis_results))\
            .filter(
                DocumentSegment.document_id == document_id,
                DocumentSegment.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
            ).offset(skip).limit(limit).all()

    def get_by_document(
        self, db: Session, *, document_id: int, tenant_id: int
    ) -> List[DocumentSegment]:
        """
        Get all segments for a specific document (alias for get_multi_by_document).

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        """
        return self.get_multi_by_document(db=db, document_id=document_id, tenant_id=tenant_id)

    def get_by_document_and_type(
        self, db: Session, *, document_id: int, segment_type: str, tenant_id: int
    ) -> Optional[DocumentSegment]:
        """
        Get a specific segment by document ID and segment type.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_document_and_type()")

        return db.query(DocumentSegment).filter(
            DocumentSegment.document_id == document_id,
            DocumentSegment.segment_type == segment_type,
            DocumentSegment.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
        ).first()

    def delete_by_document(self, db: Session, *, document_id: int, tenant_id: int) -> int:
        """
        Delete all segments for a specific document.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.

        Returns the number of deleted segments.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for delete_by_document()")

        deleted_count = db.query(DocumentSegment).filter(
            DocumentSegment.document_id == document_id,
            DocumentSegment.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
        ).delete()
        db.commit()
        return deleted_count


document_segment = CRUDDocumentSegment(DocumentSegment)
