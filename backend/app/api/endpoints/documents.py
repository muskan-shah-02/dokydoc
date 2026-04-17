# This is the final, updated content for your file at:
# backend/app/api/endpoints/documents.py

import shutil
from pathlib import Path
from typing import List, Any
import uuid
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request, Response, Query
from fastapi.responses import FileResponse # Added for download endpoint
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app import crud, models, schemas
from app.api import deps
from app.core.config import settings
from app.core.logging import LoggerMixin
from app.core.exceptions import DocumentProcessingException, ValidationException
from app.middleware.rate_limiter import limiter, RateLimits

# --- NEW: Import our Celery task ---
# The "Import could not be resolved" error is OK, it will work in Docker
from app.tasks import process_document_pipeline

class DocumentEndpoints(LoggerMixin):
    """Document endpoints with enhanced logging and error handling."""
    
    def __init__(self):
        super().__init__()
        self.upload_dir = Path("/app/uploads")
        self.upload_dir.mkdir(exist_ok=True)

# Create instance for use in endpoints
document_endpoints = DocumentEndpoints()

router = APIRouter()

# --- The process_document_pipeline function has been MOVED to app/tasks.py ---


@router.get("/")
def read_documents(
    tenant_id: int = Depends(deps.get_tenant_id),  # SPRINT 2: Tenant context
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    initiative_id: Optional[int] = Query(None, description="Filter by initiative (project) ID"),
    cursor: Optional[int] = Query(None, description="Cursor (last document ID from previous page)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
) -> Any:
    """
    Retrieve documents for the current tenant with cursor-based pagination.

    SPRINT 2: Documents are scoped to tenant, not just owner.
    SPRINT 4: Optional initiative_id filtering via project context.
    """
    from app.api.pagination import paginate_query
    from app.models.document import Document

    document_endpoints.logger.info(f"Fetching documents for tenant {tenant_id}, user {current_user.id}, initiative_id={initiative_id}")

    if initiative_id:
        query = crud.document.build_initiative_query(
            db=db,
            initiative_id=initiative_id,
            tenant_id=tenant_id,
        )
    else:
        query = crud.document.build_owner_query(
            db=db,
            owner_id=current_user.id,
            tenant_id=tenant_id,
        )

    page = paginate_query(query, Document.id, cursor=cursor, page_size=page_size)

    # Serialize SQLAlchemy objects → plain dicts so FastAPI can JSON-encode them
    serialized = []
    for doc in page["items"]:
        serialized.append(schemas.Document.model_validate(doc).model_dump())

    document_endpoints.logger.info(f"Retrieved {len(serialized)} documents for tenant {tenant_id}")
    return {**page, "items": serialized}


@router.get("/{document_id}", response_model=schemas.Document)
def read_document(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),  # SPRINT 2: Tenant context
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a single document by ID.

    SPRINT 2: Document must belong to the current tenant.
    Returns 404 (not 403) if document doesn't exist in tenant (Schrödinger's Document pattern).
    """
    document_endpoints.logger.info(f"Fetching document {document_id} for tenant {tenant_id}")

    # SPRINT 2: get() with tenant_id ensures cross-tenant access is impossible
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        # CRITICAL: Return 404 (not 403) to avoid leaking document existence
        document_endpoints.logger.warning(f"Document {document_id} not found in tenant {tenant_id}")
        raise HTTPException(status_code=404, detail="Document not found")

    return document


@router.get("/{document_id}/segments", response_model=List[schemas.DocumentSegment])
def read_document_segments(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),  # SPRINT 2: Tenant context
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get all segments for a specific document.

    SPRINT 2: Segments are scoped to tenant.
    SPRINT 3 FIX (FLAW-11-B): N+1 query eliminated — uses eager-loaded relationships.
    """
    document_endpoints.logger.info(f"Fetching segments for document {document_id}, tenant {tenant_id}")

    # SPRINT 2: Verify document exists in tenant (404 if not)
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # SPRINT 2: Get segments with tenant filtering
    segments = crud.document_segment.get_multi_by_document(
        db=db,
        document_id=document_id,
        tenant_id=tenant_id,  # SPRINT 2: Mandatory tenant filtering
        limit=50
    )

    # SPRINT 3 FIX (FLAW-11-B): Use eager-loaded analysis_results from joinedload
    # instead of N+1 queries per segment. The relationship is already loaded by
    # crud.document_segment.get_multi_by_document() which uses joinedload.
    segments_with_analysis = [
        segment for segment in segments
        if segment.analysis_results and any(
            ar.structured_data for ar in segment.analysis_results
        )
    ]
    segments_with_analysis.sort(key=lambda x: x.id)

    document_endpoints.logger.info(
        f"Retrieved {len(segments_with_analysis)} segments with analysis for document {document_id} "
        f"(filtered from {len(segments)} total)"
    )
    return segments_with_analysis


