# This is a NEW file at backend/app/tasks.py

import asyncio
from app.worker import celery_app
from app.db.session import SessionLocal
from app import crud
from app.services.document_parser import MultiModalDocumentParser
from app.services.analysis_service import DocumentAnalysisEngine
from app.services.lock_service import lock_service
from app.core.logging import logger

@celery_app.task(name="process_document_pipeline", bind=True)
def process_document_pipeline(self, document_id: int, storage_path: str, tenant_id: int):
    """
    Celery task to orchestrate the full document pipeline.
    This runs in a separate worker process.

    FLAW-10 FIX: Uses distributed locks to prevent race conditions
    when multiple workers try to process the same document.

    SPRINT 2 Phase 4: tenant_id is REQUIRED for multi-tenancy isolation.
    SA REVIEW: Made tenant_id required (was optional), task is bound for context.

    Args:
        document_id: ID of document to process
        storage_path: File path to document
        tenant_id: REQUIRED - Tenant ID for billing and data isolation

    Raises:
        ValueError: If tenant_id is not provided
    """
    # SA REVIEW: Fail-fast validation - tenant_id MUST be provided
    if tenant_id is None:
        logger.error(f"CRITICAL: process_document_pipeline called without tenant_id for document {document_id}")
        raise ValueError("tenant_id is REQUIRED for document processing. This is a security requirement.")

    logger.info(f"CELERY_TASK started for document_id: {document_id}, tenant_id: {tenant_id}")

    # FLAW-10 FIX: Acquire distributed lock to prevent concurrent processing
    # Use context manager for automatic lock release
    with lock_service.lock_document_processing(document_id, timeout=600) as acquired:
        if not acquired:
            # Another worker is already processing this document
            logger.warning(
                f"⏭️ Document {document_id} is already being processed by another worker. Skipping."
            )
            return

        logger.info(f"🔒 Lock acquired for document_id: {document_id}")

        # --- Senior Dev Step: Session Management ---
        # A Celery task MUST manage its own DB session.
        db = SessionLocal()

        # SPRINT 2 Phase 4: Get document with tenant_id for billing
        if tenant_id:
            document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
        else:
            # Backwards compatibility: fetch without tenant filter
            document = crud.document.get(db=db, id=document_id)
            if document:
                tenant_id = document.tenant_id  # Get tenant_id from document

        if not document:
            logger.error(f"Celery task could not find document_id: {document_id}")
            db.close()
            return

        try:
            # We use asyncio.run() to execute our async pipeline
            # from within this synchronous Celery task.
            # SPRINT 2 Phase 4: Pass tenant_id for billing
            asyncio.run(
                _run_async_pipeline(db, document, storage_path, document_id, tenant_id)
            )
        except Exception as e:
            # Top-level safety net
            logger.error(f"A critical unhandled error occurred in the async pipeline: {e}")
            crud.document.update(db=db, db_obj=document, obj_in={
                "status": "analysis_failed",
                "progress": 100,
                "error_message": f"Critical task failure: {str(e)}"
            })
        finally:
            # --- Senior Dev Step: Session Management ---
            # Always close the session in a finally block
            db.close()
            logger.info(f"CELERY_TASK finished for document_id: {document_id}")
            # Lock is automatically released by context manager

async def _run_async_pipeline(db, document, storage_path, document_id, tenant_id=None):
    """
    This is the core async logic that runs inside the Celery task.

    SPRINT 2 Phase 4: tenant_id added for billing cost deduction after analysis.

    Args:
        db: Database session
        document: Document object
        storage_path: Path to document file
        document_id: Document ID
        tenant_id: Tenant ID for billing (optional)
    """
    
    # --- Step 1: Text Extraction ---
    try:
        parser = MultiModalDocumentParser()
        
        # Fix for UX-02: Granular status update
        crud.document.update(db=db, db_obj=document, obj_in={"progress": 25, "status": "parsing"})
        
        content = await parser.parse_with_images(storage_path)
        
        update_data = {
            "raw_text": content,
            "status": "analyzing" if content else "parsing_failed",
            "progress": 50 if content else 100,
            "error_message": None if content else "Parsing failed - no content extracted" # Fix for DAE-01
        }
        document = crud.document.update(db=db, db_obj=document, obj_in=update_data)
        
        if not content:
            logger.warning(f"Parsing failed for document {document_id} - no content extracted")
            return # Stop pipeline
            
    except Exception as e:
        logger.error(f"An error occurred during parsing for document {document_id}: {e}")
        # Fix for DAE-01: Save the actual error message
        crud.document.update(db=db, db_obj=document, obj_in={
            "status": "parsing_failed", 
            "progress": 100, 
            "error_message": str(e)
        })
        return # Stop pipeline

    # --- Step 2: Multi-Pass Analysis ---
    try:
        dae = DocumentAnalysisEngine()
        
        # This DAE service will provide its own granular status updates
        # (e.g., "pass_1_composition") as it runs, fulfilling UX-02.
        success = await dae.analyze_document(db=db, document_id=document.id, tenant_id=tenant_id, learning_mode=True)

        if success:
            crud.document.update(db=db, db_obj=document, obj_in={"status": "completed", "progress": 100, "error_message": None})
            logger.info(f"Multi-pass analysis completed successfully for document_id: {document_id}")

            # SPRINT 2 Phase 4: Deduct cost from tenant after successful analysis
            if tenant_id:
                try:
                    from app.services.billing_enforcement_service import billing_enforcement_service

                    # Refresh document to get latest cost data
                    db.refresh(document)

                    # Use actual cost if available, otherwise use estimate
                    actual_cost = float(document.ai_cost_inr) if document.ai_cost_inr else 0.0

                    if actual_cost > 0:
                        result = billing_enforcement_service.deduct_cost(
                            db=db,
                            tenant_id=tenant_id,
                            cost_inr=actual_cost,
                            description=f"Document analysis: {document.filename}"
                        )

                        logger.info(
                            f"Cost deducted for tenant {tenant_id}: ₹{actual_cost} "
                            f"(billing_type={result['billing_type']}, "
                            f"low_balance_alert={result['low_balance_alert']})"
                        )

                        # Emit low balance warning if needed
                        if result.get('low_balance_alert'):
                            logger.warning(
                                f"⚠️ LOW BALANCE ALERT for tenant {tenant_id}: "
                                f"balance=₹{result.get('new_balance_inr', 'N/A')}"
                            )
                    else:
                        logger.info(f"No cost to deduct for document {document_id} (ai_cost_inr=0)")

                except Exception as billing_error:
                    # Don't fail the entire analysis if billing deduction fails
                    logger.error(f"Failed to deduct billing cost for tenant {tenant_id}: {billing_error}")
                    # Continue - document analysis was successful
            else:
                logger.debug(f"No tenant_id provided for document {document_id}, skipping billing deduction")

        else:
            # If 'success' is false, the DAE service should have already
            # set the error_message in the DB, per DAE-01.
            logger.warning(f"Multi-pass analysis failed for document_id: {document_id}")
        
    except Exception as e:
        logger.error(f"A top-level error occurred during multi-pass analysis for document {document_id}: {e}")
        # Fix for DAE-01: Save the actual error message
        crud.document.update(db=db, db_obj=document, obj_in={
            "status": "analysis_failed", 
            "progress": 100, 
            "error_message": str(e)
        })