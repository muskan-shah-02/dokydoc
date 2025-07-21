# This is the content for your NEW file at:
# backend/app/crud/crud_code_component.py

from typing import List
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.code_component import CodeComponent
from app.schemas.code_component import CodeComponentCreate, CodeComponentUpdate
from app.models.document_code_link import DocumentCodeLink

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
    # --- NEW: Safe Deletion Method ---
    def remove_with_links(self, db: Session, *, id: int) -> CodeComponent:
        """
        Safely deletes a code component and its associated links.
        
        This method first deletes all entries in the document_code_links table
        that reference this component, satisfying the foreign key constraint.
        Then, it deletes the component itself.
        """
        # Step 1: Delete all associated links
        db.query(DocumentCodeLink).filter(DocumentCodeLink.code_component_id == id).delete()
        
        # Step 2: Delete the component itself using the base remove method
        component = super().remove(db=db, id=id)
        
        db.commit()
        return component
# Create a single instance that we can import and use in our API endpoints.
code_component = CRUDCodeComponent(CodeComponent)
