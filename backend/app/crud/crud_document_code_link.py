# This is the content for your NEW file at:
# backend/app/crud/crud_document_code_link.py

from typing import List
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.document_code_link import DocumentCodeLink
from app.schemas.document_code_link import DocumentCodeLinkCreate, DocumentCodeLinkUpdate

class CRUDDocumentCodeLink(CRUDBase[DocumentCodeLink, DocumentCodeLinkCreate, DocumentCodeLinkUpdate]):
    """
    CRUD functions for the DocumentCodeLink model.
    """

    def get_multi_by_document(
        self, db: Session, *, document_id: int, tenant_id: int
    ) -> List[DocumentCodeLink]:
        """
        Retrieve all links associated with a specific document.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_multi_by_document()")

        return (
            db.query(self.model)
            .filter(
                DocumentCodeLink.document_id == document_id,
                DocumentCodeLink.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
            )
            .all()
        )

    def remove_link(
        self, db: Session, *, document_id: int, code_component_id: int, tenant_id: int
    ) -> DocumentCodeLink | None:
        """
        Remove a specific link between a document and a code component.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for remove_link()")

        obj = db.query(self.model).filter(
            DocumentCodeLink.document_id == document_id,
            DocumentCodeLink.code_component_id == code_component_id,
            DocumentCodeLink.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
        ).first()

        if obj:
            db.delete(obj)
            db.commit()

        return obj


# Create a single instance that we can import and use in our API endpoints.
document_code_link = CRUDDocumentCodeLink(DocumentCodeLink)

