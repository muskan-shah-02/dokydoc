# This is the content for your NEW file at:
# backend/app/crud/crud_mismatch.py

from typing import List
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.mismatch import Mismatch
from app.schemas.mismatch import MismatchCreate, MismatchUpdate

class CRUDMismatch(CRUDBase[Mismatch, MismatchCreate, MismatchUpdate]):
    """
    CRUD functions for the Mismatch model.
    """
    
    def get_multi_by_document(
        self, db: Session, *, document_id: int, skip: int = 0, limit: int = 100
    ) -> List[Mismatch]:
        """
        Retrieve all mismatches associated with a specific document.
        """
        return (
            db.query(self.model)
            .filter(Mismatch.document_id == document_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

# Create a single instance that we can import and use in our API endpoints.
mismatch = CRUDMismatch(Mismatch)
