from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.initiative import Initiative
from app.schemas.initiative import InitiativeCreate, InitiativeUpdate


class CRUDInitiative(CRUDBase[Initiative, InitiativeCreate, InitiativeUpdate]):

    def create_with_owner(
        self, db: Session, *, obj_in: InitiativeCreate, owner_id: int, tenant_id: int
    ) -> Initiative:
        """Create a new initiative with owner assignment."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for initiative creation")

        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data, owner_id=owner_id, tenant_id=tenant_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_with_assets(
        self, db: Session, *, id: int, tenant_id: int
    ) -> Optional[Initiative]:
        """Get initiative with all linked assets eager-loaded."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_with_assets()")

        return db.query(self.model).filter(
            self.model.id == id,
            self.model.tenant_id == tenant_id
        ).options(
            joinedload(self.model.assets),
            joinedload(self.model.owner)
        ).first()

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, tenant_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[Initiative]:
        """Get all initiatives owned by a user."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_multi_by_owner()")

        return db.query(self.model).filter(
            self.model.owner_id == owner_id,
            self.model.tenant_id == tenant_id
        ).options(
            joinedload(self.model.assets)
        ).order_by(self.model.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_status(
        self, db: Session, *, status: str, tenant_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[Initiative]:
        """Get initiatives filtered by status."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_status()")

        return db.query(self.model).filter(
            self.model.status == status,
            self.model.tenant_id == tenant_id
        ).offset(skip).limit(limit).all()


initiative = CRUDInitiative(Initiative)
