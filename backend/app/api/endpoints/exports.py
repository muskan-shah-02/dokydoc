"""
Export API Endpoints (Sprint 5)

Provides data export in multiple formats:
  GET /exports/documents       — Export document analysis data as JSON/CSV
  GET /exports/code            — Export code component analysis data
  GET /exports/ontology        — Export ontology concepts and relationships
  GET /exports/report          — Generate a comprehensive PDF-style report (JSON)
"""
from typing import Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import csv
import io
import json

from app import crud, models
from app.api import deps
from app.db.session import get_db
from app.core.logging import get_logger

logger = get_logger("api.exports")

router = APIRouter()


@router.get("/documents")
def export_documents(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    format: str = Query("json", description="Export format: json or csv"),
    initiative_id: Optional[int] = Query(None, description="Filter by project"),
) -> Any:
    """Export document analysis data."""
    if initiative_id:
        documents = crud.document.get_by_initiative(
            db=db, initiative_id=initiative_id, tenant_id=tenant_id
        )
    else:
        documents = crud.document.get_multi(
            db=db, tenant_id=tenant_id, skip=0, limit=1000
        )

    data = []
    for doc in documents:
        data.append({
            "id": doc.id,
            "filename": doc.filename,
            "document_type": doc.document_type,
            "version": doc.version,
            "status": doc.status,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "summary": getattr(doc, "ai_summary", None),
        })

    if format == "csv":
        return _to_csv_response(data, "documents_export.csv")

    return {
        "exported_at": datetime.utcnow().isoformat(),
        "format": "json",
        "total": len(data),
        "records": data,
    }


@router.get("/code")
def export_code_components(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    format: str = Query("json", description="Export format: json or csv"),
    repo_id: Optional[int] = Query(None, description="Filter by repository"),
) -> Any:
    """Export code component analysis data."""
    from app.models.code_component import CodeComponent

    query = db.query(CodeComponent).filter(
        CodeComponent.tenant_id == tenant_id
    )
    if repo_id:
        query = query.filter(CodeComponent.repository_id == repo_id)

    components = query.limit(2000).all()

    data = []
    for comp in components:
        data.append({
            "id": comp.id,
            "name": comp.name,
            "component_type": comp.component_type,
            "location": comp.location,
            "version": comp.version,
            "analysis_status": comp.analysis_status,
            "summary": comp.summary,
            "ai_cost_inr": float(comp.ai_cost_inr) if comp.ai_cost_inr else 0,
            "repository_id": comp.repository_id,
            "created_at": comp.created_at.isoformat() if comp.created_at else None,
        })

    if format == "csv":
        return _to_csv_response(data, "code_components_export.csv")

    return {
        "exported_at": datetime.utcnow().isoformat(),
        "format": "json",
        "total": len(data),
        "records": data,
    }


@router.get("/ontology")
def export_ontology(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    format: str = Query("json", description="Export format: json or csv"),
    initiative_id: Optional[int] = Query(None, description="Filter by project"),
) -> Any:
    """Export ontology concepts and relationships."""
    if initiative_id:
        concepts = crud.ontology_concept.get_by_initiative(
            db=db, initiative_id=initiative_id, tenant_id=tenant_id,
            skip=0, limit=5000
        )
    else:
        concepts = crud.ontology_concept.get_multi(
            db=db, tenant_id=tenant_id, skip=0, limit=5000
        )

    relationships = crud.ontology_relationship.get_multi(
        db=db, tenant_id=tenant_id, skip=0, limit=10000
    )

    concept_data = []
    for c in concepts:
        concept_data.append({
            "id": c.id,
            "name": c.name,
            "concept_type": c.concept_type,
            "description": c.description,
            "source_type": getattr(c, "source_type", None),
            "initiative_id": getattr(c, "initiative_id", None),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    rel_data = []
    for r in relationships:
        rel_data.append({
            "id": r.id,
            "source_concept_id": r.source_concept_id,
            "target_concept_id": r.target_concept_id,
            "relationship_type": r.relationship_type,
            "confidence_score": r.confidence_score,
        })

    if format == "csv":
        return _to_csv_response(concept_data, "ontology_concepts_export.csv")

    return {
        "exported_at": datetime.utcnow().isoformat(),
        "format": "json",
        "total_concepts": len(concept_data),
        "total_relationships": len(rel_data),
        "concepts": concept_data,
        "relationships": rel_data,
    }


@router.get("/report")
def generate_report(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    initiative_id: Optional[int] = Query(None, description="Scope to project"),
) -> Any:
    """
    Generate a comprehensive analysis report (JSON structure suitable for PDF rendering).
    Includes document summaries, code analysis, ontology stats, and validation results.
    """
    from app.models.code_component import CodeComponent
    from app.models.repository import Repository
    from sqlalchemy import func

    # Documents
    if initiative_id:
        try:
            documents = crud.document.get_by_initiative(
                db=db, initiative_id=initiative_id, tenant_id=tenant_id
            )
        except Exception:
            documents = []
    else:
        documents = crud.document.get_multi(
            db=db, tenant_id=tenant_id, skip=0, limit=100
        )

    # Repositories
    repos = db.query(Repository).filter(
        Repository.tenant_id == tenant_id
    ).all()

    # Code stats
    total_files = db.query(func.count(CodeComponent.id)).filter(
        CodeComponent.tenant_id == tenant_id
    ).scalar() or 0

    analyzed_files = db.query(func.count(CodeComponent.id)).filter(
        CodeComponent.tenant_id == tenant_id,
        CodeComponent.analysis_status == "completed",
    ).scalar() or 0

    total_cost = db.query(func.sum(CodeComponent.ai_cost_inr)).filter(
        CodeComponent.tenant_id == tenant_id,
        CodeComponent.ai_cost_inr.isnot(None),
    ).scalar() or 0

    # Ontology stats
    concept_count = crud.ontology_concept.count_by_tenant(
        db=db, tenant_id=tenant_id
    ) if hasattr(crud.ontology_concept, "count_by_tenant") else 0

    rel_count = len(crud.ontology_relationship.get_multi(
        db=db, tenant_id=tenant_id, skip=0, limit=1
    ))

    # Validation mismatches
    try:
        mismatches = crud.mismatch.get_multi(
            db=db, tenant_id=tenant_id, skip=0, limit=10
        )
        mismatch_count = len(mismatches)
    except Exception:
        mismatch_count = 0

    report = {
        "report_title": "DokyDoc Analysis Report",
        "generated_at": datetime.utcnow().isoformat(),
        "generated_by": current_user.email,
        "tenant_id": tenant_id,
        "initiative_id": initiative_id,
        "summary": {
            "total_documents": len(documents),
            "total_repositories": len(repos),
            "total_code_files": total_files,
            "analyzed_files": analyzed_files,
            "analysis_rate": f"{round(analyzed_files / total_files * 100, 1)}%" if total_files > 0 else "0%",
            "total_ai_cost_inr": float(total_cost),
            "ontology_concepts": concept_count,
            "validation_mismatches": mismatch_count,
        },
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "type": d.document_type,
                "status": d.status,
                "version": d.version,
            }
            for d in documents[:50]
        ],
        "repositories": [
            {
                "id": r.id,
                "name": r.name,
                "url": r.url,
                "analysis_status": r.analysis_status,
                "total_files": r.total_files,
                "analyzed_files": r.analyzed_files,
            }
            for r in repos[:50]
        ],
    }

    return report


def _to_csv_response(data: list, filename: str) -> StreamingResponse:
    """Convert a list of dicts to a CSV streaming response."""
    if not data:
        return StreamingResponse(
            io.StringIO(""),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
