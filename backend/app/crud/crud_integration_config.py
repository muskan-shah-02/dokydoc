"""
CRUD for IntegrationConfig model.
Sprint 8: Documentation Integrations.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models.integration_config import IntegrationConfig


class CRUDIntegrationConfig:

    def get_for_tenant(self, db: Session, *, tenant_id: int) -> list[IntegrationConfig]:
        return (
            db.query(IntegrationConfig)
            .filter(IntegrationConfig.tenant_id == tenant_id)
            .order_by(IntegrationConfig.created_at.desc())
            .all()
        )

    def get_by_provider(
        self, db: Session, *, tenant_id: int, provider: str
    ) -> Optional[IntegrationConfig]:
        return db.query(IntegrationConfig).filter(
            IntegrationConfig.tenant_id == tenant_id,
            IntegrationConfig.provider == provider,
        ).first()

    def get_by_id(
        self, db: Session, *, config_id: int, tenant_id: int
    ) -> Optional[IntegrationConfig]:
        return db.query(IntegrationConfig).filter(
            IntegrationConfig.id == config_id,
            IntegrationConfig.tenant_id == tenant_id,
        ).first()

    def upsert(
        self,
        db: Session,
        *,
        tenant_id: int,
        provider: str,
        created_by_id: Optional[int] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        workspace_name: Optional[str] = None,
        workspace_id: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> IntegrationConfig:
        """Create or update integration config for a given tenant+provider pair."""
        obj = self.get_by_provider(db, tenant_id=tenant_id, provider=provider)
        if obj is None:
            obj = IntegrationConfig(tenant_id=tenant_id, provider=provider, created_by_id=created_by_id)
            db.add(obj)

        if access_token is not None:
            obj.access_token = access_token
        if refresh_token is not None:
            obj.refresh_token = refresh_token
        if token_expires_at is not None:
            obj.token_expires_at = token_expires_at
        if workspace_name is not None:
            obj.workspace_name = workspace_name
        if workspace_id is not None:
            obj.workspace_id = workspace_id
        if base_url is not None:
            obj.base_url = base_url
        obj.is_active = True
        obj.sync_error = None

        db.commit()
        db.refresh(obj)
        return obj

    def mark_error(
        self, db: Session, *, config_id: int, tenant_id: int, error: str
    ) -> Optional[IntegrationConfig]:
        obj = self.get_by_id(db, config_id=config_id, tenant_id=tenant_id)
        if obj:
            obj.sync_error = error
            db.commit()
            db.refresh(obj)
        return obj

    def disconnect(
        self, db: Session, *, config_id: int, tenant_id: int
    ) -> Optional[IntegrationConfig]:
        obj = self.get_by_id(db, config_id=config_id, tenant_id=tenant_id)
        if obj:
            obj.is_active = False
            obj.access_token = None
            obj.refresh_token = None
            db.commit()
            db.refresh(obj)
        return obj


crud_integration_config = CRUDIntegrationConfig()
