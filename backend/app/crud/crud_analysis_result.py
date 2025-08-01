# This is the content for your NEW file at:
# backend/app/crud/crud_analysis_result.py

from typing import List
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
        db_obj = self.model(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_document(
        self, db: Session, *, document_id: int, skip: int = 0, limit: int = 100
    ) -> List[AnalysisResult]:
        """
        Retrieve all analysis results for a specific document.
        """
        return (
            db.query(self.model)
            .filter(AnalysisResult.document_id == document_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

# Create a single instance that we can import and use in our API endpoints.
analysis_result = CRUDAnalysisResult(AnalysisResult)
