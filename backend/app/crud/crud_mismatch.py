# This is the final, verified content for:
# backend/app/crud/crud_mismatch.py

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.mismatch import Mismatch
from app.schemas.mismatch import MismatchCreate, MismatchUpdate

class CRUDMismatch(CRUDBase[Mismatch, MismatchCreate, MismatchUpdate]):
    def get_by_details(self, db: Session, *, obj_in: MismatchCreate) -> Mismatch | None:
        """
        Checks if a specific mismatch already exists to avoid duplicates.
        """
        return db.query(self.model).filter(
            self.model.document_id == obj_in.document_id,
            self.model.code_component_id == obj_in.code_component_id,
            self.model.mismatch_type == obj_in.mismatch_type
        ).first()

mismatch = CRUDMismatch(Mismatch)