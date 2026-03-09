# This is the final, updated content for your file at:
# backend/app/api/endpoints/validation.py

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, status, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.services.validation_service import validation_service
from app.core.logging import LoggerMixin
from app.core.exceptions import ValidationException

class ValidationEndpoints(LoggerMixin):
    """Validation endpoints with enhanced logging and error handling."""
    
    def __init__(self):
        super().__init__()

# Create instance for use in endpoints
validation_endpoints = ValidationEndpoints()

router = APIRouter()

@router.get("/mismatches", response_model=List[schemas.Mismatch])
def read_mismatches(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all mismatches for the current user.

    SPRINT 2: Now filtered by tenant_id for multi-tenancy isolation.
    """
    logger = validation_endpoints.logger
    logger.info(f"Fetching mismatches for user {current_user.id} (tenant_id={tenant_id}), skip={skip}, limit={limit}")

    mismatches = crud.mismatch.get_multi_by_owner(
        db=db, owner_id=current_user.id, tenant_id=tenant_id, skip=skip, limit=limit
    )

    logger.info(f"Retrieved {len(mismatches)} mismatches for user {current_user.id} (tenant_id={tenant_id})")
    return mismatches

@router.post("/run-scan", status_code=status.HTTP_202_ACCEPTED)
def run_validation_scan(
    *,
    document_ids: List[int],
    tenant_id: int = Depends(deps.get_tenant_id),
    current_user: models.User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Trigger a new validation scan for the current user on selected documents.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when documents not in tenant to avoid leaking existence.
    """
    logger = validation_endpoints.logger
    logger.info(f"Validation scan requested by user {current_user.id} (tenant_id={tenant_id}) for documents: {document_ids}")

    if not document_ids:
        logger.warning(f"User {current_user.id} attempted validation scan with no document IDs")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one document ID must be provided"
        )

    # Verify all requested documents exist in tenant
    user_documents = crud.document.get_multi_by_owner(
        db=db, owner_id=current_user.id, tenant_id=tenant_id
    )
    user_doc_ids = {doc.id for doc in user_documents}
    invalid_doc_ids = set(document_ids) - user_doc_ids

    if invalid_doc_ids:
        logger.warning(f"User {current_user.id} attempted to validate documents not in tenant {tenant_id}: {list(invalid_doc_ids)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documents not found: {list(invalid_doc_ids)}"
        )

    # Schedule validation scan in background
    # SPRINT 2 Phase 6: Pass tenant_id to background task for isolation
    background_tasks.add_task(
        validation_service.run_validation_scan,
        user_id=current_user.id,
        document_ids=document_ids,
        tenant_id=tenant_id
    )

    logger.info(f"Validation scan scheduled for user {current_user.id} (tenant_id={tenant_id}) on {len(document_ids)} documents")
    return {
        "message": f"Validation scan has been successfully started for {len(document_ids)} document(s).",
        "document_ids": document_ids
    }


@router.get("/report/{initiative_id}")
def get_validation_report(
    initiative_id: int,
    format: str = Query("json", description="Export format: json"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Sprint 4: Generate a validation report for an initiative.
    Includes mismatch summary, requirement traceability, and coverage metrics.
    """
    logger = validation_endpoints.logger

    # Fetch mismatches for this tenant
    mismatches = crud.mismatch.get_multi_by_owner(
        db=db, owner_id=current_user.id, tenant_id=tenant_id, skip=0, limit=500
    )

    # Fetch requirement traces for the initiative
    traces = []
    try:
        from app.models.requirement_trace import RequirementTrace
        traces = db.query(RequirementTrace).filter(
            RequirementTrace.tenant_id == tenant_id,
            RequirementTrace.initiative_id == initiative_id,
        ).all()
    except Exception as e:
        logger.warning(f"Failed to fetch requirement traces: {e}")

    # Calculate coverage
    total_traces = len(traces)
    fully_covered = sum(1 for t in traces if t.coverage_status == "fully_covered")
    partially_covered = sum(1 for t in traces if t.coverage_status == "partially_covered")
    not_covered = sum(1 for t in traces if t.coverage_status == "not_covered")
    contradicted = sum(1 for t in traces if t.coverage_status == "contradicted")

    coverage_pct = (fully_covered / total_traces * 100) if total_traces > 0 else 0

    # Build report
    report = {
        "initiative_id": initiative_id,
        "generated_at": str(schemas.datetime_now()) if hasattr(schemas, 'datetime_now') else None,
        "summary": {
            "total_mismatches": len(mismatches),
            "critical": sum(1 for m in mismatches if getattr(m, 'severity', '') == "critical"),
            "warning": sum(1 for m in mismatches if getattr(m, 'severity', '') == "warning"),
            "info": sum(1 for m in mismatches if getattr(m, 'severity', '') == "info"),
        },
        "requirement_coverage": {
            "total_requirements": total_traces,
            "fully_covered": fully_covered,
            "partially_covered": partially_covered,
            "not_covered": not_covered,
            "contradicted": contradicted,
            "coverage_percentage": round(coverage_pct, 1),
        },
        "mismatches": [
            {
                "id": m.id,
                "description": m.description if hasattr(m, 'description') else str(m),
                "severity": getattr(m, 'severity', 'unknown'),
                "category": getattr(m, 'category', None),
                "status": getattr(m, 'status', 'open'),
            }
            for m in mismatches
        ],
        "requirement_traces": [
            {
                "id": t.id,
                "requirement_text": t.requirement_text[:200] if t.requirement_text else None,
                "coverage_status": t.coverage_status,
                "linked_concepts": t.linked_concept_ids if hasattr(t, 'linked_concept_ids') else None,
            }
            for t in traces
        ],
    }

    return report
