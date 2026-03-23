"""
CRUD operations for Tenant model.
Sprint 2 Phase 3: Tenant Registration Flow
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.crud.base import CRUDBase
from app.models.tenant import Tenant
from app.models.user import User
from app.models.document import Document
from app.schemas.tenant import TenantCreate, TenantUpdate


class CRUDTenant(CRUDBase[Tenant, TenantCreate, TenantUpdate]):
    """
    CRUD operations for Tenant model.

    Handles tenant registration, subdomain validation, and tenant management.
    """

    def get_by_id(self, db: Session, *, id: int) -> Optional[Tenant]:
        """
        Get tenant by ID (no tenant isolation needed for Tenant model itself).

        Args:
            db: Database session
            id: Tenant ID

        Returns:
            Tenant if found, None otherwise
        """
        return db.query(Tenant).filter(Tenant.id == id).first()

    def get_by_subdomain(self, db: Session, *, subdomain: str) -> Optional[Tenant]:
        """
        Get tenant by subdomain.

        Used for subdomain uniqueness validation during registration.

        Args:
            db: Database session
            subdomain: Tenant subdomain to lookup

        Returns:
            Tenant if found, None otherwise
        """
        return (
            db.query(Tenant)
            .filter(Tenant.subdomain == subdomain.lower())
            .first()
        )

    def is_subdomain_available(self, db: Session, *, subdomain: str) -> bool:
        """
        Check if a subdomain is available for registration.

        Args:
            db: Database session
            subdomain: Subdomain to check

        Returns:
            True if available, False if already taken
        """
        existing = self.get_by_subdomain(db, subdomain=subdomain)
        return existing is None

    def create_tenant(
        self,
        db: Session,
        *,
        obj_in: TenantCreate
    ) -> Tenant:
        """
        Create a new tenant with default settings.

        This does NOT create the admin user or billing record.
        Use create_tenant_with_admin() for full registration flow.

        Args:
            db: Database session
            obj_in: Tenant creation data

        Returns:
            Created tenant

        Raises:
            ValueError: If subdomain is already taken
        """
        # Check subdomain availability
        if not self.is_subdomain_available(db, subdomain=obj_in.subdomain):
            raise ValueError(f"Subdomain '{obj_in.subdomain}' is already taken")

        # Set defaults based on tier
        tier_defaults = {
            "free": {"max_users": 10, "max_documents": 100},
            "pro": {"max_users": 50, "max_documents": 1000},
            "enterprise": {"max_users": 500, "max_documents": 10000}
        }
        defaults = tier_defaults.get(obj_in.tier, tier_defaults["free"])

        # Create tenant
        db_obj = Tenant(
            name=obj_in.name,
            subdomain=obj_in.subdomain.lower(),
            status="active",
            tier=obj_in.tier,
            billing_type=obj_in.billing_type,
            max_users=defaults["max_users"],
            max_documents=defaults["max_documents"],
            settings={}
        )

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

        return db_obj

    def update_tenant(
        self,
        db: Session,
        *,
        tenant_id: int,
        obj_in: TenantUpdate
    ) -> Optional[Tenant]:
        """
        Update tenant settings.

        Args:
            db: Database session
            tenant_id: Tenant ID to update
            obj_in: Update data

        Returns:
            Updated tenant or None if not found
        """
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(tenant, field, value)

        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        return tenant

    def get_tenant_statistics(
        self,
        db: Session,
        *,
        tenant_id: int
    ) -> dict:
        """
        Get tenant usage statistics.

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            Dictionary with user_count, document_count, storage_used_mb
        """
        # Count users
        user_count = (
            db.query(func.count(User.id))
            .filter(User.tenant_id == tenant_id)
            .scalar()
        ) or 0

        # Count documents
        document_count = (
            db.query(func.count(Document.id))
            .filter(Document.tenant_id == tenant_id)
            .scalar()
        ) or 0

        # Calculate storage (sum of file_size_kb converted to MB)
        storage_kb = (
            db.query(func.sum(Document.file_size_kb))
            .filter(Document.tenant_id == tenant_id)
            .scalar()
        ) or 0
        storage_used_mb = round(storage_kb / 1024, 2)

        return {
            "user_count": user_count,
            "document_count": document_count,
            "storage_used_mb": storage_used_mb
        }

    def check_limits(
        self,
        db: Session,
        *,
        tenant_id: int
    ) -> dict:
        """
        Check if tenant is within its limits.

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            Dictionary with limit checks:
            {
                "can_add_user": bool,
                "can_add_document": bool,
                "users_remaining": int,
                "documents_remaining": int
            }
        """
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        stats = self.get_tenant_statistics(db, tenant_id=tenant_id)

        users_remaining = tenant.max_users - stats["user_count"]
        documents_remaining = tenant.max_documents - stats["document_count"]

        return {
            "can_add_user": users_remaining > 0,
            "can_add_document": documents_remaining > 0,
            "users_remaining": max(0, users_remaining),
            "documents_remaining": max(0, documents_remaining),
            "current_users": stats["user_count"],
            "current_documents": stats["document_count"],
            "max_users": tenant.max_users,
            "max_documents": tenant.max_documents
        }


# Create singleton instance
tenant = CRUDTenant(Tenant)
