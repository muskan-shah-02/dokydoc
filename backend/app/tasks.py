# This is a NEW file at backend/app/tasks.py

import asyncio
from app.worker import celery_app
from app.db.session import SessionLocal
from app import crud
from app.services.document_parser import MultiModalDocumentParser
from app.services.analysis_service import DocumentAnalysisEngine
from app.services.lock_service import lock_service
from app.core.logging import logger

@celery_app.task(name="process_document_pipeline")
def process_document_pipeline(document_id: int, storage_path: str):
    """
    Celery task to orchestrate the full document pipeline.
    This runs in a separate worker process.

    FLAW-10 FIX: Uses distributed locks to prevent race conditions
    when multiple workers try to process the same document.
    """
    logger.info(f"CELERY_TASK started for document_id: {document_id}")

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

        document = crud.document.get(db=db, id=document_id)
        if not document:
            logger.error(f"Celery task could not find document_id: {document_id}")
            db.close()
            return

        try:
            # We use asyncio.run() to execute our async pipeline
            # from within this synchronous Celery task.
            asyncio.run(
                _run_async_pipeline(db, document, storage_path, document_id)
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

async def _run_async_pipeline(db, document, storage_path, document_id):
    """
    This is the core async logic that runs inside the Celery task.
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
        success = await dae.analyze_document(db=db, document_id=document.id, learning_mode=True)
        
        if success:
            crud.document.update(db=db, db_obj=document, obj_in={"status": "completed", "progress": 100, "error_message": None})
            logger.info(f"Multi-pass analysis completed successfully for document_id: {document_id}")
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