# This is the final, updated content for your file at:
# backend/app/api/endpoints/documents.py

import shutil
from pathlib import Path
from typing import List, Any
import uuid
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request
from fastapi.responses import FileResponse # Added for download endpoint
from sqlalchemy.orm import Session

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


@router.get("/", response_model=List[schemas.Document])
def read_documents(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Retrieve all documents owned by the current user."""
    document_endpoints.logger.info(f"Fetching documents for user {current_user.id}")
    documents = crud.document.get_multi_by_owner(db=db, owner_id=current_user.id)
    document_endpoints.logger.info(f"Retrieved {len(documents)} documents for user {current_user.id}")
    return documents


@router.get("/{document_id}", response_model=schemas.Document)
def read_document(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get a single document by ID."""
    document_endpoints.logger.info(f"Fetching document {document_id} for user {current_user.id}")
    
    document = crud.document.get(db=db, id=document_id)
    if not document:
        document_endpoints.logger.warning(f"Document {document_id} not found")
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        document_endpoints.logger.warning(f"User {current_user.id} attempted to access document {document_id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to access this document")
    
    return document


@router.get("/{document_id}/segments", response_model=List[schemas.DocumentSegment])
def read_document_segments(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get all segments for a specific document."""
    # (Note: This is still the N+1 query from bug BE-02. We'll fix that later.)
    document_endpoints.logger.info(f"Fetching segments for document {document_id}")
    
    document = crud.document.get(db=db, id=document_id)
    if not document:
        document_endpoints.logger.warning(f"Document {document_id} not found")
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        document_endpoints.logger.warning(f"User {current_user.id} attempted to access segments for document {document_id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to access this document")
    
    segments = crud.document_segment.get_multi_by_document(db=db, document_id=document_id, limit=50)
    
    segments_with_analysis = []
    for segment in segments:
        analysis_result = crud.analysis_result.get_by_segment(db=db, segment_id=segment.id)
        if analysis_result and analysis_result.structured_data:
            segments_with_analysis.append(segment)
    
    segments_with_analysis.sort(key=lambda x: x.id)
    
    document_endpoints.logger.info(f"Retrieved {len(segments_with_analysis)} segments with analysis results for document {document_id} (filtered from {len(segments)} total)")
    return segments_with_analysis


@router.get("/{document_id}/analysis")
def get_document_analysis(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get complete document analysis in a single request."""
    document_endpoints.logger.info(f"Fetching complete analysis for document {document_id}")
    
    document = crud.document.get(db=db, id=document_id)
    if not document:
        document_endpoints.logger.warning(f"Document {document_id} not found")
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        document_endpoints.logger.warning(f"User {current_user.id} attempted to access analysis for document {document_id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to access this document")
    
    # (This is also part of the N+1 problem)
    segments = crud.document_segment.get_multi_by_document(db=db, document_id=document_id, limit=50)
    
    segments_with_analysis = []
    analysis_stats = {"analyzed": 0, "failed": 0, "total": len(segments)}
    
    for segment in segments:
        analysis_result = crud.analysis_result.get_by_segment(db=db, segment_id=segment.id)
        
        if analysis_result and analysis_result.structured_data:
            segments_with_analysis.append({
                "segment": schemas.DocumentSegment.model_validate(segment).model_dump(),
                "analysis_result": schemas.AnalysisResult.model_validate(analysis_result).model_dump(),
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
    
    document_endpoints.logger.info(f"Retrieved complete analysis for document {document_id}: {analysis_stats['analyzed']} analyzed, {analysis_stats['failed']} failed, {analysis_stats['total']} total")
    return result


# --- NEW ENDPOINT (Fix for UX-02 & DAE-01) ---
@router.get("/{document_id}/status", response_model=schemas.DocumentStatus)
def get_document_status(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Gets the current parsing status, progress, and error for a document."""
    document = crud.document.get(db=db, id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this document")
    
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
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Serves the original uploaded file for download."""
    logger = document_endpoints.logger
    logger.info(f"Download request for document {document_id} by user {current_user.id}")
    
    document = crud.document.get(db=db, id=document_id)
    if not document:
        logger.warning(f"Document {document_id} not found")
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to download document {document_id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to access this document")

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
    *,
    db: Session = Depends(deps.get_db),
    document_type: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Upload a new document. This only saves the file and creates the
    database record. It does NOT trigger the analysis.
    This endpoint is fast and will not time out. (Fix for A-01)

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
        
        logger.info(f"Starting upload for file: {file.filename}, type: {document_type}, version: {version}")
        
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
        
        document = crud.document.create_with_owner(
            db=db, 
            obj_in=document_in, 
            owner_id=current_user.id,
            storage_path=str(storage_path) # create_with_owner might not need this
        )
        
        logger.info(f"Document {document.id} uploaded successfully. Ready for analysis.")
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
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Triggers the full processing pipeline for an uploaded document.
    This now uses Celery instead of BackgroundTasks. (Fix for A-01)
    """
    logger = document_endpoints.logger
    logger.info(f"Received analysis request for document {document_id} from user {current_user.id}")
    
    document = crud.document.get(db=db, id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this document")
    
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
        
    # Set status to "processing" and reset any old errors
    crud.document.update(
        db=db, 
        db_obj=document, 
        obj_in={"status": "processing", "progress": 10, "error_message": None}
    )
    
    # --- THIS IS THE KEY CHANGE ---
    # We call .delay() on our task with simple, serializable arguments
    process_document_pipeline.delay(
        document_id=document.id, 
        storage_path=str(document.storage_path)
    )
    # --- END OF KEY CHANGE ---
    
    logger.info(f"Analysis for document {document.id} has been scheduled (202 Accepted)")
    return {"message": "Document analysis has been scheduled"}

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> None:
    """
    Delete a document from the database and the filesystem.
    """
    document_endpoints.logger.info(f"Delete request for document {document_id} by user {current_user.id}")
    
    document = crud.document.get(db=db, id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        document_endpoints.logger.warning(f"User {current_user.id} attempted to delete document {document_id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")

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

    # 2. Delete from Database
    # Note: Cascading deletes in your DB models should handle segments/results
    crud.document.remove(db=db, id=document_id)
    
    document_endpoints.logger.info(f"Document {document_id} deleted successfully")
    return None
@router.post("/{document_id}/stop")
def stop_document_analysis(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Signals the analysis engine to stop processing this document.
    """
    document = crud.document.get(db=db, id=document_id)
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