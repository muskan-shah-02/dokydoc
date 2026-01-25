from sqlalchemy.orm import Session
from app.core.security import get_password_hash
from app.crud.base import CRUDBase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, Role


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_user_by_email(self, db: Session, *, email: str) -> User | None:
        return db.query(User).filter(User.email == email).first()

    def create_user(self, db: Session, *, obj_in: UserCreate, tenant_id: int) -> User:
        """
        Create a new user with tenant_id assignment.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.

        Args:
            db: Database session
            obj_in: User creation schema
            tenant_id: REQUIRED tenant ID for multi-tenancy isolation

        Returns:
            Created user object
        """
        # CRITICAL VALIDATION: Ensure tenant_id is provided
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for user creation")

        # Convert the list of Role enums to a list of strings for the database
        role_values = [role.value for role in obj_in.roles]

        db_obj = User(
            email=obj_in.email,
            hashed_password=get_password_hash(obj_in.password),
            roles=role_values,  # Assign the list of role strings
            is_superuser=False,
            tenant_id=tenant_id  # SPRINT 2: Assign user to tenant
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_tenant(
        self, db: Session, *, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> list[User]:
        """
        Get all users in a specific tenant.

        SPRINT 2 Phase 5: Used by tenant admins to list users in their tenant.

        Args:
            db: Database session
            tenant_id: Tenant ID to filter by
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return

        Returns:
            List of users in the tenant
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED")

        return (
            db.query(User)
            .filter(User.tenant_id == tenant_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

user = CRUDUser(User)