# This is the content for your NEW file at:
# backend/app/crud/crud_document.py

from typing import List
from sqlalchemy.orm import Session, selectinload

from app.crud.base import CRUDBase
from app.models.document import Document
from app.models.document_segment import DocumentSegment
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
        storage_path: str,
        tenant_id: int
    ) -> Document:
        """
        Create a new document in the database and associate it with an owner.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.

        Args:
            db: Database session
            obj_in: Document creation schema
            owner_id: Owner user ID
            storage_path: Path to stored document file
            tenant_id: REQUIRED tenant ID for multi-tenancy isolation

        Returns:
            Created document object
        """
        # CRITICAL VALIDATION: Ensure tenant_id is provided
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for document creation")

        # Convert the Pydantic schema object to a dictionary (Pydantic v2 compatible)
        obj_in_data = obj_in.model_dump()

        # Override owner_id, storage_path, and tenant_id from parameters
        obj_in_data["owner_id"] = owner_id
        obj_in_data["storage_path"] = storage_path
        obj_in_data["tenant_id"] = tenant_id  # SPRINT 2: Assign document to tenant

        # Create a new SQLAlchemy model instance
        db_obj = self.model(**obj_in_data)

        # Add the new object to the session and commit to the database
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> List[Document]:
        """
        Retrieve multiple documents from the database belonging to a specific owner.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        Documents are filtered by BOTH owner_id and tenant_id.

        Args:
            db: Database session
            owner_id: Owner user ID
            tenant_id: REQUIRED tenant ID for multi-tenancy isolation
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of documents belonging to the owner in the tenant
        """
        # CRITICAL VALIDATION: Ensure tenant_id is provided
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_multi_by_owner()")

        # FLAW-11-B FIX: Eager load segments to prevent N+1 queries
        # when dashboard/document list accesses segment counts or statuses
        return (
            db.query(self.model)
            .options(selectinload(Document.segments))
            .filter(
                Document.owner_id == owner_id,
                Document.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

# Create a single instance of the CRUDDocument class that we can import elsewhere
document = CRUDDocument(Document)
