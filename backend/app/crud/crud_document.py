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

    def build_owner_query(
        self, db: Session, *, owner_id: int, tenant_id: int,
    ):
        """Build a filtered query for owner documents (without ordering/pagination)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for build_owner_query()")

        return (
            db.query(self.model)
            .options(selectinload(Document.segments))
            .filter(
                Document.owner_id == owner_id,
                Document.tenant_id == tenant_id,
            )
        )

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> List[Document]:
        """Retrieve documents belonging to a specific owner (offset-based, kept for backward compat)."""
        query = self.build_owner_query(db=db, owner_id=owner_id, tenant_id=tenant_id)
        return query.offset(skip).limit(limit).all()

    def build_initiative_query(
        self, db: Session, *, initiative_id: int, tenant_id: int,
    ):
        """Build a filtered query for initiative documents (without ordering/pagination)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for build_initiative_query()")

        from app.models.initiative_asset import InitiativeAsset
        asset_ids = db.query(InitiativeAsset.asset_id).filter(
            InitiativeAsset.initiative_id == initiative_id,
            InitiativeAsset.asset_type == "DOCUMENT",
            InitiativeAsset.tenant_id == tenant_id,
            InitiativeAsset.is_active == True,
        ).subquery()

        return (
            db.query(self.model)
            .options(selectinload(Document.segments))
            .filter(
                self.model.id.in_(asset_ids),
                self.model.tenant_id == tenant_id,
            )
        )

    def get_by_initiative(
        self, db: Session, *, initiative_id: int, tenant_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[Document]:
        """Get documents linked to a specific initiative (offset-based, kept for backward compat)."""
        query = self.build_initiative_query(db=db, initiative_id=initiative_id, tenant_id=tenant_id)
        return query.offset(skip).limit(limit).all()

# Create a single instance of the CRUDDocument class that we can import elsewhere
document = CRUDDocument(Document)
