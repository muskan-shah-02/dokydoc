# This is the final, updated content for your file at:
# backend/app/api/endpoints/documents.py

import shutil
from pathlib import Path
from typing import List, Any
import uuid
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request, Response, Query
from fastapi.responses import FileResponse # Added for download endpoint
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

    document_endpoints.logger.info(f"Retrieved {len(page['items'])} documents for tenant {tenant_id}")
    return page


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
            file_size_kb = round(os.path.getsize(storage_path) / 1024)
            logger.info(f"File saved to {storage_path}, size: {file_size_kb} KB")
        finally:
            file.file.close()

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