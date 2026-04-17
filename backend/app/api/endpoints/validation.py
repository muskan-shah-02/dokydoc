# backend/app/api/endpoints/validation.py
# Sprint 9: Added JIRA validation scan endpoint.

from typing import Any, List, Optional
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, BackgroundTasks, status, HTTPException, Query, Body
from fastapi.responses import JSONResponse, StreamingResponse
import io
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

    # ARC-BE-04: Fetch mismatches with explicit cap; flag truncation in response
    REPORT_LIMIT = 500
    mismatches = crud.mismatch.get_multi_by_owner(
        db=db, owner_id=current_user.id, tenant_id=tenant_id, skip=0, limit=REPORT_LIMIT
    )
    report_truncated = len(mismatches) == REPORT_LIMIT

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
        # ARC-BE-04: Tell callers when the mismatch list was capped
        "truncated": report_truncated,
        "mismatch_limit": REPORT_LIMIT,
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


# ── P5B-02: Compliance Score ──────────────────────────────────────────────────

@router.get("/{document_id}/compliance-score")
def get_compliance_score(
    document_id: int,
    code_component_id: Optional[int] = Query(None),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    P5B-02: Returns single compliance score for a document.
    Grade: A(≥95%) B(≥85%) C(≥75%) D(≥60%) F(<60%)
    Optional: filter to a specific code component for link-level score.
    """
    document = crud.document.get(db, id=document_id)
    if not document or document.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    breakdown = crud.mismatch.get_compliance_breakdown(
        db=db, document_id=document_id,
        tenant_id=tenant_id, code_component_id=code_component_id,
    )
    if breakdown.get("overall_score") is None:
        raise HTTPException(status_code=404, detail=breakdown.get("message"))

    score = breakdown["overall_score"]
    pct = round(score * 100)
    grade = "A" if pct >= 95 else "B" if pct >= 85 else "C" if pct >= 75 else "D" if pct >= 60 else "F"

    return {"document_id": document_id, **breakdown, "percentage": pct, "grade": grade}


# ── P5B-04: False Positive Workflow ───────────────────────────────────────────

class FalsePositiveRequest(BaseModel):
    reason: str

class DisputeRequest(BaseModel):
    dispute_reason: str

@router.post("/mismatches/{mismatch_id}/false-positive")
def mark_false_positive(
    mismatch_id: int,
    payload: FalsePositiveRequest,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """P5B-04: Mark mismatch as false positive. Reason must be ≥10 chars."""
    try:
        m = crud.mismatch.mark_false_positive(
            db, mismatch_id=mismatch_id, tenant_id=tenant_id,
            reason=payload.reason, changed_by_user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not m:
        raise HTTPException(status_code=404, detail="Mismatch not found")
    return {"mismatch_id": mismatch_id, "status": m.status, "resolution_note": m.resolution_note}


@router.post("/mismatches/{mismatch_id}/dispute")
def dispute_false_positive(
    mismatch_id: int,
    payload: DisputeRequest,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """P5B-04: Dispute a false positive decision — sets status to 'disputed'."""
    m = crud.mismatch.dispute_false_positive(
        db, mismatch_id=mismatch_id, tenant_id=tenant_id,
        dispute_reason=payload.dispute_reason, changed_by_user_id=current_user.id,
    )
    if not m:
        raise HTTPException(status_code=404, detail="Mismatch not found or not in false_positive state")
    return {"mismatch_id": mismatch_id, "status": m.status}


# ── P5B-05: Evidence Transparency ────────────────────────────────────────────

@router.get("/mismatches/{mismatch_id}/evidence")
def get_mismatch_evidence(
    mismatch_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    P5B-05: Returns structured evidence for a mismatch.
    Shows exactly what BRD text was checked, what code was analyzed, and AI reasoning.
    """
    m = db.query(models.Mismatch).filter(
        models.Mismatch.id == mismatch_id,
        models.Mismatch.tenant_id == tenant_id,
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mismatch not found")

    details = m.details or {}
    atom_content = details.get("atom_content", "")

    # Fetch atom if linked
    if m.requirement_atom_id and not atom_content:
        from app.models.requirement_atom import RequirementAtom
        atom = db.query(RequirementAtom).filter(RequirementAtom.id == m.requirement_atom_id).first()
        if atom:
            atom_content = atom.content

    return {
        "mismatch_id": mismatch_id,
        "brd_requirement": {
            "atom_id": details.get("atom_id"),
            "atom_type": details.get("atom_type"),
            "content": atom_content,
            "regulatory_tags": details.get("regulatory_frameworks", []),
        },
        "code_analyzed": {
            "snapshot": details.get("code_evidence", {}),
            "component_name": details.get("component_name"),
        },
        "ai_conclusion": {
            "mismatch_type": m.mismatch_type,
            "description": m.description,
            "severity": m.severity,
            "confidence": m.confidence,
            "evidence": details.get("evidence", ""),
            "confidence_reasoning": details.get("confidence_reasoning", ""),
            "validation_timestamp": details.get("validation_timestamp"),
        },
    }


# ── P5B-07: Coverage Matrix ───────────────────────────────────────────────────

@router.get("/{document_id}/coverage-matrix")
def get_coverage_matrix(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    P5B-07: Returns BRD atoms × code components coverage matrix.
    Cell values: {coverage_score, open_mismatches, critical_mismatches, status}
    """
    document = crud.document.get(db, id=document_id)
    if not document or document.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.models.requirement_atom import RequirementAtom
    from app.models.document_code_link import DocumentCodeLink
    from app.models.code_component import CodeComponent

    atoms = db.query(RequirementAtom).filter(
        RequirementAtom.document_id == document_id,
        RequirementAtom.tenant_id == tenant_id,
    ).all()

    links = db.query(DocumentCodeLink).filter(
        DocumentCodeLink.document_id == document_id,
        DocumentCodeLink.tenant_id == tenant_id,
    ).all()

    component_ids = [l.code_component_id for l in links]
    components = db.query(CodeComponent).filter(
        CodeComponent.id.in_(component_ids)
    ).all() if component_ids else []

    mismatches = db.query(models.Mismatch).filter(
        models.Mismatch.document_id == document_id,
        models.Mismatch.tenant_id == tenant_id,
        models.Mismatch.status.in_(["open", "in_progress", "new"]),
    ).all()

    # ARC-BE-01: Pre-build set for O(1) link lookup (was O(N) any() inside O(N²) loop)
    linked_component_ids = {l.code_component_id for l in links}

    # Build matrix: (atom_id, component_id) → {open, critical}
    from collections import defaultdict
    cell_data: dict = defaultdict(lambda: {"open": 0, "critical": 0})
    for m in mismatches:
        if m.requirement_atom_id:
            key = f"{m.requirement_atom_id}::{m.code_component_id}"
            cell_data[key]["open"] += 1
            if m.severity in ("critical", "compliance_risk"):
                cell_data[key]["critical"] += 1

    matrix = {}
    for atom in atoms:
        for comp in components:
            key = f"{atom.id}::{comp.id}"
            cell = cell_data.get(key, {"open": 0, "critical": 0})
            open_count = cell["open"]
            crit_count = cell["critical"]

            # ARC-BE-01: O(1) set lookup instead of O(N) any()
            if comp.id not in linked_component_ids:
                cell_status = "not_linked"
                cov_score = 0.0
            elif crit_count > 0:
                cell_status = "missing"
                cov_score = 0.0
            elif open_count > 0:
                cell_status = "partial"
                cov_score = 0.5
            else:
                cell_status = "covered"
                cov_score = 1.0

            matrix[key] = {
                "coverage_score": cov_score,
                "open_mismatches": open_count,
                "critical_mismatches": crit_count,
                "status": cell_status,
            }

    covered = sum(1 for v in matrix.values() if v["status"] == "covered")
    partial = sum(1 for v in matrix.values() if v["status"] == "partial")
    missing = sum(1 for v in matrix.values() if v["status"] == "missing")

    return {
        "document_id": document_id,
        "atoms": [{"id": a.id, "atom_id": a.atom_id, "atom_type": a.atom_type, "content": a.content[:120]} for a in atoms],
        "components": [{"id": c.id, "name": c.name, "file_path": getattr(c, "file_path", "")} for c in components],
        "matrix": matrix,
        "summary": {"covered": covered, "partial": partial, "missing": missing, "total_cells": len(matrix)},
    }


# ── P5B-10: Mismatch Status Lifecycle ────────────────────────────────────────

class StatusUpdateRequest(BaseModel):
    status: str
    note: Optional[str] = None

@router.patch("/mismatches/{mismatch_id}/status")
def update_mismatch_status(
    mismatch_id: int,
    payload: StatusUpdateRequest,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    P5B-10: Update mismatch status with lifecycle transition validation.
    Valid: open → in_progress → resolved → verified (+ false_positive, auto_closed, disputed)
    """
    try:
        m = crud.mismatch.update_status(
            db, mismatch_id=mismatch_id, tenant_id=tenant_id,
            new_status=payload.status, changed_by_user_id=current_user.id,
            note=payload.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not m:
        raise HTTPException(status_code=404, detail="Mismatch not found")
    return {
        "mismatch_id": mismatch_id,
        "status": m.status,
        "status_changed_at": m.status_changed_at,
        "changed_by": current_user.email,
    }


# ── P5B-11: Version-Linked Mismatches info ────────────────────────────────────

@router.get("/mismatches/{mismatch_id}/version-info")
def get_mismatch_version_info(
    mismatch_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """P5B-11: Returns BRD version and git commit context for a mismatch."""
    m = db.query(models.Mismatch).filter(
        models.Mismatch.id == mismatch_id,
        models.Mismatch.tenant_id == tenant_id,
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mismatch not found")

    doc_version_info = None
    if m.document_version_id:
        try:
            from app.models.document_version import DocumentVersion
            dv = db.query(DocumentVersion).filter(
                DocumentVersion.id == m.document_version_id
            ).first()
            if dv:
                doc_version_info = {
                    "id": dv.id,
                    "version_number": getattr(dv, "version_number", None),
                    "original_filename": getattr(dv, "original_filename", None),
                    "uploaded_at": str(getattr(dv, "created_at", "")),
                }
        except Exception:
            pass

    return {
        "mismatch_id": mismatch_id,
        "created_at": str(m.created_at),
        "status": m.status,
        "document_version": doc_version_info,
        "created_commit": m.created_commit_hash,
        "created_commit_short": m.created_commit_hash[:8] if m.created_commit_hash else None,
        "resolved_commit": m.resolved_commit_hash,
        "resolved_commit_short": m.resolved_commit_hash[:8] if m.resolved_commit_hash else None,
        "status_changed_at": str(m.status_changed_at) if m.status_changed_at else None,
    }


# ── P5B-12: BA Sign-Off + Compliance Certificate ─────────────────────────────

class SignOffRequest(BaseModel):
    repository_id: Optional[int] = None
    acknowledged_mismatch_ids: List[int] = []
    sign_off_notes: Optional[str] = None
    confirm_acknowledged_criticals: bool = False


@router.post("/{document_id}/sign-off")
def create_sign_off(
    document_id: int,
    payload: SignOffRequest,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    P5B-12: BA signs off on a document validation review.
    Blocks if unresolved critical mismatches exist unless explicitly acknowledged.
    Returns compliance certificate reference.
    """
    document = crud.document.get(db, id=document_id)
    if not document or document.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get current compliance state
    breakdown = crud.mismatch.get_compliance_breakdown(
        db=db, document_id=document_id, tenant_id=tenant_id
    )
    open_count = breakdown.get("total_atoms", 0) - breakdown.get("covered_atoms", 0)
    critical_count = breakdown.get("open_critical_count", 0)
    score = breakdown.get("overall_score")

    has_unresolved_critical = critical_count > 0
    unacknowledged_criticals = 0
    if has_unresolved_critical:
        # Check all critical mismatches are either resolved or in acknowledged list
        from app.models.mismatch import Mismatch as MismatchModel
        critical_mismatches = db.query(MismatchModel).filter(
            MismatchModel.document_id == document_id,
            MismatchModel.tenant_id == tenant_id,
            MismatchModel.severity.in_(["critical", "compliance_risk"]),
            MismatchModel.status.in_(["open", "in_progress", "new"]),
        ).all()
        unacknowledged_criticals = sum(
            1 for m in critical_mismatches
            if m.id not in payload.acknowledged_mismatch_ids
        )

    if unacknowledged_criticals > 0 and not payload.confirm_acknowledged_criticals:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{unacknowledged_criticals} critical mismatch(es) are unresolved and not acknowledged. "
                f"Include their IDs in acknowledged_mismatch_ids or set confirm_acknowledged_criticals=true."
            ),
        )

    # Create sign-off record
    from app.models.brd_sign_off import BRDSignOff
    now = datetime.now()
    sign_off = BRDSignOff(
        tenant_id=tenant_id,
        document_id=document_id,
        repository_id=payload.repository_id,
        signed_by_user_id=current_user.id,
        signed_at=now,
        compliance_score_at_signoff=score,
        open_mismatches_count=open_count,
        critical_mismatches_count=critical_count,
        acknowledged_mismatch_ids=payload.acknowledged_mismatch_ids or [],
        sign_off_notes=payload.sign_off_notes,
        has_unresolved_critical=has_unresolved_critical,
        created_at=now,
    )
    db.add(sign_off)
    db.flush()  # Get ID before hashing

    cert_hash = sign_off.generate_certificate_hash()
    sign_off.certificate_hash = cert_hash
    db.commit()
    db.refresh(sign_off)

    return {
        "sign_off_id": sign_off.id,
        "document_id": document_id,
        "signed_by": current_user.email,
        "signed_at": str(sign_off.signed_at),
        "compliance_score": score,
        "percentage": round((score or 0) * 100),
        "open_mismatches": open_count,
        "critical_mismatches": critical_count,
        "certificate_hash": cert_hash,
        "status": "signed_off",
    }


@router.get("/{document_id}/certificate")
def get_compliance_certificate(
    document_id: int,
    sign_off_id: Optional[int] = Query(None),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """P5B-12: Returns a tamper-evident compliance certificate JSON."""
    from app.models.brd_sign_off import BRDSignOff

    query = db.query(BRDSignOff).filter(
        BRDSignOff.document_id == document_id,
        BRDSignOff.tenant_id == tenant_id,
    )
    if sign_off_id:
        query = query.filter(BRDSignOff.id == sign_off_id)
    sign_off = query.order_by(BRDSignOff.signed_at.desc()).first()

    if not sign_off:
        raise HTTPException(status_code=404, detail="No sign-off found for this document")

    document = crud.document.get(db, id=document_id)

    return {
        "certificate_type": "DOCUMENTATION_COMPLIANCE_CERTIFICATE",
        "certificate_id": f"DOKYDOC-{sign_off.id:06d}",
        "issued_at": str(sign_off.signed_at),
        "tenant": {"id": tenant_id},
        "document": {
            "id": document_id,
            "filename": document.filename if document else None,
            "version": document.version if document else None,
        },
        "validation_summary": {
            "compliance_score": sign_off.compliance_score_at_signoff,
            "percentage": round((sign_off.compliance_score_at_signoff or 0) * 100),
            "open_mismatches": sign_off.open_mismatches_count,
            "critical_mismatches": sign_off.critical_mismatches_count,
            "has_unresolved_critical": sign_off.has_unresolved_critical,
        },
        "acknowledged_risks": {
            "mismatch_ids": sign_off.acknowledged_mismatch_ids or [],
            "count": len(sign_off.acknowledged_mismatch_ids or []),
        },
        "sign_off": {
            "signed_by_user_id": sign_off.signed_by_user_id,
            "signed_by_email": current_user.email,
            "notes": sign_off.sign_off_notes,
        },
        "tamper_evidence": {
            "certificate_hash": sign_off.certificate_hash,
            "algorithm": "SHA-256",
            "note": "Re-compute hash from sign_off fields to verify integrity",
        },
    }


@router.get("/{document_id}/sign-off-history")
def get_sign_off_history(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """P5B-12: Returns all sign-offs for a document, newest first."""
    from app.models.brd_sign_off import BRDSignOff

    document = crud.document.get(db, id=document_id)
    if not document or document.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    sign_offs = db.query(BRDSignOff).filter(
        BRDSignOff.document_id == document_id,
        BRDSignOff.tenant_id == tenant_id,
    ).order_by(BRDSignOff.signed_at.desc()).all()

    return {
        "document_id": document_id,
        "sign_offs": [
            {
                "id": s.id,
                # ARC-BE-02: Include certificate_id so frontend history panel renders it
                "certificate_id": f"DOKYDOC-{s.id:06d}",
                "signed_at": str(s.signed_at),
                "signed_by_user_id": s.signed_by_user_id,
                "compliance_score": s.compliance_score_at_signoff,
                "percentage": round((s.compliance_score_at_signoff or 0) * 100),
                "open_mismatches": s.open_mismatches_count,
                "critical_mismatches": s.critical_mismatches_count,
                "has_unresolved_critical": s.has_unresolved_critical,
                "certificate_hash": s.certificate_hash,
                "sign_off_notes": s.sign_off_notes,
            }
            for s in sign_offs
        ],
        "total": len(sign_offs),
    }


# ── P5C-03: Request Clarification Workflow ────────────────────────────────────

class ClarificationRequest(BaseModel):
    question: str
    assignee_user_id: Optional[int] = None


class ClarificationAnswer(BaseModel):
    answer: str


@router.post("/mismatches/{mismatch_id}/clarification", status_code=201)
def request_clarification(
    mismatch_id: int,
    body: ClarificationRequest,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """P5C-03: BA requests clarification from developer on an ambiguous mismatch."""
    from app.crud.crud_mismatch_clarification import crud_mismatch_clarification
    from app.models.mismatch import Mismatch
    from app.services.notification_service import notify

    mismatch = db.query(Mismatch).filter(
        Mismatch.id == mismatch_id,
        Mismatch.tenant_id == tenant_id,
    ).first()
    if not mismatch:
        raise HTTPException(status_code=404, detail="Mismatch not found")

    try:
        clarification = crud_mismatch_clarification.create(
            db=db,
            tenant_id=tenant_id,
            mismatch_id=mismatch_id,
            requested_by_user_id=current_user.id,
            assignee_user_id=body.assignee_user_id,
            question=body.question,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    notify_user_id = body.assignee_user_id or getattr(mismatch, "owner_id", None)
    if notify_user_id:
        notify(
            db=db,
            tenant_id=tenant_id,
            user_id=notify_user_id,
            notification_type="clarification_requested",
            title=f"Clarification requested on mismatch #{mismatch_id}",
            message=(
                f"{current_user.full_name or current_user.email} has a question: "
                f"{body.question[:200]}"
            ),
            resource_type="mismatch",
            resource_id=mismatch_id,
            details={
                "clarification_id": clarification.id,
                "question": body.question,
                "requested_by": current_user.email,
            },
        )

    return {
        "clarification_id": clarification.id,
        "status": "open",
        "message": "Clarification request created and developer notified",
    }


@router.post("/mismatches/{mismatch_id}/clarification/{clarification_id}/answer")
def answer_clarification(
    mismatch_id: int,
    clarification_id: int,
    body: ClarificationAnswer,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """P5C-03: Developer answers a clarification question; notifies the BA who asked."""
    from app.crud.crud_mismatch_clarification import crud_mismatch_clarification
    from app.services.notification_service import notify

    try:
        clarification = crud_mismatch_clarification.answer(
            db=db,
            clarification_id=clarification_id,
            tenant_id=tenant_id,
            answering_user_id=current_user.id,
            answer=body.answer,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    notify(
        db=db,
        tenant_id=tenant_id,
        user_id=clarification.requested_by_user_id,
        notification_type="clarification_answered",
        title=f"Clarification answered on mismatch #{mismatch_id}",
        message=(
            f"{current_user.full_name or current_user.email} answered: "
            f"{body.answer[:200]}"
        ),
        resource_type="mismatch",
        resource_id=mismatch_id,
        details={
            "clarification_id": clarification.id,
            "answer": body.answer,
            "answered_by": current_user.email,
        },
    )

    return {
        "clarification_id": clarification.id,
        "status": "answered",
        "answer": clarification.answer,
    }


@router.get("/mismatches/{mismatch_id}/clarifications")
def get_clarifications(
    mismatch_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """P5C-03: Return all clarification threads for a mismatch."""
    from app.crud.crud_mismatch_clarification import crud_mismatch_clarification

    items = crud_mismatch_clarification.get_by_mismatch(
        db=db, mismatch_id=mismatch_id, tenant_id=tenant_id,
    )
    return {
        "mismatch_id": mismatch_id,
        "clarifications": [
            {
                "id": c.id,
                "question": c.question,
                "answer": c.answer,
                "status": c.status,
                "requested_by_user_id": c.requested_by_user_id,
                "assignee_user_id": c.assignee_user_id,
                "created_at": c.created_at.isoformat(),
                "answered_at": c.answered_at.isoformat() if c.answered_at else None,
            }
            for c in items
        ],
    }


# ── P5C-04: UAT Checklist Endpoints ──────────────────────────────────────────

class UATCheckBody(BaseModel):
    result: str
    notes: Optional[str] = None


@router.get("/{document_id}/uat-checklist")
def get_uat_checklist(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """P5C-04: Return all UAT checklist items for a document (manual-testability atoms only)."""
    from app.models.uat_checklist_item import UATChecklistItem
    from app.models.requirement_atom import RequirementAtom

    rows = (
        db.query(UATChecklistItem, RequirementAtom)
        .join(RequirementAtom, UATChecklistItem.atom_id == RequirementAtom.id)
        .filter(
            UATChecklistItem.document_id == document_id,
            UATChecklistItem.tenant_id == tenant_id,
        )
        .all()
    )

    total = len(rows)
    checked = sum(1 for item, _ in rows if item.result is not None)
    passed = sum(1 for item, _ in rows if item.result == "pass")
    failed = sum(1 for item, _ in rows if item.result == "fail")

    return {
        "document_id": document_id,
        "summary": {
            "total": total,
            "checked": checked,
            "pending": total - checked,
            "passed": passed,
            "failed": failed,
            "completion_pct": round(checked / total * 100) if total > 0 else 0,
        },
        "items": [
            {
                "id": item.id,
                "atom_id": atom.atom_id,
                "atom_type": atom.atom_type,
                "content": atom.content,
                "criticality": atom.criticality,
                "result": item.result,
                "notes": item.notes,
                "checked_by_user_id": item.checked_by_user_id,
                "checked_at": item.checked_at.isoformat() if item.checked_at else None,
            }
            for item, atom in rows
        ],
    }


@router.post("/{document_id}/uat-checklist/{item_id}/check")
def check_uat_item(
    document_id: int,
    item_id: int,
    body: UATCheckBody,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """P5C-04: BA or QA marks a UAT checklist item as pass/fail/blocked with notes."""
    from app.models.uat_checklist_item import UATChecklistItem

    if body.result not in ("pass", "fail", "blocked"):
        raise HTTPException(status_code=422, detail="result must be pass, fail, or blocked")

    item = db.query(UATChecklistItem).filter(
        UATChecklistItem.id == item_id,
        UATChecklistItem.document_id == document_id,
        UATChecklistItem.tenant_id == tenant_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="UAT checklist item not found")

    item.result = body.result
    item.notes = body.notes
    item.checked_by_user_id = current_user.id
    item.checked_at = datetime.utcnow()
    db.add(item)
    db.commit()

    return {
        "id": item_id,
        "result": body.result,
        "checked_at": item.checked_at.isoformat(),
        "message": f"UAT item marked as {body.result}",
    }


# ── P5C-05: Test Suite Generation ─────────────────────────────────────────────

@router.post("/{document_id}/generate-tests", status_code=202)
def trigger_test_suite_generation(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """P5C-05: Trigger async test suite generation. QA polls GET /download-tests until ready."""
    from app.models.document import Document
    from app.tasks.test_generation_tasks import generate_test_suite

    doc = db.get(Document, document_id)
    if not doc or doc.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    task = generate_test_suite.apply_async(
        args=[document_id, tenant_id, doc.title or "Untitled"]
    )
    return {
        "task_id": task.id,
        "status": "generating",
        "poll_url": f"/validation/{document_id}/download-tests",
    }


@router.get("/{document_id}/download-tests")
def download_test_suite(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """P5C-05: Download generated test suite zip. Returns 202 if still generating, 200 + zip if ready."""
    try:
        from app.core.redis import get_redis_client
        redis = get_redis_client()
        redis_key = f"test_suite:{document_id}:{tenant_id}"
        zip_bytes = redis.get(redis_key)
    except Exception:
        zip_bytes = None

    if not zip_bytes:
        return JSONResponse(
            status_code=202,
            content={
                "status": "generating",
                "message": "Test suite is being generated. Try again in 30 seconds.",
            },
        )

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=dokydoc_tests_doc{document_id}.zip"},
    )


# ── P5C-07: AI Fix Suggestion ─────────────────────────────────────────────────

@router.post("/mismatches/{mismatch_id}/suggest-fix")
async def get_fix_suggestion(
    mismatch_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    P5C-07: Return AI-generated fix suggestion for a mismatch.
    Generated lazily on first call, cached in mismatch.details['suggested_fix'].
    Subsequent calls return cached result without re-calling Gemini.
    """
    from app.services.fix_suggestion_service import fix_suggestion_service

    fix = await fix_suggestion_service.get_or_generate(
        db=db, mismatch_id=mismatch_id, tenant_id=tenant_id,
    )
    return {"mismatch_id": mismatch_id, "suggested_fix": fix}


@router.delete("/mismatches/{mismatch_id}/suggest-fix", status_code=204)
def clear_fix_suggestion(
    mismatch_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> None:
    """P5C-07: Clear cached fix suggestion to force regeneration on next POST."""
    from app.models.mismatch import Mismatch

    mismatch = db.query(Mismatch).filter(
        Mismatch.id == mismatch_id,
        Mismatch.tenant_id == tenant_id,
    ).first()
    if not mismatch:
        raise HTTPException(status_code=404, detail="Mismatch not found")

    updated = dict(mismatch.details or {})
    updated.pop("suggested_fix", None)
    mismatch.details = updated
    db.add(mismatch)
    db.commit()


# ── P5C-08: Compliance Score Trend ────────────────────────────────────────────

@router.get("/{document_id}/compliance-trend")
def get_compliance_trend(
    document_id: int,
    days: int = Query(default=30, ge=7, le=365),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """P5C-08: Return compliance score snapshots for the last N days for trend chart."""
    from app.models.compliance_score_snapshot import ComplianceScoreSnapshot

    since = date.today() - timedelta(days=days)
    snapshots = db.query(ComplianceScoreSnapshot).filter(
        ComplianceScoreSnapshot.document_id == document_id,
        ComplianceScoreSnapshot.tenant_id == tenant_id,
        ComplianceScoreSnapshot.snapshot_date >= since,
    ).order_by(ComplianceScoreSnapshot.snapshot_date.asc()).all()

    if not snapshots:
        return {
            "document_id": document_id,
            "days": days,
            "trend": [],
            "direction": "neutral",
            "change_pct": 0.0,
            "current_score": None,
            "baseline_score": None,
        }

    trend_data = [
        {
            "date": s.snapshot_date.isoformat(),
            "score": s.score_percentage,
            "total_atoms": s.total_atoms,
            "covered_atoms": s.covered_atoms,
            "open_mismatches": s.open_mismatches,
            "critical_mismatches": s.critical_mismatches,
        }
        for s in snapshots
    ]

    first_score = snapshots[0].score_percentage
    last_score = snapshots[-1].score_percentage
    change = round(last_score - first_score, 1)
    direction = "improving" if change > 1 else "degrading" if change < -1 else "stable"

    return {
        "document_id": document_id,
        "days": days,
        "trend": trend_data,
        "direction": direction,
        "change_pct": change,
        "current_score": last_score,
        "baseline_score": first_score,
    }
