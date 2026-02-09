"""
SPRINT 3: Ontology Entity Extraction Celery Tasks

Dual-source architecture:
1. extract_ontology_entities — Runs after DOCUMENT analysis (BRD/SRS → ontology)
2. extract_code_ontology_entities — Runs after REPO analysis (code → ontology)

Both are fire-and-forget. If a concept already exists from the other source,
it gets promoted to source_type="both" (cross-referenced).

The frontend can poll /ontology/document/{id}/status to show a subtle
"X entities extracted" badge when these tasks finish.
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


@celery_app.task(name="extract_code_ontology_entities", bind=True, max_retries=2)
def extract_code_ontology_entities(self, repo_id: int, tenant_id: int):
    """
    Celery task: Extract business entities from a repository's code analysis
    and populate the ontology graph with source_type="code".

    Fires AFTER repo_analysis_task completes. If a concept already exists from
    document analysis, the CRUD layer promotes it to source_type="both" —
    marking it as cross-validated by both BRD and code.

    This is fire-and-forget. Repo stays "completed" regardless of outcome.
    """
    logger.info(f"🔧 CODE_ONTOLOGY_TASK started for repo_id: {repo_id}, tenant_id: {tenant_id}")

    db = SessionLocal()
    try:
        # Verify repository exists and is completed
        repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
        if not repo:
            logger.error(f"Code ontology task: Repository {repo_id} not found")
            return

        if repo.analysis_status != "completed":
            logger.warning(
                f"Code ontology task: Repo {repo_id} status is '{repo.analysis_status}', "
                f"expected 'completed'. Skipping code entity extraction."
            )
            return

        # Run the async code entity extraction
        result = asyncio.run(
            business_ontology_service.extract_entities_from_code(
                db=db, repo_id=repo_id, tenant_id=tenant_id
            )
        )

        logger.info(
            f"🔧 CODE_ONTOLOGY_TASK complete for repo {repo_id}: "
            f"{result.get('entities_created', 0)} entities, "
            f"{result.get('relationships_created', 0)} relationships, "
            f"{result.get('cross_referenced', 0)} cross-referenced with documents"
        )

        # Deduct code ontology extraction cost from billing
        cost_inr = result.get("cost_inr", 0)
        if cost_inr > 0 and tenant_id:
            try:
                from app.services.billing_enforcement_service import billing_enforcement_service
                billing_enforcement_service.deduct_cost(
                    db=db,
                    tenant_id=tenant_id,
                    cost_inr=cost_inr,
                    description=f"Code ontology extraction: {repo.name}"
                )
            except Exception as billing_error:
                logger.warning(f"Code ontology billing deduction failed (non-critical): {billing_error}")

        # After code extraction succeeds, trigger reconciliation
        # This creates bridge relationships between document and code layers
        try:
            reconcile_ontology_sources.delay(tenant_id)
            logger.info(f"Dispatched reconciliation task for tenant {tenant_id}")
        except Exception as recon_err:
            logger.warning(f"Failed to dispatch reconciliation (non-critical): {recon_err}")

    except Exception as e:
        logger.error(f"🔧 CODE_ONTOLOGY_TASK failed for repo {repo_id}: {e}")
        try:
            self.retry(countdown=30 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(f"🔧 CODE_ONTOLOGY_TASK permanently failed for repo {repo_id} after retries")
    finally:
        db.close()


@celery_app.task(name="reconcile_ontology_sources", bind=True, max_retries=1)
def reconcile_ontology_sources(self, tenant_id: int):
    """
    Celery task: Reconciliation pass — connects document-layer and code-layer concepts.

    This is the CRITICAL step that makes the dual-source graph useful:
    1. Creates bridge relationships (implements, enforces, extends)
    2. Detects contradictions (document says X, code does Y)
    3. Identifies unimplemented requirements (document concepts with no code)
    4. Identifies undocumented features (code concepts with no document)

    Only promotes concepts to source_type="both" when AI confirms high-confidence
    "implements" match — NOT on naive name matching.

    Fires automatically after code ontology extraction, but can also be triggered
    manually via the API.
    """
    logger.info(f"🔗 RECONCILIATION_TASK started for tenant_id: {tenant_id}")

    db = SessionLocal()
    try:
        result = asyncio.run(
            business_ontology_service.reconcile_document_code_concepts(
                db=db, tenant_id=tenant_id
            )
        )

        bridges = result.get("bridges_created", 0)
        contradictions = result.get("contradictions_found", 0)
        unimplemented = len(result.get("unimplemented_requirements", []))
        undocumented = len(result.get("undocumented_features", []))

        logger.info(
            f"🔗 RECONCILIATION_TASK complete for tenant {tenant_id}: "
            f"{bridges} bridges, {contradictions} contradictions, "
            f"{unimplemented} unimplemented, {undocumented} undocumented"
        )

        # Deduct reconciliation cost
        cost_inr = result.get("cost_inr", 0)
        if cost_inr > 0:
            try:
                from app.services.billing_enforcement_service import billing_enforcement_service
                billing_enforcement_service.deduct_cost(
                    db=db,
                    tenant_id=tenant_id,
                    cost_inr=cost_inr,
                    description="Ontology source reconciliation"
                )
            except Exception as billing_error:
                logger.warning(f"Reconciliation billing deduction failed: {billing_error}")

    except Exception as e:
        logger.error(f"🔗 RECONCILIATION_TASK failed for tenant {tenant_id}: {e}")
        try:
            self.retry(countdown=60)
        except self.MaxRetriesExceededError:
            logger.error(f"🔗 RECONCILIATION_TASK permanently failed for tenant {tenant_id}")
    finally:
        db.close()
