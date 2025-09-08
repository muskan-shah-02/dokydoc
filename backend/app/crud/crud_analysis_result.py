# This is the content for your NEW file at:
# backend/app/crud/crud_analysis_result.py

from typing import List, Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.analysis_result import AnalysisResult
from app.schemas.analysis_result import AnalysisResultCreate

class CRUDAnalysisResult(CRUDBase[AnalysisResult, AnalysisResultCreate, None]):
    """
    CRUD functions for the AnalysisResult model.
    """

    def create_for_document(
        self, 
        db: Session, 
        *, 
        obj_in: AnalysisResultCreate
    ) -> AnalysisResult:
        """
        Create a new analysis result for a specific document.
        """
        db_obj = self.model(**obj_in.model_dump())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_document(
        self, db: Session, *, document_id: int
    ) -> List[AnalysisResult]:
        """
        Retrieve all analysis results associated with a specific document.
        """
        return db.query(self.model).filter(self.model.document_id == document_id).all()

    def get_by_segment(
        self, db: Session, *, segment_id: int
    ) -> Optional[AnalysisResult]:
        """
        Retrieve analysis result for a specific segment.
        """
        return db.query(self.model).filter(self.model.segment_id == segment_id).first()

    def delete_by_segment(self, db: Session, *, segment_id: int) -> int:
        """
        Delete analysis result for a specific segment.
        Returns the number of deleted analysis results.
        """
        deleted_count = db.query(self.model).filter(self.model.segment_id == segment_id).delete()
        db.commit()
        return deleted_count

# Create a single instance that we can import and use in our API endpoints.
analysis_result = CRUDAnalysisResult(AnalysisResult)
