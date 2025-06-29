# This is the content for your NEW file at:
# backend/app/crud/crud_code_component.py

from typing import List
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.code_component import CodeComponent
from app.schemas.code_component import CodeComponentCreate, CodeComponentUpdate

class CRUDCodeComponent(CRUDBase[CodeComponent, CodeComponentCreate, CodeComponentUpdate]):
    """
    CRUD functions for the CodeComponent model.
    """

    def create_with_owner(
        self, 
        db: Session, 
        *, 
        obj_in: CodeComponentCreate, 
        owner_id: int
    ) -> CodeComponent:
        """
        Create a new code component and associate it with an owner.
        """
        obj_in_data = obj_in.dict()
        db_obj = self.model(**obj_in_data, owner_id=owner_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[CodeComponent]:
        """
        Retrieve multiple code components belonging to a specific owner.
        """
        return (
            db.query(self.model)
            .filter(CodeComponent.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

# Create a single instance that we can import and use in our API endpoints.
code_component = CRUDCodeComponent(CodeComponent)
