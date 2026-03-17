"""
CRUD for GeneratedDoc model.
Sprint 8: Auto Docs.
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.models.generated_doc import GeneratedDoc


class CRUDGeneratedDoc:

    def create(
        self,
        db: Session,
        *,
        tenant_id: int,
        user_id: Optional[int],
        source_type: str,
        source_id: int,
        source_name: Optional[str],
        doc_type: str,
        title: str,
        content: str,
        metadata: Optional[dict] = None,
        status: str = "completed",
    ) -> GeneratedDoc:
        obj = GeneratedDoc(
            tenant_id=tenant_id,
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            source_name=source_name,
            doc_type=doc_type,
            title=title,
            content=content,
            metadata=metadata,
            status=status,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get_by_id(self, db: Session, *, doc_id: int, tenant_id: int) -> Optional[GeneratedDoc]:
        return db.query(GeneratedDoc).filter(
            GeneratedDoc.id == doc_id, GeneratedDoc.tenant_id == tenant_id
        ).first()

    def list_for_tenant(
        self,
        db: Session,
        *,
        tenant_id: int,
        source_type: Optional[str] = None,
        source_id: Optional[int] = None,
        doc_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[GeneratedDoc]:
        q = db.query(GeneratedDoc).filter(GeneratedDoc.tenant_id == tenant_id)
        if source_type:
            q = q.filter(GeneratedDoc.source_type == source_type)
        if source_id is not None:
            q = q.filter(GeneratedDoc.source_id == source_id)
        if doc_type:
            q = q.filter(GeneratedDoc.doc_type == doc_type)
        return q.order_by(GeneratedDoc.created_at.desc()).offset(skip).limit(limit).all()


crud_generated_doc = CRUDGeneratedDoc()
