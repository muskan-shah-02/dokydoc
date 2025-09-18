# This is the final, updated content for your file at:
# backend/app/api/endpoints/analysis_results.py

from typing import List, Any
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.services.analysis_service import DocumentAnalysisEngine
from app.services.analysis_run_service import AnalysisRunService
from app.core.logging import LoggerMixin
from app.core.exceptions import DocumentProcessingException, NotFoundException

class AnalysisEndpoints(LoggerMixin):
    """Analysis endpoints with enhanced logging and error handling."""
    
    def __init__(self):
        super().__init__()

# Create instance for use in endpoints
analysis_endpoints = AnalysisEndpoints()

router = APIRouter()

# --- This is our new multi-pass analysis background task ---
async def perform_multi_pass_analysis(db: Session, document_id: int, triggered_by_user_id: int):
    """
    This function runs in the background and performs the complete multi-pass analysis
    using the Document Analysis Engine (DAE).
    """
    logger = analysis_endpoints.logger
    logger.info(f"Starting multi-pass analysis for document_id: {document_id}")
    
    document = crud.document.get(db=db, id=document_id)
    if not document or not document.raw_text:
        logger.warning(f"Document {document_id} has no raw_text to analyze.")
        return

    # Initialize services
    run_service = AnalysisRunService()
    dae = DocumentAnalysisEngine()
    
    # Start a new analysis run
    analysis_run = run_service.create_analysis_run(
        db=db, 
        document_id=document_id, 
        user_id=triggered_by_user_id,
        learning_mode=True
    )
    
    try:
        # Use the new Document Analysis Engine with learning mode enabled
        success = await dae.analyze_document(db=db, document_id=document_id, learning_mode=True, analysis_run_id=analysis_run.id)
        
        if success:
            run_service.complete_run(db=db, run_id=analysis_run.id, success=True)
            logger.info(f"Multi-pass analysis completed successfully for document {document_id}")
        else:
            run_service.fail_run(db=db, run_id=analysis_run.id, error_message="Analysis failed")
            logger.warning(f"Multi-pass analysis failed for document {document_id}")

    except DocumentProcessingException as e:
        run_service.fail_run(db=db, run_id=analysis_run.id, error_message=str(e))
        if "already_running" in str(e.details):
            logger.warning(f"Analysis already running for document {document_id}, skipping duplicate request")
        else:
            logger.error(f"Document processing error for document {document_id}: {e}")
    except Exception as e:
        run_service.fail_run(db=db, run_id=analysis_run.id, error_message=str(e))
        logger.error(f"An error occurred during multi-pass analysis for document {document_id}: {e}")


