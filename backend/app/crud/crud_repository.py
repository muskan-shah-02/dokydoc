"""
SPRINT 3: Repository CRUD (ARCH-04)

Provides data access for the Repository model — the parent entity
for scalable code analysis. Each repository contains N code components.
"""

from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.crud.base import CRUDBase
from app.models.repository import Repository
from app.schemas.repository import RepositoryCreate, RepositoryUpdate


class CRUDRepository(CRUDBase[Repository, RepositoryCreate, RepositoryUpdate]):

    def create_with_owner(
        self, db: Session, *, obj_in: RepositoryCreate, owner_id: int, tenant_id: int
    ) -> Repository:
        """Create a repository with explicit owner assignment."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for create_with_owner()")

        db_obj = Repository(
            name=obj_in.name,
            url=obj_in.url,
            default_branch=obj_in.default_branch or "main",
            description=obj_in.description,
            owner_id=owner_id,
            tenant_id=tenant_id,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_url(
        self, db: Session, *, url: str, tenant_id: int
    ) -> Optional[Repository]:
        """Find a repository by its URL within a tenant (for dedup on onboarding)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_url()")

        return db.query(self.model).filter(
            self.model.url == url,
            self.model.tenant_id == tenant_id,
        ).first()

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, tenant_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[Repository]:
        """List repositories owned by a specific user."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_multi_by_owner()")

        return db.query(self.model).filter(
            self.model.owner_id == owner_id,
            self.model.tenant_id == tenant_id,
        ).offset(skip).limit(limit).all()

    def get_by_status(
        self, db: Session, *, analysis_status: str, tenant_id: int,
        skip: int = 0, limit: int = 50
    ) -> List[Repository]:
        """Get repositories by analysis status (pending, analyzing, completed, failed)."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_status()")

        return db.query(self.model).filter(
            self.model.analysis_status == analysis_status,
            self.model.tenant_id == tenant_id,
        ).offset(skip).limit(limit).all()

    def update_analysis_progress(
        self, db: Session, *, repo_id: int, tenant_id: int,
        analyzed_files: int, total_files: int = None,
        status: str = None, last_commit: str = None,
        error_message: str = None
    ) -> Optional[Repository]:
        """Atomic progress update for the Repo Agent worker."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for update_analysis_progress()")

        repo = self.get(db=db, id=repo_id, tenant_id=tenant_id)
        if not repo:
            return None

        update_data = {"analyzed_files": analyzed_files}
        if total_files is not None:
            update_data["total_files"] = total_files
        if status:
            update_data["analysis_status"] = status
        if last_commit:
            update_data["last_analyzed_commit"] = last_commit
        if error_message is not None:
            update_data["error_message"] = error_message

        return self.update(db=db, db_obj=repo, obj_in=update_data)

    def get_by_initiative(
        self, db: Session, *, initiative_id: int, tenant_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[Repository]:
        """Get repositories linked to a specific initiative via InitiativeAsset."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_by_initiative()")

        from app.models.initiative_asset import InitiativeAsset
        asset_ids = db.query(InitiativeAsset.asset_id).filter(
            InitiativeAsset.initiative_id == initiative_id,
            InitiativeAsset.asset_type == "REPOSITORY",
            InitiativeAsset.tenant_id == tenant_id,
            InitiativeAsset.is_active == True,
        ).subquery()

        return db.query(self.model).filter(
            self.model.id.in_(asset_ids),
            self.model.tenant_id == tenant_id,
        ).offset(skip).limit(limit).all()

    def count_by_tenant(self, db: Session, *, tenant_id: int) -> int:
        """Count all repositories for a tenant."""
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for count_by_tenant()")

        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
        ).count()


repository = CRUDRepository(Repository)