@router.get("/{document_id}/analysis")
def get_document_analysis(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),  # SPRINT 2: Tenant context
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get complete document analysis in a single request.

    SPRINT 2: Analysis is scoped to tenant.
    """
    document_endpoints.logger.info(f"Fetching complete analysis for document {document_id}, tenant {tenant_id}")

    # SPRINT 2: Verify document exists in tenant
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # SPRINT 2: Get segments with tenant filtering
    segments = crud.document_segment.get_multi_by_document(
        db=db,
        document_id=document_id,
        tenant_id=tenant_id,  # SPRINT 2: Mandatory tenant filtering
        limit=50
    )

    # SPRINT 3 FIX (FLAW-11-B): Use eager-loaded analysis_results instead of N+1 queries
    segments_with_analysis = []
    analysis_stats = {"analyzed": 0, "failed": 0, "total": len(segments)}

    for segment in segments:
        # Use the already-loaded relationship (joinedload in CRUD)
        successful_results = [
            ar for ar in (segment.analysis_results or [])
            if ar.structured_data
        ]

        if successful_results:
            segments_with_analysis.append({
                "segment": schemas.DocumentSegment.model_validate(segment).model_dump(),
                "analysis_result": schemas.AnalysisResult.model_validate(successful_results[0]).model_dump(),
                "status": "analyzed"
            })
            analysis_stats["analyzed"] += 1
        else:
            analysis_stats["failed"] += 1

    segments_with_analysis.sort(key=lambda x: x["segment"]["id"])

    result = {
        "document": schemas.Document.model_validate(document).model_dump(),
        "composition": document.composition_analysis,
        "segments": segments_with_analysis,
        "stats": analysis_stats
    }

    document_endpoints.logger.info(
        f"Retrieved complete analysis for document {document_id}: "
        f"{analysis_stats['analyzed']} analyzed, {analysis_stats['failed']} failed, {analysis_stats['total']} total"
    )
    return result


# --- NEW ENDPOINT (Fix for UX-02 & DAE-01) ---
@router.get("/{document_id}/status", response_model=schemas.DocumentStatus)
def get_document_status(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),  # SPRINT 2: Tenant context
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Gets the current parsing status, progress, and error for a document.

    SPRINT 2: Document status is scoped to tenant.
    """
    # SPRINT 2: Verify document exists in tenant
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # This now returns the error_message as well, per the architect's plan
    return {
        "status": document.status or "unknown",
        "progress": document.progress or 0,
        "error_message": document.error_message or None
    }


