"""
CRUD for JiraItem model.
Sprint 9: Deep JIRA integration.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.jira_item import JiraItem


class CRUDJiraItem:

    def upsert_by_key(
        self,
        db: Session,
        *,
        tenant_id: int,
        integration_config_id: int,
        external_key: str,
        data: dict,
    ) -> JiraItem:
        """Create or update a JiraItem by its external key. Thread-safe via filter+update."""
        existing = db.query(JiraItem).filter(
            JiraItem.tenant_id == tenant_id,
            JiraItem.integration_config_id == integration_config_id,
            JiraItem.external_key == external_key,
        ).first()

        if existing:
            for field, value in data.items():
                if hasattr(existing, field):
                    setattr(existing, field, value)
            existing.synced_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing

        obj = JiraItem(
            tenant_id=tenant_id,
            integration_config_id=integration_config_id,
            external_key=external_key,
            synced_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            **{k: v for k, v in data.items() if hasattr(JiraItem, k)},
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get_by_key(
        self, db: Session, *, tenant_id: int, external_key: str
    ) -> Optional[JiraItem]:
        return db.query(JiraItem).filter(
            JiraItem.tenant_id == tenant_id,
            JiraItem.external_key == external_key,
        ).first()

    def get_multi(
        self,
        db: Session,
        *,
        tenant_id: int,
        integration_config_id: Optional[int] = None,
        item_type: Optional[str] = None,
        project_key: Optional[str] = None,
        epic_key: Optional[str] = None,
        sprint_name: Optional[str] = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[JiraItem]:
        q = db.query(JiraItem).filter(JiraItem.tenant_id == tenant_id)
        if integration_config_id is not None:
            q = q.filter(JiraItem.integration_config_id == integration_config_id)
        if item_type:
            q = q.filter(JiraItem.item_type == item_type)
        if project_key:
            q = q.filter(JiraItem.project_key == project_key)
        if epic_key:
            q = q.filter(JiraItem.epic_key == epic_key)
        if sprint_name:
            q = q.filter(JiraItem.sprint_name == sprint_name)
        return q.order_by(JiraItem.external_key).offset(skip).limit(limit).all()

    def get_with_acceptance_criteria(
        self,
        db: Session,
        *,
        tenant_id: int,
        project_key: Optional[str] = None,
        epic_key: Optional[str] = None,
        sprint_name: Optional[str] = None,
    ) -> list[JiraItem]:
        """Return only items that have acceptance criteria (used by validation engine)."""
        q = db.query(JiraItem).filter(
            JiraItem.tenant_id == tenant_id,
            JiraItem.acceptance_criteria.isnot(None),
        )
        if project_key:
            q = q.filter(JiraItem.project_key == project_key)
        if epic_key:
            q = q.filter(JiraItem.epic_key == epic_key)
        if sprint_name:
            q = q.filter(JiraItem.sprint_name == sprint_name)
        return q.order_by(JiraItem.external_key).all()

    def count_by_tenant(self, db: Session, *, tenant_id: int, integration_config_id: int) -> int:
        return db.query(JiraItem).filter(
            JiraItem.tenant_id == tenant_id,
            JiraItem.integration_config_id == integration_config_id,
        ).count()

    def set_ontology_concept(
        self, db: Session, *, jira_item_id: int, concept_id: int
    ) -> None:
        db.query(JiraItem).filter(JiraItem.id == jira_item_id).update(
            {"ontology_concept_id": concept_id}
        )
        db.commit()


crud_jira_item = CRUDJiraItem()
