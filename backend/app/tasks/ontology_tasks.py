"""
SPRINT 3: Ontology Entity Extraction Celery Task

Runs ASYNCHRONOUSLY after document analysis completes.
Does NOT block the user — document is already marked "completed" before this fires.

The frontend can poll /ontology/document/{id}/status to show a subtle
"X entities extracted" badge when this task finishes.
"""

import asyncio
from app.worker import celery_app
from app.db.session import SessionLocal
from app import crud
from app.services.business_ontology_service import business_ontology_service
from app.core.logging import logger


@celery_app.task(name="extract_ontology_entities", bind=True, max_retries=2)
def extract_ontology_entities(self, document_id: int, tenant_id: int):
    """
    Celery task: Extract business entities from a completed document's analysis
    and populate the ontology graph.

    This is a fire-and-forget task triggered after the document pipeline completes.
    If it fails, the document remains "completed" — ontology enrichment is best-effort.
    """
    logger.info(f"🧠 ONTOLOGY_TASK started for document_id: {document_id}, tenant_id: {tenant_id}")

    db = SessionLocal()
    try:
        # Verify document exists and is completed
        document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
        if not document:
            logger.error(f"Ontology task: Document {document_id} not found")
            return

        if document.status != "completed":
            logger.warning(
                f"Ontology task: Document {document_id} status is '{document.status}', "
                f"expected 'completed'. Skipping entity extraction."
            )
            return

        # Run the async entity extraction
        result = asyncio.run(
            business_ontology_service.extract_entities_from_analysis(
                db=db, document_id=document_id, tenant_id=tenant_id
            )
        )

        logger.info(
            f"🧠 ONTOLOGY_TASK complete for document {document_id}: "
            f"{result.get('entities_created', 0)} entities, "
            f"{result.get('relationships_created', 0)} relationships"
        )

        # Deduct ontology extraction cost from billing if applicable
        cost_inr = result.get("cost_inr", 0)
        if cost_inr > 0 and tenant_id:
            try:
                from app.services.billing_enforcement_service import billing_enforcement_service
                billing_enforcement_service.deduct_cost(
                    db=db,
                    tenant_id=tenant_id,
                    cost_inr=cost_inr,
                    description=f"Ontology extraction: {document.filename}"
                )
            except Exception as billing_error:
                logger.warning(f"Ontology billing deduction failed (non-critical): {billing_error}")

    except Exception as e:
        logger.error(f"🧠 ONTOLOGY_TASK failed for document {document_id}: {e}")
        # Retry with exponential backoff (30s, 60s)
        try:
            self.retry(countdown=30 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(f"🧠 ONTOLOGY_TASK permanently failed for document {document_id} after retries")
    finally:
        db.close()