# --- NEW ENDPOINT (Fix for FEAT-01) ---
@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),  # SPRINT 2: Tenant context
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Serves the original uploaded file for download.

    SPRINT 2: Download is scoped to tenant.
    """
    logger = document_endpoints.logger
    logger.info(f"Download request for document {document_id}, tenant {tenant_id}")

    # SPRINT 2: Verify document exists in tenant
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        logger.warning(f"Document {document_id} not found in tenant {tenant_id}")
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(document.storage_path)
    if not file_path.is_file():
        logger.error(f"File not found on disk for document {document_id}: {document.storage_path}")
        raise HTTPException(status_code=404, detail="File not found")

    # Return a FileResponse to send the actual file
    return FileResponse(
        path=file_path,
        filename=document.filename,
        media_type="application/octet-stream"
    )


@router.post("/upload", response_model=schemas.Document)
@limiter.limit(RateLimits.UPLOAD)  # API-01 FIX: Rate limit uploads (10/min, 50/hour)
async def upload_document(
    request: Request,  # API-01 FIX: Required for rate limiter
    response: Response,  # Required for rate limiter to inject headers
    *,
    tenant_id: int = Depends(deps.get_tenant_id),  # SPRINT 2: Tenant context
    db: Session = Depends(deps.get_db),
    document_type: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
    initiative_id: Optional[int] = Form(None),  # SPRINT 4: Auto-link to project
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Upload a new document. This only saves the file and creates the
    database record. It does NOT trigger the analysis.
    This endpoint is fast and will not time out. (Fix for A-01)

    SPRINT 2: Document is created in the current tenant.

    Rate Limit: 10 uploads/minute, 50 uploads/hour per user
    """
    logger = document_endpoints.logger

    try:
        if not file.filename:
            raise ValidationException("No filename provided")

        file_extension = Path(file.filename).suffix.lower()
        # CONFIG-01 FIX: Use settings instead of hardcoded extensions
        allowed_extensions = settings.ALLOWED_EXTENSIONS

        if file_extension not in allowed_extensions:
            raise ValidationException(f"File type {file_extension} not supported. Allowed types: {', '.join(allowed_extensions)}")

        logger.info(f"Starting upload for file: {file.filename}, type: {document_type}, version: {version}, tenant: {tenant_id}")

        unique_filename = f"{uuid.uuid4()}{file_extension}"
        storage_path = document_endpoints.upload_dir / unique_filename
        file_size_kb = 0

        try:
            with storage_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            file_size_bytes = os.path.getsize(storage_path)
            file_size_kb = round(file_size_bytes / 1024)
            logger.info(f"File saved to {storage_path}, size: {file_size_kb} KB")

            # Hard block only if above the configured maximum (default 2GB)
            if file_size_bytes > settings.MAX_FILE_SIZE:
                storage_path.unlink(missing_ok=True)
                raise ValidationException(
                    f"File size {file_size_kb} KB exceeds maximum allowed "
                    f"{settings.MAX_FILE_SIZE // (1024 * 1024)} MB"
                )
        finally:
            file.file.close()

        # Soft warning for large files (default >100MB) — logged but not blocked
        file_size_warning = None
        if file_size_bytes > settings.FILE_SIZE_WARN_BYTES:
            file_size_warning = (
                f"Large file ({file_size_kb // 1024} MB) — processing may take longer than usual"
            )
            logger.warning(f"Large file upload: {file.filename}, {file_size_kb} KB, tenant {tenant_id}")

        # The user's model (from last step) has raw_text as nullable=False.
        # We must provide a non-null value. An empty string is the most
        # correct "empty" value for a text field.
        document_in = schemas.DocumentCreate(
            filename=file.filename,
            document_type=document_type,
            version=version,
            raw_text="",  # Provide empty string for non-null field
            owner_id=current_user.id,
            storage_path=str(storage_path),
            status="uploaded",
            progress=0,
            file_size_kb=file_size_kb
        )

        # SPRINT 2: Create document with tenant_id
        document = crud.document.create_with_owner(
            db=db,
            obj_in=document_in,
            owner_id=current_user.id,
            storage_path=str(storage_path),
            tenant_id=tenant_id  # SPRINT 2: Mandatory tenant assignment
        )

        # SPRINT 4: Auto-link document to initiative (project) if specified
        if initiative_id:
            try:
                from app.schemas.initiative import InitiativeAssetCreate
                crud.initiative_asset.create_asset(
                    db=db,
                    obj_in=InitiativeAssetCreate(
                        initiative_id=initiative_id,
                        asset_type="DOCUMENT",
                        asset_id=document.id,
                    ),
                    tenant_id=tenant_id
                )
                logger.info(f"Document {document.id} auto-linked to initiative {initiative_id}")
            except Exception as e:
                logger.warning(f"Failed to auto-link document {document.id} to initiative {initiative_id}: {e}")

        logger.info(f"Document {document.id} uploaded successfully to tenant {tenant_id}. Ready for analysis.")
        if file_size_warning:
            # Attach warning as a response header so clients can surface it
            response.headers["X-File-Size-Warning"] = file_size_warning
        return document

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during document upload: {e}")
        raise DocumentProcessingException(f"Failed to upload document: {str(e)}")


