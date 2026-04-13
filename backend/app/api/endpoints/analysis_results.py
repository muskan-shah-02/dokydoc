# This is the final, updated content for your file at:
# backend/app/api/endpoints/analysis_results.py

from typing import List, Any, Optional
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
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
async def perform_multi_pass_analysis(db: Session, document_id: int, triggered_by_user_id: int, tenant_id: int):
    """
    This function runs in the background and performs the complete multi-pass analysis
    using the Document Analysis Engine (DAE).

    SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Starting multi-pass analysis for document_id: {document_id} (tenant_id={tenant_id})")

    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document or not document.raw_text:
        logger.warning(f"Document {document_id} has no raw_text to analyze (tenant_id={tenant_id})")
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
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all existing analysis results for a specific document.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when document not in tenant to avoid leaking existence.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Fetching analysis results for document {document_id} (tenant_id={tenant_id})")

    # Verify document exists in tenant
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        logger.warning(f"Document {document_id} not found in tenant {tenant_id}")
        raise HTTPException(status_code=404, detail="Document not found")

    results = crud.analysis_result.get_multi_by_document(db=db, document_id=document_id, tenant_id=tenant_id)
    logger.info(f"Retrieved {len(results)} analysis results for document {document_id} (tenant_id={tenant_id})")
    return results


@router.get("/segment/{segment_id}", response_model=schemas.AnalysisResult)
def get_analysis_result_for_segment(
    segment_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve analysis result for a specific document segment.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when segment/document not in tenant to avoid leaking existence.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Fetching analysis result for segment {segment_id} (tenant_id={tenant_id})")

    # Get the segment and verify it's in tenant
    segment = crud.document_segment.get(db=db, id=segment_id, tenant_id=tenant_id)
    if not segment:
        logger.warning(f"Segment {segment_id} not found in tenant {tenant_id}")
        raise HTTPException(status_code=404, detail="Segment not found")

    # Verify parent document is in tenant
    document = crud.document.get(db=db, id=segment.document_id, tenant_id=tenant_id)
    if not document:
        logger.warning(f"Document {segment.document_id} for segment {segment_id} not found in tenant {tenant_id}")
        raise HTTPException(status_code=404, detail="Document not found")

    # Get the analysis result for this segment
    analysis_result = crud.analysis_result.get_by_segment(db=db, segment_id=segment_id, tenant_id=tenant_id)
    if not analysis_result:
        logger.warning(f"Analysis result not found for segment {segment_id} (tenant_id={tenant_id})")
        raise HTTPException(status_code=404, detail="Analysis result not found for this segment")

    logger.info(f"Retrieved analysis result for segment {segment_id} (tenant_id={tenant_id})")
    return analysis_result


@router.post("/document/{document_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_new_analysis(
    document_id: int,
    background_tasks: BackgroundTasks,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Trigger a new multi-pass analysis on a document using the Document Analysis Engine (DAE).
    This endpoint responds instantly and schedules the analysis to run in the background.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when document not in tenant to avoid leaking existence.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Triggering new analysis for document {document_id} (tenant_id={tenant_id})")

    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        logger.warning(f"Document {document_id} not found in tenant {tenant_id}")
        raise HTTPException(status_code=404, detail="Document not found")

    # Add the multi-pass analysis to the background
    background_tasks.add_task(
        perform_multi_pass_analysis,
        db=db,
        document_id=document_id,
        triggered_by_user_id=current_user.id,
        tenant_id=tenant_id  # SPRINT 2: Pass tenant context to background task
    )

    logger.info(f"Multi-pass analysis scheduled for document {document_id} (tenant_id={tenant_id})")
    return {"message": "Multi-pass analysis has been scheduled to run in the background."}


@router.get("/document/{document_id}/consolidated")
def get_saved_consolidated_analysis(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Return previously saved consolidated analysis if present.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when document not in tenant to avoid leaking existence.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Fetching saved consolidated analysis for document {document_id} (tenant_id={tenant_id})")

    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    saved = crud.consolidated_analysis.get_by_document(db=db, document_id=document_id, tenant_id=tenant_id)
    if not saved:
        raise HTTPException(status_code=404, detail="No consolidated analysis found")
    return saved.data


@router.post("/document/{document_id}/consolidate")
async def consolidate_analysis(
    document_id: int,
    payload: dict,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Generate a consolidated analysis by synthesizing all segment analysis results.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when document not in tenant to avoid leaking existence.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Generating consolidated analysis for document {document_id} (tenant_id={tenant_id})")

    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        logger.warning(f"Document {document_id} not found in tenant {tenant_id}")
        raise HTTPException(status_code=404, detail="Document not found")

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
            logger.info(f"Successfully generated consolidated analysis for document {document_id} (tenant_id={tenant_id})")
            # Optionally persist if requested
            if payload.get("save", True):
                crud.consolidated_analysis.upsert(db=db, document_id=document_id, data=consolidated_analysis, tenant_id=tenant_id)
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
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get all analysis runs for a document with their status and progress.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when document not in tenant to avoid leaking existence.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Fetching analysis runs for document {document_id} (tenant_id={tenant_id})")

    # Verify document exists in tenant
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
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
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get the currently active analysis run for a document, if any.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when document not in tenant to avoid leaking existence.
    """
    logger = analysis_endpoints.logger
    logger.info(f"Fetching active analysis run for document {document_id} (tenant_id={tenant_id})")

    # Verify document exists in tenant
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
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


