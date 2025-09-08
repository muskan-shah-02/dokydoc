# This is the content for your NEW file at:
# backend/app/crud/crud_document.py

from typing import List
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.document import Document
from app.schemas.document import DocumentCreate, DocumentUpdate

class CRUDDocument(CRUDBase[Document, DocumentCreate, DocumentUpdate]):
    """
    CRUD functions for Document model.
    """

    def create_with_owner(
        self, 
        db: Session, 
        *, 
        obj_in: DocumentCreate, 
        owner_id: int, 
        storage_path: str
    ) -> Document:
        """
        Create a new document in the database and associate it with an owner.
        """
        # Convert the Pydantic schema object to a dictionary (Pydantic v2 compatible)
        obj_in_data = obj_in.model_dump()
        
        # Override owner_id and storage_path from parameters
        obj_in_data["owner_id"] = owner_id
        obj_in_data["storage_path"] = storage_path
        
        # Create a new SQLAlchemy model instance
        db_obj = self.model(**obj_in_data)
        
        # Add the new object to the session and commit to the database
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[Document]:
        """
        Retrieve multiple documents from the database belonging to a specific owner.
        """
        return (
            db.query(self.model)
            .filter(Document.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

# Create a single instance of the CRUDDocument class that we can import elsewhere
document = CRUDDocument(Document)
