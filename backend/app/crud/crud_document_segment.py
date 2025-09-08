from typing import List, Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.document_segment import DocumentSegment
from app.schemas.document_segment import DocumentSegmentCreate, DocumentSegmentUpdate


class CRUDDocumentSegment(CRUDBase[DocumentSegment, DocumentSegmentCreate, DocumentSegmentUpdate]):
    def get_multi_by_document(
        self, db: Session, *, document_id: int, skip: int = 0, limit: int = 100
    ) -> List[DocumentSegment]:
        """
        Get all segments for a specific document.
        """
        return db.query(DocumentSegment).filter(
            DocumentSegment.document_id == document_id
        ).offset(skip).limit(limit).all()

    def get_by_document(
        self, db: Session, *, document_id: int
    ) -> List[DocumentSegment]:
        """
        Get all segments for a specific document (alias for get_multi_by_document).
        """
        return self.get_multi_by_document(db=db, document_id=document_id)

    def get_by_document_and_type(
        self, db: Session, *, document_id: int, segment_type: str
    ) -> Optional[DocumentSegment]:
        """
        Get a specific segment by document ID and segment type.
        """
        return db.query(DocumentSegment).filter(
            DocumentSegment.document_id == document_id,
            DocumentSegment.segment_type == segment_type
        ).first()

    def delete_by_document(self, db: Session, *, document_id: int) -> int:
        """
        Delete all segments for a specific document.
        Returns the number of deleted segments.
        """
        deleted_count = db.query(DocumentSegment).filter(
            DocumentSegment.document_id == document_id
        ).delete()
        db.commit()
        return deleted_count


document_segment = CRUDDocumentSegment(DocumentSegment)