@router.post("/{document_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_document(
    document_id: int,
    *,
    tenant_id: int = Depends(deps.get_tenant_id),  # SPRINT 2: Tenant context
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Triggers the full processing pipeline for an uploaded document.
    This now uses Celery instead of BackgroundTasks. (Fix for A-01)

    SPRINT 2: Analysis is scoped to tenant. Celery task receives tenant_id.
    SPRINT 2 Phase 4: Billing enforcement added - checks balance before analysis.
    """
    logger = document_endpoints.logger
    logger.info(f"Received analysis request for document {document_id}, tenant {tenant_id}")

    # SPRINT 2: Verify document exists in tenant
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # We allow re-analysis on completed or failed documents
    if document.status in ["processing", "parsing", "analyzing", "pass_1_composition", "pass_2_segmenting", "pass_3_extraction"]:
        logger.warning(f"Analysis for document {document.id} already in progress. Status: {document.status}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Analysis is already in progress. Status: {document.status}"
        )

    if not document.storage_path:
        logger.error(f"Document {document.id} has no storage_path, cannot analyze.")
        raise HTTPException(status_code=500, detail="Document file is missing.")

    # SPRINT 2 Phase 4: Billing enforcement - check if tenant can afford analysis
    from app.services.billing_enforcement_service import (
        billing_enforcement_service,
        InsufficientBalanceException,
        MonthlyLimitExceededException
    )

    try:
        # Estimate cost based on document size
        estimated_cost = billing_enforcement_service.estimate_analysis_cost(
            document_size_kb=document.file_size_kb or 100,  # Default 100KB if not set
            document_type=document.document_type or "PRD"
        )

        # Check if tenant can afford it
        affordability_check = billing_enforcement_service.check_can_afford_analysis(
            db=db,
            tenant_id=tenant_id,
            estimated_cost_inr=estimated_cost
        )

        logger.info(
            f"Billing check passed for document {document.id}: "
            f"estimated_cost=₹{estimated_cost}, billing_type={affordability_check['billing_type']}"
        )

    except InsufficientBalanceException as e:
        logger.warning(f"Analysis blocked - insufficient balance: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "insufficient_balance",
                "message": e.message,
                "required_inr": e.required,
                "available_inr": e.available,
                "shortage_inr": e.required - e.available
            }
        )

    except MonthlyLimitExceededException as e:
        logger.warning(f"Analysis blocked - monthly limit exceeded: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "monthly_limit_exceeded",
                "message": e.message,
                "monthly_limit_inr": e.limit,
                "current_month_cost": e.current,
                "overage_inr": e.current - e.limit
            }
        )

    # Set status to "processing" and reset any old errors
    crud.document.update(
        db=db,
        db_obj=document,
        obj_in={"status": "processing", "progress": 10, "error_message": None}
    )

    # SPRINT 2: Pass tenant_id to Celery task for tenant-scoped operations
    process_document_pipeline.delay(
        document_id=document.id,
        storage_path=str(document.storage_path),
        tenant_id=tenant_id  # SPRINT 2: Critical for Phase 6
    )

    logger.info(f"Analysis for document {document.id} (tenant {tenant_id}) has been scheduled (202 Accepted)")
    return {
        "message": "Document analysis has been scheduled",
        "estimated_cost_inr": estimated_cost
    }

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),  # SPRINT 2: Tenant context
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> None:
    """
    Delete a document from the database and the filesystem.

    SPRINT 2: Deletion is scoped to tenant (cannot delete other tenants' documents).
    """
    document_endpoints.logger.info(f"Delete request for document {document_id}, tenant {tenant_id}")

    # SPRINT 2: Verify document exists in tenant
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # 1. Delete the file from disk
    if document.storage_path:
        file_path = Path(document.storage_path)
        if file_path.exists():
            try:
                os.remove(file_path)
                document_endpoints.logger.info(f"Deleted file: {file_path}")
            except OSError as e:
                document_endpoints.logger.error(f"Error deleting file {file_path}: {e}")
                # We continue to delete the DB record even if file delete fails
                # to prevent "ghost" records.

    # 2. Delete from Database with tenant_id
    # Note: Cascading deletes in your DB models should handle segments/results
    crud.document.remove(db=db, id=document_id, tenant_id=tenant_id)

    document_endpoints.logger.info(f"Document {document_id} deleted successfully from tenant {tenant_id}")
    return None
# --- Document Version Comparison Endpoints ---

@router.get("/{document_id}/versions")
def list_document_versions(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """List all saved versions for a document, newest first."""
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.crud.crud_document_version import crud_document_version
    versions = crud_document_version.get_by_document(
        db, document_id=document_id, tenant_id=tenant_id
    )

    # Enrich with uploader email
    result = []
    for v in versions:
        user = db.query(models.User).filter(models.User.id == v.uploaded_by_id).first()
        result.append({
            "id": v.id,
            "document_id": v.document_id,
            "version_number": v.version_number,
            "content_hash": v.content_hash,
            "file_size": v.file_size,
            "original_filename": v.original_filename,
            "uploaded_by_id": v.uploaded_by_id,
            "uploaded_by_email": user.email if user else None,
            "created_at": v.created_at.isoformat(),
        })
    return {"versions": result, "total": len(result)}


@router.post("/{document_id}/versions/diff")
def diff_document_versions(
    document_id: int,
    payload: dict,  # {version_a: int, version_b: int}
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Compute a side-by-side line diff between two versions.
    Returns structured diff lines for rendering in the frontend diff viewer.
    """
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.crud.crud_document_version import crud_document_version

    version_a_num = payload.get("version_a")
    version_b_num = payload.get("version_b")
    if not version_a_num or not version_b_num:
        raise HTTPException(status_code=422, detail="version_a and version_b are required")

    ver_a = crud_document_version.get_by_version_number(
        db, document_id=document_id, tenant_id=tenant_id, version_number=version_a_num
    )
    ver_b = crud_document_version.get_by_version_number(
        db, document_id=document_id, tenant_id=tenant_id, version_number=version_b_num
    )

    if not ver_a:
        raise HTTPException(status_code=404, detail=f"Version {version_a_num} not found")
    if not ver_b:
        raise HTTPException(status_code=404, detail=f"Version {version_b_num} not found")

    return crud_document_version.compute_diff(
        text_a=ver_a.content_text,
        text_b=ver_b.content_text,
        version_a=version_a_num,
        version_b=version_b_num,
        document_id=document_id,
    )


@router.post("/{document_id}/versions/{version_number}/restore", response_model=schemas.Document)
def restore_document_version(
    document_id: int,
    version_number: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Restore a document to a previous version.
    Creates a NEW version entry with the old content (non-destructive).
    """
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.crud.crud_document_version import crud_document_version

    target_version = crud_document_version.get_by_version_number(
        db, document_id=document_id, tenant_id=tenant_id, version_number=version_number
    )
    if not target_version:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found")

    # Create a new version with the old content (non-destructive restore)
    new_version = crud_document_version.create(
        db,
        document_id=document_id,
        tenant_id=tenant_id,
        content_text=target_version.content_text,
        original_filename=target_version.original_filename or document.filename,
        file_size=target_version.file_size,
        uploaded_by_id=current_user.id,
    )

    # Update document raw_text to reflect the restored content
    crud.document.update(
        db=db,
        db_obj=document,
        obj_in={"raw_text": target_version.content_text, "status": "completed"},
    )

    document_endpoints.logger.info(
        f"Document {document_id} restored to version {version_number} as new version {new_version.version_number}"
    )
    return document


@router.post("/{document_id}/stop")
def stop_document_analysis(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),  # SPRINT 2: Tenant context
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Signals the analysis engine to stop processing this document.

    SPRINT 2: Stop signal is scoped to tenant.
    """
    # SPRINT 2: Verify document exists in tenant
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status not in ["processing", "analyzing", "parsing", "pass_1_composition", "pass_2_segmenting", "pass_3_extraction"]:
        raise HTTPException(status_code=400, detail="Document is not currently running.")

    # We set a special status. The worker loop will see this and exit.
    crud.document.update(
        db=db,
        db_obj=document,
        obj_in={"status": "stopping"}
    )

    return {"message": "Stop signal sent. Analysis will halt shortly."}


# ── P5B-01: Atom Diff Endpoint ────────────────────────────────────────────────

@router.get("/{document_id}/atom-diff")
def get_atom_diff(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    P5B-01: Returns the last atom-level diff result for a document.
    Used by frontend to show "BRD Updated: 3 new requirements, 2 removed" banner.
    """
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # ARC-DB-04: last_atom_diff is written by validation_service.atomize_document()
    # after every re-atomization (diff.summary()) and consumed here.
    diff = getattr(document, "last_atom_diff", None) or {}
    has_diff = bool(diff.get("added") or diff.get("modified") or diff.get("deleted"))
    return {
        "document_id": document_id,
        "has_diff": has_diff,
        "atom_diff": diff if has_diff else None,
        "message": None if has_diff else "No diff available — document not yet re-uploaded",
    }


# ── P5C-01: File Suggestion Endpoints ────────────────────────────────────────

@router.get("/{document_id}/file-suggestions")
def get_file_suggestions(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    P5C-01: Returns AI-generated file suggestions for a document.
    Each suggestion names a code file the developer should upload to cover specific BRD atoms.
    """
    from app.models.file_suggestion import FileSuggestion

    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    suggestions = (
        db.query(FileSuggestion)
        .filter_by(document_id=document_id, tenant_id=tenant_id)
        .order_by(FileSuggestion.atom_count.desc())
        .all()
    )
    return {
        "document_id": document_id,
        "total": len(suggestions),
        "suggestions": [
            {
                "id": s.id,
                "suggested_filename": s.suggested_filename,
                "reason": s.reason,
                "atom_ids": s.atom_ids,
                "atom_count": s.atom_count,
                "fulfilled": s.fulfilled_by_component_id is not None,
                "fulfilled_by_component_id": s.fulfilled_by_component_id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in suggestions
        ],
    }


class UploadRequestBody(BaseModel):
    user_ids: List[int] = []                 # P5C-02: specific user IDs to notify
    message: Optional[str] = None           # optional custom message from BA
    suggested_filenames: List[str] = []     # P5C-02: pre-filled from P5C-01 suggestions


@router.post("/{document_id}/request-uploads", status_code=202)
async def request_uploads(
    document_id: int,
    body: Optional[UploadRequestBody] = None,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    P5C-01: Triggers (or re-triggers) AI file suggestion engine.
    P5C-02: When body contains user_ids, also notifies those users with upload request.
    """
    from app.services.file_suggestion_service import file_suggestion_service

    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Always refresh suggestions
    try:
        stored = await file_suggestion_service.generate_and_store(
            db, document_id=document_id, tenant_id=tenant_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File suggestion generation failed: {e}")

    # P5C-02: Notify team members if user_ids provided
    notified: List[int] = []
    if body and body.user_ids:
        from app.services.notification_service import notify
        filenames_str = ", ".join(body.suggested_filenames) if body.suggested_filenames else "relevant code files"
        custom_msg = body.message or ""
        base_msg = (
            f"{current_user.full_name or current_user.email} has requested that you upload "
            f"{filenames_str} for BRD validation of '{document.title}'."
        )
        full_message = f"{base_msg} {custom_msg}".strip()

        valid_users = db.query(models.User).filter(
            models.User.id.in_(body.user_ids),
            models.User.tenant_id == tenant_id,
            models.User.is_active == True,
        ).all()
        valid_ids = {u.id for u in valid_users}

        for uid in body.user_ids:
            if uid not in valid_ids:
                continue
            notify(
                db=db,
                tenant_id=tenant_id,
                user_id=uid,
                notification_type="upload_request",
                title=f"Code upload requested for '{document.title}'",
                message=full_message,
                resource_type="document",
                resource_id=document_id,
                details={
                    "requested_by_user_id": current_user.id,
                    "requested_by_name": current_user.full_name or current_user.email,
                    "suggested_filenames": body.suggested_filenames,
                    "document_title": document.title,
                },
            )
            notified.append(uid)

    return {
        "message": f"Generated {len(stored)} file suggestions" + (f"; notified {len(notified)} user(s)" if notified else ""),
        "total": len(stored),
        "notified_user_ids": notified,
    }


# ── P5C-02: Team Members Endpoint ─────────────────────────────────────────────

@router.get("/{document_id}/team-members")
def get_document_team_members(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    P5C-02: Return active users in the tenant for the BA to select upload recipients.
    Sorted by role: tech_lead first, then developer, then others.
    """
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    users = db.query(models.User).filter(
        models.User.tenant_id == tenant_id,
        models.User.is_active == True,
        models.User.id != current_user.id,
    ).all()

    def role_sort_key(u):
        roles = u.roles or []
        if "tech_lead" in roles:
            return 0
        if "developer" in roles:
            return 1
        return 2

    users.sort(key=role_sort_key)
    return {
        "team_members": [
            {"id": u.id, "name": u.full_name or u.email, "email": u.email, "roles": u.roles}
            for u in users
        ]
    }