# ─────────────────────────────────────────────────────────────────────────────
# P4-08: Unified Analysis Orchestrator
# POST /api/v1/analysis/run-full
#
# Single endpoint that:
#   1. Triggers document re-analysis (if needed / forced)
#   2. Triggers code component re-analysis (if needed / forced)
#   3. Enqueues validation scan after both complete
#
# This replaces the previous requirement of calling 3 separate endpoints
# in the correct order from the frontend.
# ─────────────────────────────────────────────────────────────────────────────

class FullAnalysisRequest(BaseModel):
    document_id: int
    repository_id: Optional[int] = None
    force_reanalyze: bool = False


class FullAnalysisResponse(BaseModel):
    status: str
    message: str
    document_id: int
    repository_id: Optional[int]
    validation_queued: bool


@router.post(
    "/run-full",
    response_model=FullAnalysisResponse,
    summary="P4-08: Unified Analysis Orchestrator",
    description=(
        "Triggers document analysis + code analysis + validation scan "
        "in the correct order. Idempotent — skips steps already completed "
        "unless force_reanalyze=true."
    ),
)
async def run_full_analysis(
    request: FullAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """
    P4-08: Unified orchestrator — one call to analyse both sides and validate.

    Flow:
      1. Validate document exists + belongs to tenant
      2. Check if document needs (re)analysis — trigger if so
      3. Check if repository needs (re)analysis — trigger if so
      4. Enqueue validation scan (non-blocking, runs in background)
    """
    # Step 1: Verify document ownership
    document = crud.document.get(
        db=db, id=request.document_id, tenant_id=tenant_id
    )
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document {request.document_id} not found",
        )

    validation_queued = False
    messages = []

    # Step 2: Trigger document re-analysis if needed
    doc_needs_analysis = (
        request.force_reanalyze
        or document.status in ("pending", "parsing_failed", "analysis_failed")
        or not getattr(document, "raw_text", None)
    )
    if doc_needs_analysis:
        try:
            background_tasks.add_task(
                perform_multi_pass_analysis,
                db=db,
                document_id=request.document_id,
                triggered_by_user_id=current_user.id,
                tenant_id=tenant_id,
            )
            messages.append(f"Document analysis queued for doc {request.document_id}")
        except Exception as e:
            messages.append(f"Document analysis queue failed: {e}")
    else:
        messages.append("Document analysis skipped (already completed)")

    # Step 3: Re-analyse failed code components for repository if provided
    # (Full repo re-analysis requires file_list from the upload flow;
    #  here we only retry components that are in 'failed' or 'pending' state)
    if request.repository_id:
        try:
            from app.tasks.code_analysis_tasks import batch_retry_failed_components
            # Fetch IDs of failed/pending components for this repo
            failed_components = (
                db.query(models.CodeComponent.id)
                .filter(
                    models.CodeComponent.repository_id == request.repository_id,
                    models.CodeComponent.tenant_id == tenant_id,
                    models.CodeComponent.analysis_status.in_(
                        ["failed", "pending"] if not request.force_reanalyze
                        else ["failed", "pending", "completed"]
                    ),
                )
                .all()
            )
            component_ids = [row[0] for row in failed_components]
            if component_ids:
                batch_retry_failed_components.delay(
                    repo_id=request.repository_id,
                    tenant_id=tenant_id,
                    component_ids=component_ids,
                )
                messages.append(
                    f"Re-analysis queued for {len(component_ids)} code components"
                )
            else:
                messages.append("No failed components found — code analysis skipped")
        except Exception as e:
            messages.append(f"Code component retry failed: {e}")

    # Step 4: Enqueue validation scan as background task (idempotent per link)
    try:
        from app.services.validation_service import validation_service as _vs
        background_tasks.add_task(
            _vs.run_validation_scan,
            user_id=current_user.id,
            document_ids=[request.document_id],
            tenant_id=tenant_id,
        )
        validation_queued = True
        messages.append("Validation scan queued")
    except Exception as e:
        messages.append(f"Validation scan queue failed: {e}")

    return FullAnalysisResponse(
        status="queued",
        message=" | ".join(messages),
        document_id=request.document_id,
        repository_id=request.repository_id,
        validation_queued=validation_queued,
    )


