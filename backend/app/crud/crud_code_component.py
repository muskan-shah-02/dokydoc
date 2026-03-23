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
        owner_id: int,
        tenant_id: int
    ) -> CodeComponent:
        """
        Create a new code component and associate it with an owner.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.

        Args:
            db: Database session
            obj_in: Code component creation schema
            owner_id: Owner user ID
            tenant_id: REQUIRED tenant ID for multi-tenancy isolation

        Returns:
            Created code component object
        """
        # CRITICAL VALIDATION: Ensure tenant_id is provided
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for code component creation")

        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data, owner_id=owner_id, tenant_id=tenant_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> List[CodeComponent]:
        """
        Retrieve multiple code components belonging to a specific owner.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.

        Args:
            db: Database session
            owner_id: Owner user ID
            tenant_id: REQUIRED tenant ID for multi-tenancy isolation
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of code components belonging to the owner in the tenant
        """
        # CRITICAL VALIDATION: Ensure tenant_id is provided
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_multi_by_owner()")

        return (
            db.query(self.model)
            .filter(
                CodeComponent.owner_id == owner_id,
                CodeComponent.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
    # --- NEW: Safe Deletion Method ---
    def remove_with_links(self, db: Session, *, id: int, tenant_id: int) -> CodeComponent:
        """
        Safely deletes a code component and its associated links.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.

        This method first deletes all entries in the document_code_links table
        that reference this component (within the same tenant), satisfying the foreign key constraint.
        Then, it deletes the component itself.

        Args:
            db: Database session
            id: Code component ID to delete
            tenant_id: REQUIRED tenant ID for multi-tenancy isolation

        Returns:
            Deleted code component object
        """
        # CRITICAL VALIDATION: Ensure tenant_id is provided
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for remove_with_links()")

        # Step 1: Delete all associated links (scoped to tenant)
        db.query(DocumentCodeLink).filter(
            DocumentCodeLink.code_component_id == id,
            DocumentCodeLink.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
        ).delete()

        # Step 2: Delete the component itself using the base remove method (with tenant_id)
        component = super().remove(db=db, id=id, tenant_id=tenant_id)

        db.commit()
        return component
# Create a single instance that we can import and use in our API endpoints.
code_component = CRUDCodeComponent(CodeComponent)
