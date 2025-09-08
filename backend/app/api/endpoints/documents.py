# This is the final, updated content for your file at:
# backend/app/api/endpoints/documents.py

import shutil
from pathlib import Path
from typing import List, Any
import uuid
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.services.document_parser import MultiModalDocumentParser
from app.services.analysis_service import DocumentAnalysisEngine
from app.core.logging import LoggerMixin
from app.core.exceptions import DocumentProcessingException, ValidationException

class DocumentEndpoints(LoggerMixin):
    """Document endpoints with enhanced logging and error handling."""
    
    def __init__(self):
        super().__init__()
        self.upload_dir = Path("/app/uploads")
        self.upload_dir.mkdir(exist_ok=True)

# Create instance for use in endpoints
document_endpoints = DocumentEndpoints()

router = APIRouter()

# --- This is our updated background task function with full pipeline ---
async def process_document_pipeline(db: Session, document_id: int, storage_path: str):
    """
    This function runs in the background and orchestrates the full pipeline:
    1. Parse text from the document using Gemini parser.
    2. Trigger the multi-pass Document Analysis Engine (DAE).
    """
    logger = document_endpoints.logger
    logger.info(f"Pipeline started for document_id: {document_id}")
    
    document = crud.document.get(db=db, id=document_id)
    if not document:
        logger.error(f"Background task could not find document_id: {document_id}")
        return

    # --- Step 1: Text Extraction ---
    try:
        # Initialize the parser
        parser = MultiModalDocumentParser()
        
        # Update progress to 25% before starting the API call
        crud.document.update(db=db, db_obj=document, obj_in={"progress": 25, "status": "parsing"})
        
        # Use the new multi-modal parser with image analysis
        content = await parser.parse_with_images(storage_path)
        
        # Update progress to 50% after parsing completion
        update_data = {
            "raw_text": content,  # Updated to use raw_text instead of content
            "status": "analyzing" if content else "parsing_failed",
            "progress": 50 if content else 100
        }
        document = crud.document.update(db=db, db_obj=document, obj_in=update_data)
        logger.info(f"Parsing complete for document {document_id}. Starting multi-pass analysis.")
        
        # Stop the pipeline if parsing fails
        if not content:
            logger.warning(f"Parsing failed for document {document_id} - no content extracted")
            return
            
    except Exception as e:
        logger.error(f"An error occurred during parsing for document {document_id}: {e}")
        # Mark the document as failed in case of an error
        crud.document.update(db=db, db_obj=document, obj_in={"status": "parsing_failed", "progress": 100})
        return # Stop the pipeline if parsing fails

    # --- Step 2: Multi-Pass Analysis ---
    try:
        # Initialize the Document Analysis Engine
        dae = DocumentAnalysisEngine()
        
        # Use the new Document Analysis Engine with learning mode enabled
        success = await dae.analyze_document(db=db, document_id=document.id, learning_mode=True)
        
        if success:
            crud.document.update(db=db, db_obj=document, obj_in={"status": "completed", "progress": 100})
            logger.info(f"Multi-pass analysis completed successfully for document_id: {document_id}")
        else:
            crud.document.update(db=db, db_obj=document, obj_in={"status": "analysis_failed", "progress": 100})
            logger.warning(f"Multi-pass analysis failed for document_id: {document_id}")
        
    except Exception as e:
        logger.error(f"An error occurred during multi-pass analysis for document {document_id}: {e}")
        crud.document.update(db=db, db_obj=document, obj_in={"status": "analysis_failed", "progress": 100})


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
    document_endpoints.logger.info(f"Fetching segments for document {document_id}")
    
    # First verify the document exists and user has access
    document = crud.document.get(db=db, id=document_id)
    if not document:
        document_endpoints.logger.warning(f"Document {document_id} not found")
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        document_endpoints.logger.warning(f"User {current_user.id} attempted to access segments for document {document_id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to access this document")
    
    # Get only segments that have analysis results (to avoid showing segments without data)
    segments = crud.document_segment.get_multi_by_document(db=db, document_id=document_id, limit=50)
    
    # Filter segments to only include those with analysis results
    segments_with_analysis = []
    for segment in segments:
        analysis_result = crud.analysis_result.get_by_segment(db=db, segment_id=segment.id)
        if analysis_result and analysis_result.structured_data:
            segments_with_analysis.append(segment)
    
    # Sort by ID ascending for consistent ordering
    segments_with_analysis.sort(key=lambda x: x.id)
    
    document_endpoints.logger.info(f"Retrieved {len(segments_with_analysis)} segments with analysis results for document {document_id} (filtered from {len(segments)} total)")
    return segments_with_analysis