@router.get("/document/{document_id}", response_model=List[schemas.AnalysisResult])
def get_analysis_results_for_document(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all existing analysis results for a specific document.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Fetching analysis results for document {document_id}")
    
    # Verify user owns the document
    document = crud.document.get(db=db, id=document_id)
    if not document:
        logger.warning(f"Document {document_id} not found")
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to access analysis results for document {document_id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to access this document")

    results = crud.analysis_result.get_multi_by_document(db=db, document_id=document_id)
    logger.info(f"Retrieved {len(results)} analysis results for document {document_id}")
    return results


@router.get("/segment/{segment_id}", response_model=schemas.AnalysisResult)
def get_analysis_result_for_segment(
    segment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve analysis result for a specific document segment.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Fetching analysis result for segment {segment_id}")
    
    # Get the segment and verify user has access to the parent document
    segment = crud.document_segment.get(db=db, id=segment_id)
    if not segment:
        logger.warning(f"Segment {segment_id} not found")
        raise HTTPException(status_code=404, detail="Segment not found")
    
    document = crud.document.get(db=db, id=segment.document_id)
    if not document:
        logger.warning(f"Document {segment.document_id} for segment {segment_id} not found")
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to access analysis result for segment {segment_id} in document {document.id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to access this document")

    # Get the analysis result for this segment
    analysis_result = crud.analysis_result.get_by_segment(db=db, segment_id=segment_id)
    if not analysis_result:
        logger.warning(f"Analysis result not found for segment {segment_id}")
        raise HTTPException(status_code=404, detail="Analysis result not found for this segment")
    
    logger.info(f"Retrieved analysis result for segment {segment_id}")
    return analysis_result


@router.post("/document/{document_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_new_analysis(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Trigger a new multi-pass analysis on a document using the Document Analysis Engine (DAE).
    This endpoint responds instantly and schedules the analysis to run in the background.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Triggering new analysis for document {document_id}")
    
    document = crud.document.get(db=db, id=document_id)
    if not document:
        logger.warning(f"Document {document_id} not found")
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to trigger analysis for document {document_id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to analyze this document")

    # Add the multi-pass analysis to the background
    background_tasks.add_task(
        perform_multi_pass_analysis,
        db=db,
        document_id=document_id,
        triggered_by_user_id=current_user.id
    )

    logger.info(f"Multi-pass analysis scheduled for document {document_id}")
    return {"message": "Multi-pass analysis has been scheduled to run in the background."}


@router.get("/document/{document_id}/consolidated")
def get_saved_consolidated_analysis(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Return previously saved consolidated analysis if present.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Fetching saved consolidated analysis for document {document_id}")

    document = crud.document.get(db=db, id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    saved = crud.consolidated_analysis.get_by_document(db=db, document_id=document_id)
    if not saved:
        raise HTTPException(status_code=404, detail="No consolidated analysis found")
    return saved.data


@router.post("/document/{document_id}/consolidate")
async def consolidate_analysis(
    document_id: int,
    payload: dict,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Generate a consolidated analysis by synthesizing all segment analysis results.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Generating consolidated analysis for document {document_id}")
    
    document = crud.document.get(db=db, id=document_id)
    if not document:
        logger.warning(f"Document {document_id} not found")
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to consolidate analysis for document {document_id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to access this document")

    try:
        # Import the gemini service for consolidation
        from app.services.ai.gemini import gemini_service
        
        # Prepare the consolidation prompt
        consolidation_prompt = f"""
        You are an expert document analyst. Please consolidate the following segment analysis results into a unified, comprehensive analysis.

        SEGMENT ANALYSIS DATA:
        {json.dumps(payload.get('analysis_data', []), indent=2)}

        Please provide a consolidated analysis that:
        1. Synthesizes information from all segments
        2. Identifies key themes and patterns
        3. Provides a unified view of the document's content
        4. Maintains the structured format but combines related information
        5. Highlights important insights and relationships

        Return the result as a JSON object with clear, organized sections.
        """

        # Call Gemini API for consolidation
        response = await gemini_service.generate_content(consolidation_prompt)
        response_text = response.text
        
        # Clean the response - remove markdown code block formatting
        cleaned_response = response_text.strip()
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
        elif cleaned_response.startswith('```'):
            cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
        
        # Parse the JSON response
        try:
            consolidated_analysis = json.loads(cleaned_response)
            logger.info(f"Successfully generated consolidated analysis for document {document_id}")
            # Optionally persist if requested
            if payload.get("save", True):
                crud.consolidated_analysis.upsert(db=db, document_id=document_id, data=consolidated_analysis)
            return consolidated_analysis
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse consolidated analysis response: {e}")
            logger.error(f"Raw response: {response_text}")
            raise HTTPException(status_code=500, detail="Failed to parse consolidated analysis response")
            
    except Exception as e:
        logger.error(f"Error generating consolidated analysis for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate consolidated analysis")


@router.get("/document/{document_id}/runs")
def get_analysis_runs(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get all analysis runs for a document with their status and progress.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Fetching analysis runs for document {document_id}")
    
    # Verify document ownership
    document = crud.document.get(db=db, id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this document's analysis runs")
    
    # Get analysis runs for this document
    run_service = AnalysisRunService()
    runs = run_service.get_runs_for_document(db=db, document_id=document_id)
    
    return {
        "document_id": document_id,
        "total_runs": len(runs),
        "runs": [
            {
                "id": run.id,
                "status": run.status,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "total_segments": run.total_segments,
                "completed_segments": run.completed_segments,
                "failed_segments": run.failed_segments,
                "error_message": run.error_message,
                "learning_mode": run.learning_mode
            }
            for run in runs
        ]
    }


@router.get("/document/{document_id}/runs/active")
def get_active_analysis_run(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get the currently active analysis run for a document, if any.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Fetching active analysis run for document {document_id}")
    
    # Verify document ownership
    document = crud.document.get(db=db, id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this document's analysis runs")
    
    # Get active run for this document
    run_service = AnalysisRunService()
    active_run = run_service.get_active_run(db=db, document_id=document_id)
    
    if not active_run:
        return {"active_run": None}
    
    # Be defensive: coalesce possible None values to avoid 500s
    total_segments = active_run.total_segments or 0
    completed_segments = active_run.completed_segments or 0
    failed_segments = active_run.failed_segments or 0
    progress_percentage = (completed_segments / total_segments * 100) if total_segments > 0 else 0

    return {
        "active_run": {
            "id": active_run.id,
            "status": active_run.status,
            "started_at": active_run.started_at,
            "total_segments": total_segments,
            "completed_segments": completed_segments,
            "failed_segments": failed_segments,
            "progress_percentage": progress_percentage,
            "learning_mode": active_run.learning_mode,
        }
    }