# ─────────────────────────────────────────────────────────────────────────────
# P4-09: BOE Savings Analytics
# GET /api/v1/analysis/boe-savings-summary
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/boe-savings-summary",
    summary="P4-09: BOE Cost Savings Summary",
    description=(
        "Returns a summary of how many Gemini calls the BOE has avoided "
        "through high-confidence auto-approvals."
    ),
)
def get_boe_savings_summary(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """
    P4-09: BOE Savings Analytics.

    Computes:
      - How many confirmed mappings exist for this tenant
      - How many are above the auto-approve threshold (high confidence)
      - Coverage % and estimated INR saved this month
    """
    from app.services.boe_context import BOEContext

    AUTO_APPROVE_THRESHOLD = BOEContext.AUTO_APPROVE_THRESHOLD

    try:
        from app.models.concept_mapping import ConceptMapping

        total_confirmed = (
            db.query(ConceptMapping)
            .filter(
                ConceptMapping.tenant_id == tenant_id,
                ConceptMapping.status == "confirmed",
            )
            .count()
        )

        high_conf_count = (
            db.query(ConceptMapping)
            .filter(
                ConceptMapping.tenant_id == tenant_id,
                ConceptMapping.status == "confirmed",
                ConceptMapping.confidence_score >= AUTO_APPROVE_THRESHOLD,
            )
            .count()
        )

        coverage_pct = (
            round(high_conf_count / total_confirmed * 100, 1)
            if total_confirmed > 0
            else 0.0
        )

        # Estimate: each skipped Gemini call saves ~₹0.03 on average
        # Assume 10 validation runs per month per mapping in a typical sprint
        COST_PER_GEMINI_CALL_INR = 0.03
        RUNS_PER_MONTH_ESTIMATE = 10
        estimated_calls_saved = high_conf_count * RUNS_PER_MONTH_ESTIMATE
        estimated_inr_saved = round(
            estimated_calls_saved * COST_PER_GEMINI_CALL_INR, 2
        )

        return {
            "confirmed_mapping_count": total_confirmed,
            "auto_approved_count": high_conf_count,
            "coverage_pct": coverage_pct,
            "auto_approve_threshold": AUTO_APPROVE_THRESHOLD,
            "estimated_calls_saved_this_month": estimated_calls_saved,
            "estimated_inr_saved": estimated_inr_saved,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute BOE savings summary: {str(e)}",
        )

