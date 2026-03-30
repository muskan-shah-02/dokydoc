# backend/app/api/endpoints/validation.py
# Sprint 9: Added JIRA validation scan endpoint.

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, status, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
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


class SuggestLinksRequest(BaseModel):
    document_id: int


@router.post("/suggest-links")
async def suggest_additional_links(
    payload: SuggestLinksRequest,
    tenant_id: int = Depends(deps.get_tenant_id),
    current_user: models.User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Suggest additional code files to link to a document based on existing validation gaps.
    Reuses stored mismatch records and code component analyses — no re-analysis needed.
    Returns up to 3 file suggestions with relevance scores and reasons.
    """
    logger = validation_endpoints.logger

    # Verify document belongs to this tenant
    document = crud.document.get(db=db, id=payload.document_id)
    if not document or document.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    suggestions = await validation_service.generate_coverage_suggestions(
        document_id=payload.document_id,
        user_id=current_user.id,
        tenant_id=tenant_id,
    )

    logger.info(
        f"Coverage suggestions for doc {payload.document_id} "
        f"(tenant={tenant_id}): {len(suggestions)} suggestions returned"
    )
    return {"document_id": payload.document_id, "suggestions": suggestions}


@router.get("/atom-count/{document_id}")
def get_atom_count(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Sprint 10: Return the total number of RequirementAtoms extracted from a document.
    Used by the frontend to compute the coverage score:
      coverage_pct = (total_atoms - atoms_with_forward_mismatches) / total_atoms * 100
    """
    document = crud.document.get(db=db, id=document_id)
    if not document or document.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    total = crud.requirement_atom.count_by_document(db, document_id=document_id)
    return {"document_id": document_id, "total_atoms": total}


class JiraValidationRequest(BaseModel):
    repository_id: int
    project_key: Optional[str] = None
    epic_key: Optional[str] = None
    sprint_name: Optional[str] = None


@router.post("/run-jira-scan", status_code=status.HTTP_202_ACCEPTED)
async def run_jira_validation_scan(
    payload: JiraValidationRequest,
    tenant_id: int = Depends(deps.get_tenant_id),
    current_user: models.User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Sprint 9: Validate a code repository against JIRA acceptance criteria.

    Fetches JIRA stories/tasks with acceptance criteria in the given scope
    (project, epic, or sprint) and checks whether the code satisfies each one.

    Results are stored as Mismatch records with category='jira_acceptance_criteria'.
    Returns immediately with a summary once validation completes.
    """
    logger = validation_endpoints.logger
    logger.info(
        f"JIRA validation scan requested by user {current_user.id} "
        f"(tenant={tenant_id}) for repo={payload.repository_id}"
    )

    if not payload.project_key and not payload.epic_key and not payload.sprint_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of project_key, epic_key, or sprint_name must be provided.",
        )

    stats = await validation_service.run_jira_validation_scan(
        tenant_id=tenant_id,
        user_id=current_user.id,
        repository_id=payload.repository_id,
        project_key=payload.project_key,
        epic_key=payload.epic_key,
        sprint_name=payload.sprint_name,
    )

    return {
        "message": "JIRA validation scan completed.",
        "repository_id": payload.repository_id,
        "scope": {
            "project_key": payload.project_key,
            "epic_key": payload.epic_key,
            "sprint_name": payload.sprint_name,
        },
        "results": stats,
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
