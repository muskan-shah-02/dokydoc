"""
SPRINT 3: Ontology Entity Extraction + Mapping Celery Tasks

Architecture (cost-optimized):
1. extract_ontology_entities     — Runs after DOCUMENT analysis (BRD/SRS → document graph)
2. extract_code_ontology_entities — Runs after REPO analysis (code → code graph)
3. run_cross_graph_mapping       — Algorithmic 3-tier mapping (replaces AI reconciliation)

The mapping task uses:
  Tier 1: Exact name match (FREE)
  Tier 2: Fuzzy token overlap + Levenshtein (FREE)
  Tier 3: AI validation for ambiguous pairs only (~$0.001/pair)

This replaces the old reconcile_ontology_sources task which sent ALL concepts
to AI ($2-5 per run). The new approach costs ~$0.05 per run (97% cheaper).
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
    and populate the DOCUMENT GRAPH.

    Fire-and-forget. If it fails, the document remains "completed".
    After extraction, triggers cross-graph mapping for new concepts.
    """
    logger.info(f"ONTOLOGY_TASK started for document_id: {document_id}, tenant_id: {tenant_id}")

    db = SessionLocal()
    try:
        document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
        if not document:
            logger.error(f"Ontology task: Document {document_id} not found")
            return

        if document.status != "completed":
            logger.warning(
                f"Ontology task: Document {document_id} status is '{document.status}', "
                f"expected 'completed'. Skipping."
            )
            return

        result = asyncio.run(
            business_ontology_service.extract_entities_from_analysis(
                db=db, document_id=document_id, tenant_id=tenant_id
            )
        )

        logger.info(
            f"ONTOLOGY_TASK complete for document {document_id}: "
            f"{result.get('entities_created', 0)} entities, "
            f"{result.get('relationships_created', 0)} relationships"
        )

        # Deduct cost and log to usage_log for billing analytics
        cost_inr = result.get("cost_inr", 0)
        if cost_inr > 0 and tenant_id:
            try:
                from app.services.billing_enforcement_service import billing_enforcement_service
                billing_enforcement_service.deduct_cost(
                    db=db, tenant_id=tenant_id, cost_inr=cost_inr,
                    description=f"Ontology extraction: {document.filename}"
                )
            except Exception as billing_error:
                logger.warning(f"Ontology billing deduction failed (non-critical): {billing_error}")

            # Log to usage_log so it appears in billing analytics
            try:
                from app.services.cost_service import cost_service
                crud.usage_log.log_usage(
                    db=db,
                    tenant_id=tenant_id,
                    user_id=None,
                    document_id=document_id,
                    feature_type="document_analysis",
                    operation="ontology_extraction",
                    model_used="gemini-2.5-flash",
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=cost_inr / 84.0,
                    cost_inr=cost_inr,
                )
            except Exception as log_error:
                logger.warning(f"Usage logging failed (non-critical): {log_error}")

        # Trigger cross-graph mapping for newly created concepts
        if result.get("entities_created", 0) > 0:
            try:
                run_cross_graph_mapping.delay(tenant_id)
                logger.info(f"Dispatched cross-graph mapping for tenant {tenant_id}")
            except Exception as map_err:
                logger.warning(f"Failed to dispatch mapping task (non-critical): {map_err}")

    except Exception as e:
        logger.error(f"ONTOLOGY_TASK failed for document {document_id}: {e}")
        try:
            self.retry(countdown=30 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(f"ONTOLOGY_TASK permanently failed for document {document_id}")
    finally:
        db.close()


@celery_app.task(name="extract_code_ontology_entities", bind=True, max_retries=2)
def extract_code_ontology_entities(self, repo_id: int, tenant_id: int):
    """
    Celery task: Extract business entities from a repository's code analysis
    and populate the CODE GRAPH with source_type="code".

    After extraction, triggers cross-graph mapping (algorithmic, not AI).
    """
    logger.info(f"CODE_ONTOLOGY_TASK started for repo_id: {repo_id}, tenant_id: {tenant_id}")

    db = SessionLocal()
    try:
        repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
        if not repo:
            logger.error(f"Code ontology task: Repository {repo_id} not found")
            return

        if repo.analysis_status != "completed":
            logger.warning(
                f"Code ontology task: Repo {repo_id} status is '{repo.analysis_status}', "
                f"expected 'completed'. Skipping."
            )
            return

        result = asyncio.run(
            business_ontology_service.extract_entities_from_code(
                db=db, repo_id=repo_id, tenant_id=tenant_id
            )
        )

        logger.info(
            f"CODE_ONTOLOGY_TASK complete for repo {repo_id}: "
            f"{result.get('entities_created', 0)} entities, "
            f"{result.get('relationships_created', 0)} relationships"
        )

        # Deduct cost and log to usage_log for billing analytics
        cost_inr = result.get("cost_inr", 0)
        if cost_inr > 0 and tenant_id:
            try:
                from app.services.billing_enforcement_service import billing_enforcement_service
                billing_enforcement_service.deduct_cost(
                    db=db, tenant_id=tenant_id, cost_inr=cost_inr,
                    description=f"Code ontology extraction: {repo.name}"
                )
            except Exception as billing_error:
                logger.warning(f"Code ontology billing deduction failed (non-critical): {billing_error}")

            # Log to usage_log so it appears in billing analytics
            try:
                crud.usage_log.log_usage(
                    db=db,
                    tenant_id=tenant_id,
                    user_id=None,
                    feature_type="code_analysis",
                    operation="code_ontology_extraction",
                    model_used="gemini-2.5-flash",
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=cost_inr / 84.0,
                    cost_inr=cost_inr,
                )
            except Exception as log_error:
                logger.warning(f"Usage logging failed (non-critical): {log_error}")

        # Trigger cross-graph mapping (algorithmic — replaces expensive AI reconciliation)
        if result.get("entities_created", 0) > 0:
            try:
                run_cross_graph_mapping.delay(tenant_id)
                logger.info(
                    f"Dispatched algorithmic cross-graph mapping for tenant {tenant_id} "
                    f"(replaces AI reconciliation — 97% cheaper)"
                )
            except Exception as map_err:
                logger.warning(f"Failed to dispatch mapping task (non-critical): {map_err}")

    except Exception as e:
        logger.error(f"CODE_ONTOLOGY_TASK failed for repo {repo_id}: {e}")
        try:
            self.retry(countdown=30 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(f"CODE_ONTOLOGY_TASK permanently failed for repo {repo_id}")
    finally:
        db.close()


@celery_app.task(name="run_cross_graph_mapping", bind=True, max_retries=1)
def run_cross_graph_mapping(self, tenant_id: int):
    """
    Celery task: Run 3-tier algorithmic mapping between document and code graphs.

    REPLACES the old reconcile_ontology_sources task.

    Cost comparison:
      Old (AI reconciliation): $2-5 per run — sends ALL concepts to Gemini
      New (3-tier mapping):    $0.05 per run — AI only for ambiguous pairs
    """
    logger.info(f"CROSS_GRAPH_MAPPING started for tenant {tenant_id}")

    db = SessionLocal()
    try:
        from app.services.mapping_service import mapping_service

        result = mapping_service.run_full_mapping(
            db=db, tenant_id=tenant_id, use_ai_fallback=True
        )

        logger.info(
            f"CROSS_GRAPH_MAPPING complete for tenant {tenant_id}: "
            f"{result['exact_matches']} exact + {result['fuzzy_matches']} fuzzy + "
            f"{result['ai_validated']} AI = {result['total_mappings']} total. "
            f"Gaps: {result['total_gaps']}, Undocumented: {result['total_undocumented']}. "
            f"AI cost: INR {result['ai_cost_inr']:.4f}"
        )

        # Deduct AI cost if any
        ai_cost = result.get("ai_cost_inr", 0)
        if ai_cost > 0:
            try:
                from app.services.billing_enforcement_service import billing_enforcement_service
                billing_enforcement_service.deduct_cost(
                    db=db, tenant_id=tenant_id, cost_inr=ai_cost,
                    description="Cross-graph mapping (AI validation for ambiguous pairs)"
                )
            except Exception as billing_error:
                logger.warning(f"Mapping billing deduction failed: {billing_error}")

    except Exception as e:
        logger.error(f"CROSS_GRAPH_MAPPING failed for tenant {tenant_id}: {e}")
        try:
            self.retry(countdown=60)
        except self.MaxRetriesExceededError:
            logger.error(f"CROSS_GRAPH_MAPPING permanently failed for tenant {tenant_id}")
    finally:
        db.close()
