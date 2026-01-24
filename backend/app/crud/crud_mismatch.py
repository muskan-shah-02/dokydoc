# This is the updated content for your file at:
# backend/app/crud/crud_mismatch.py

from typing import List
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.mismatch import Mismatch
from app.models.document_code_link import DocumentCodeLink
from app.schemas.mismatch import MismatchCreate, MismatchUpdate

class CRUDMismatch(CRUDBase[Mismatch, MismatchCreate, MismatchUpdate]):
    """
    CRUD functions for the Mismatch model.
    """

    def create_with_owner(
        self, db: Session, *, obj_in: MismatchCreate, owner_id: int, tenant_id: int
    ) -> Mismatch:
        """
        Create a new mismatch and associate it with an owner.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for mismatch creation")

        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data, owner_id=owner_id, tenant_id=tenant_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> List[Mismatch]:
        """
        Retrieve multiple mismatches for a specific owner with eager loading.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_multi_by_owner()")

        return (
            db.query(self.model)
            .filter(
                Mismatch.owner_id == owner_id,
                Mismatch.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
            )
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
    def remove_by_link(self, db: Session, *, document_id: int, code_component_id: int, tenant_id: int) -> int:
        """
        Deletes all mismatches associated with a specific document-code link.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.

        Returns the number of mismatches deleted.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for remove_by_link()")

        num_deleted = db.query(self.model).filter(
            self.model.document_id == document_id,
            self.model.code_component_id == code_component_id,
            self.model.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
        ).delete()
        db.commit()
        return num_deleted

    def create_with_link(
        self,
        db: Session,
        *,
        obj_in: dict,
        link_id: int,
        owner_id: int,
        tenant_id: int
    ) -> Mismatch:
        """
        Create mismatch from document-code link.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for create_with_link()")

        link = db.query(DocumentCodeLink).filter(
            DocumentCodeLink.id == link_id,
            DocumentCodeLink.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
        ).first()
        if not link:
            raise ValueError(f"DocumentCodeLink {link_id} not found in tenant {tenant_id}")

        mismatch_schema = MismatchCreate(
            **obj_in,
            document_id=link.document_id,
            code_component_id=link.code_component_id
        )

        db_obj = self.model(**mismatch_schema.model_dump(), owner_id=owner_id, tenant_id=tenant_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

# A single, reusable instance of our CRUD class.
mismatch = CRUDMismatch(Mismatch)
