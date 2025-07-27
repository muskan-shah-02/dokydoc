# This is the updated content for your file at:
# backend/app/crud/crud_mismatch.py

from typing import List
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.mismatch import Mismatch
from app.schemas.mismatch import MismatchCreate, MismatchUpdate

class CRUDMismatch(CRUDBase[Mismatch, MismatchCreate, MismatchUpdate]):
    """
    CRUD functions for the Mismatch model.
    """

    def create_with_owner(
        self, db: Session, *, obj_in: MismatchCreate, owner_id: int
    ) -> Mismatch:
        """Create a new mismatch and associate it with an owner."""
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data, owner_id=owner_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[Mismatch]:
        """Retrieve multiple mismatches for a specific owner with eager loading."""
        return (
            db.query(self.model)
            .filter(Mismatch.owner_id == owner_id)
            .options(
                joinedload(self.model.document),
                joinedload(self.model.code_component)
            )
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # --- NEW: Helper method for the ValidationService ---
    def remove_by_link(self, db: Session, *, document_id: int, code_component_id: int) -> int:
        """
        Deletes all mismatches associated with a specific document-code link.
        Returns the number of mismatches deleted.
        """
        num_deleted = db.query(self.model).filter(
            self.model.document_id == document_id,
            self.model.code_component_id == code_component_id
        ).delete()
        db.commit()
        return num_deleted

# A single, reusable instance of our CRUD class.
mismatch = CRUDMismatch(Mismatch)
