"""
Sprint 5: Unified Semantic Search API

Provides a single endpoint that searches across all entity types:
ontology concepts, documents, code components, and knowledge graphs.
"""

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models
from app.api import deps
from app.db.session import get_db
from app.core.logging import get_logger

logger = get_logger("api.search")

router = APIRouter()


@router.get("/unified")
def unified_search(
    q: str = Query(..., min_length=1, description="Search query"),
    categories: Optional[str] = Query(
        None,
        description="Comma-separated categories to search: concepts,documents,code,graphs",
    ),
    initiative_id: Optional[int] = Query(None, description="Filter by initiative"),
    limit: int = Query(30, ge=1, le=100, description="Max total results"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Unified semantic search across concepts, documents, code, and graphs.
    Returns results grouped by category with relevance scores and facet counts.
    """
    from app.services.semantic_search_service import semantic_search_service

    cat_list = None
    if categories:
        cat_list = [c.strip() for c in categories.split(",") if c.strip()]

    return semantic_search_service.unified_search(
        db,
        q,
        tenant_id,
        categories=cat_list,
        initiative_id=initiative_id,
        limit=limit,
    )


@router.get("/documents")
def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Search documents by filename, content, and type."""
    from app.services.semantic_search_service import semantic_search_service

    results = semantic_search_service.search_documents(
        db, q, tenant_id,
        document_type=document_type,
        limit=limit,
    )
    return {"query": q, "results": results, "count": len(results)}


@router.get("/code")
def search_code(
    q: str = Query(..., min_length=1, description="Search query"),
    component_type: Optional[str] = Query(None, description="Filter by component type"),
    analysis_status: Optional[str] = Query(None, description="Filter by analysis status"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Search code components by name, summary, and location."""
    from app.services.semantic_search_service import semantic_search_service

    results = semantic_search_service.search_code_components(
        db, q, tenant_id,
        component_type=component_type,
        analysis_status=analysis_status,
        limit=limit,
    )
    return {"query": q, "results": results, "count": len(results)}


@router.get("/suggestions")
def search_suggestions(
    q: str = Query(..., min_length=1, description="Partial query for autocomplete"),
    limit: int = Query(8, ge=1, le=20, description="Max suggestions"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Quick autocomplete suggestions from concept names, document filenames,
    and code component names. Optimized for speed over relevance.
    """
    from sqlalchemy import text as sql_text

    suggestions = []

    # Concept names
    try:
        rows = db.execute(
            sql_text(
                "SELECT DISTINCT name, 'concept' AS source FROM ontology_concepts "
                "WHERE tenant_id = :tid AND is_active = true AND name ILIKE :q "
                "ORDER BY name LIMIT :lim"
            ),
            {"tid": tenant_id, "q": f"%{q}%", "lim": limit},
        ).fetchall()
        suggestions.extend({"text": row[0], "source": row[1]} for row in rows)
    except Exception:
        pass

    # Document filenames
    try:
        rows = db.execute(
            sql_text(
                "SELECT DISTINCT filename, 'document' AS source FROM documents "
                "WHERE tenant_id = :tid AND filename ILIKE :q "
                "ORDER BY filename LIMIT :lim"
            ),
            {"tid": tenant_id, "q": f"%{q}%", "lim": limit},
        ).fetchall()
        suggestions.extend({"text": row[0], "source": row[1]} for row in rows)
    except Exception:
        pass

    # Code component names
    try:
        rows = db.execute(
            sql_text(
                "SELECT DISTINCT name, 'code' AS source FROM code_components "
                "WHERE tenant_id = :tid AND name ILIKE :q "
                "ORDER BY name LIMIT :lim"
            ),
            {"tid": tenant_id, "q": f"%{q}%", "lim": limit},
        ).fetchall()
        suggestions.extend({"text": row[0], "source": row[1]} for row in rows)
    except Exception:
        pass

    # Deduplicate by text, keep first occurrence
    seen = set()
    unique = []
    for s in suggestions:
        if s["text"].lower() not in seen:
            seen.add(s["text"].lower())
            unique.append(s)

    return {"query": q, "suggestions": unique[:limit]}
