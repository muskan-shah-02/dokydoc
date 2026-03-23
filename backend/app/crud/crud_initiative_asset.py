from typing import List, Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.initiative_asset import InitiativeAsset
from app.schemas.initiative import InitiativeAssetCreate, InitiativeAssetUpdate


class CRUDInitiativeAsset(CRUDBase[InitiativeAsset, InitiativeAssetCreate, InitiativeAssetUpdate]):

    def create_asset(
        self, db: Session, *, obj_in: InitiativeAssetCreate, tenant_id: int
    ) -> InitiativeAsset:
        """Link an asset (document or repository) to an initiative."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for create_asset()")

        # Check for duplicate link
        existing = db.query(self.model).filter(
            self.model.initiative_id == obj_in.initiative_id,
            self.model.asset_type == obj_in.asset_type,
            self.model.asset_id == obj_in.asset_id,
            self.model.tenant_id == tenant_id
        ).first()

        if existing:
            if not existing.is_active:
                existing.is_active = True
                db.commit()
                db.refresh(existing)
            return existing

        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data, tenant_id=tenant_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_initiative(
        self, db: Session, *, initiative_id: int, tenant_id: int
    ) -> List[InitiativeAsset]:
        """Get all active assets linked to an initiative."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_initiative()")

        return db.query(self.model).filter(
            self.model.initiative_id == initiative_id,
            self.model.tenant_id == tenant_id,
            self.model.is_active == True
        ).all()

    def get_by_asset(
        self, db: Session, *, asset_type: str, asset_id: int, tenant_id: int
    ) -> List[InitiativeAsset]:
        """Get all initiatives linked to a specific asset."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_asset()")

        return db.query(self.model).filter(
            self.model.asset_type == asset_type,
            self.model.asset_id == asset_id,
            self.model.tenant_id == tenant_id,
            self.model.is_active == True
        ).all()

    def deactivate_asset(
        self, db: Session, *, id: int, tenant_id: int
    ) -> Optional[InitiativeAsset]:
        """Soft-delete an asset link (set is_active=False)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for deactivate_asset()")

        obj = db.query(self.model).filter(
            self.model.id == id,
            self.model.tenant_id == tenant_id
        ).first()

        if obj:
            obj.is_active = False
            db.commit()
            db.refresh(obj)
        return obj


initiative_asset = CRUDInitiativeAsset(InitiativeAsset)