@router.get("/{document_id}/analysis")
def get_document_analysis(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get complete document analysis in a single request.
    Returns document info, composition, and all segments with their analysis results.
    This eliminates N+1 queries and 404 errors.
    """
    document_endpoints.logger.info(f"Fetching complete analysis for document {document_id}")
    
    # Verify document exists and user has access
    document = crud.document.get(db=db, id=document_id)
    if not document:
        document_endpoints.logger.warning(f"Document {document_id} not found")
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        document_endpoints.logger.warning(f"User {current_user.id} attempted to access analysis for document {document_id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to access this document")
    
    # Get all segments for this document
    segments = crud.document_segment.get_multi_by_document(db=db, document_id=document_id, limit=50)
    
    # Build segments with analysis results
    segments_with_analysis = []
    analysis_stats = {"analyzed": 0, "failed": 0, "total": len(segments)}
    
    for segment in segments:
        analysis_result = crud.analysis_result.get_by_segment(db=db, segment_id=segment.id)
        
        if analysis_result and analysis_result.structured_data:
            # Segment has successful analysis
            segments_with_analysis.append({
                "segment": schemas.DocumentSegment.model_validate(segment).model_dump(),
                "analysis_result": schemas.AnalysisResult.model_validate(analysis_result).model_dump(),
                "status": "analyzed"
            })
            analysis_stats["analyzed"] += 1
        else:
            # Segment failed or has no analysis - don't include in results but count it
            analysis_stats["failed"] += 1
    
    # Sort by segment ID for consistent ordering
    segments_with_analysis.sort(key=lambda x: x["segment"]["id"])
    
    result = {
        "document": schemas.Document.model_validate(document).model_dump(),
        "composition": document.composition_analysis,
        "segments": segments_with_analysis,
        "stats": analysis_stats
    }
    
    document_endpoints.logger.info(f"Retrieved complete analysis for document {document_id}: {analysis_stats['analyzed']} analyzed, {analysis_stats['failed']} failed, {analysis_stats['total']} total")
    return result


# --- STATUS ENDPOINT ---
@router.get("/{document_id}/status", response_model=schemas.DocumentStatus)
def get_document_status(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Gets the current parsing status and progress for a document."""
    document = crud.document.get(db=db, id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this document")
    
    return {"status": document.status or "unknown", "progress": document.progress or 0}


@router.post("/upload", response_model=schemas.Document)
async def upload_document(
    background_tasks: BackgroundTasks,
    *,
    db: Session = Depends(deps.get_db),
    document_type: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Upload a new document and schedule the full processing pipeline in the background."""
    logger = document_endpoints.logger
    
    try:
        # Validate file type
        if not file.filename:
            raise ValidationException("No filename provided")
        
        file_extension = Path(file.filename).suffix.lower()
        allowed_extensions = ['.pdf', '.docx', '.doc', '.txt']
        
        if file_extension not in allowed_extensions:
            raise ValidationException(f"File type {file_extension} not supported. Allowed types: {', '.join(allowed_extensions)}")
        
        logger.info(f"Starting upload for file: {file.filename}, type: {document_type}, version: {version}")
        
        # Save the file
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

        # Parse the document content FIRST to get raw_text
        parser = MultiModalDocumentParser()
        try:
            logger.debug(f"Starting to parse document: {storage_path}")
            # parse_with_images returns a string directly, not a dict
            raw_text = await parser.parse_with_images(str(storage_path))
            logger.debug(f"Parsed content type: {type(raw_text)}, length: {len(raw_text) if raw_text else 'None'}")
            
            if not raw_text:
                raw_text = "Document content extracted but no text found"
                logger.warning(f"No text extracted, using fallback")
        except Exception as e:
            # Fallback: extract basic text if parsing fails
            error_msg = f"Document content extraction failed: {str(e)}"
            logger.error(f"Parsing failed with error: {error_msg}")
            raw_text = error_msg
        
        # TEMPORARY WORKAROUND: If parsing still fails, use a basic placeholder
        if not raw_text or raw_text is None:
            raw_text = f"Document content placeholder for {file.filename}. Original parsing failed."
            logger.warning(f"Using temporary workaround text")
        
        logger.debug(f"Final raw_text length: {len(raw_text) if raw_text else 'None'}")
        
        # Now create the document with the extracted raw_text
        document_in = schemas.DocumentCreate(
            filename=file.filename, 
            document_type=document_type, 
            version=version,
            raw_text=raw_text,  # Use parsed content
            owner_id=current_user.id,
            storage_path=str(storage_path),  # Include storage_path in schema
            status="uploaded",
            progress=0
        )
        
        logger.debug(f"Document data being created: {document_in}")
        
        document = crud.document.create_with_owner(
            db=db, 
            obj_in=document_in, 
            owner_id=current_user.id,
            storage_path=str(storage_path)  # Pass storage_path separately
        )
        
        # Update with initial size, progress, and status
        crud.document.update(
            db=db, 
            db_obj=document, 
            obj_in={
                "file_size_kb": file_size_kb, 
                "progress": 10, 
                "status": "processing"
            }
        )

        # Add the full processing pipeline to the background
        background_tasks.add_task(
            process_document_pipeline, 
            db=db, 
            document_id=document.id, 
            storage_path=str(storage_path)
        )
        
        logger.info(f"Document {document.id} uploaded successfully and processing scheduled")
        return document
        
    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during document upload: {e}")
        raise DocumentProcessingException(f"Failed to upload document: {str(e)}")