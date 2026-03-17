"""
Auto Docs API Endpoints
Sprint 8: AI-powered documentation generation (Module 12).

  POST /auto-docs/generate     — Generate a documentation artifact
  GET  /auto-docs/             — List generated docs for current tenant
  GET  /auto-docs/{id}         — Get a single generated doc
"""
import asyncio
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.api import deps
from app.db.session import get_db
from app.crud.crud_generated_doc import crud_generated_doc
from app.services.auto_docs_service import auto_docs_service, _DOC_TYPE_TITLES
from app.core.logging import get_logger

logger = get_logger("api.auto_docs")

router = APIRouter()


# ---- Schemas ----

class GenerateDocRequest(BaseModel):
    source_type: str = Field(..., pattern="^(document|repository)$")
    source_id: int
    doc_type: str = Field(..., description=(
        "component_spec | architecture_diagram | api_summary | brd | test_cases | data_models"
    ))


class GeneratedDocResponse(BaseModel):
    id: int
    tenant_id: int
    user_id: Optional[int] = None
    source_type: str
    source_id: int
    source_name: Optional[str] = None
    doc_type: str
    title: str
    content: str
    metadata: Optional[dict] = None
    status: str
    created_at: str

    class Config:
        from_attributes = True


# ---- Endpoints ----

@router.post("/generate", status_code=201)
async def generate_doc(
    payload: GenerateDocRequest,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Generate a documentation artifact using AI.
    This is a synchronous call — the response contains the generated content.
    """
    if payload.doc_type not in auto_docs_service.SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown doc_type. Supported: {auto_docs_service.SUPPORTED_TYPES}",
        )

    try:
        result = await auto_docs_service.generate(
            db,
            doc_type=payload.doc_type,
            source_type=payload.source_type,
            source_id=payload.source_id,
            tenant_id=tenant_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    obj = crud_generated_doc.create(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        source_type=payload.source_type,
        source_id=payload.source_id,
        source_name=result.get("source_name"),
        doc_type=payload.doc_type,
        title=result["title"],
        content=result["content"],
        metadata=result.get("metadata"),
        status=result["status"],
    )

    return {
        "id": obj.id,
        "tenant_id": obj.tenant_id,
        "user_id": obj.user_id,
        "source_type": obj.source_type,
        "source_id": obj.source_id,
        "source_name": obj.source_name,
        "doc_type": obj.doc_type,
        "title": obj.title,
        "content": obj.content,
        "metadata": obj.doc_metadata,
        "status": obj.status,
        "created_at": obj.created_at.isoformat(),
    }


@router.get("/")
def list_generated_docs(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    source_type: Optional[str] = Query(None),
    source_id: Optional[int] = Query(None),
    doc_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    """List previously generated docs with optional filters."""
    docs = crud_generated_doc.list_for_tenant(
        db,
        tenant_id=tenant_id,
        source_type=source_type,
        source_id=source_id,
        doc_type=doc_type,
        skip=skip,
        limit=limit,
    )
    return {
        "docs": [
            {
                "id": d.id,
                "source_type": d.source_type,
                "source_id": d.source_id,
                "source_name": d.source_name,
                "doc_type": d.doc_type,
                "title": d.title,
                "status": d.status,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ],
        "total": len(docs),
        "supported_types": auto_docs_service.SUPPORTED_TYPES,
    }


@router.get("/{doc_id}")
def get_generated_doc(
    doc_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get full content of a specific generated doc."""
    obj = crud_generated_doc.get_by_id(db, doc_id=doc_id, tenant_id=tenant_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Generated doc not found")
    return {
        "id": obj.id,
        "tenant_id": obj.tenant_id,
        "user_id": obj.user_id,
        "source_type": obj.source_type,
        "source_id": obj.source_id,
        "source_name": obj.source_name,
        "doc_type": obj.doc_type,
        "title": obj.title,
        "content": obj.content,
        "metadata": obj.doc_metadata,
        "status": obj.status,
        "created_at": obj.created_at.isoformat(),
    }
