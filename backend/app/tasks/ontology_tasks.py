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
from app.tasks.utils import run_async


@celery_app.task(name="extract_ontology_entities", bind=True, max_retries=2)
def extract_ontology_entities(self, document_id: int, tenant_id: int):
    """
    Celery task: Build document knowledge graph from structured_data.

    Uses programmatic extraction (NO AI call) — reads the already-analyzed
    structured_data from Pass 1-3 and builds concepts + relationships directly.
    After graph building, triggers cross-graph mapping.
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

        # Programmatic graph building — no AI call, zero cost
        result = business_ontology_service.build_graph_from_document_analysis(
            db=db, document_id=document_id, tenant_id=tenant_id
        )

        logger.info(
            f"ONTOLOGY_TASK complete for document {document_id}: "
            f"{result.get('entities_created', 0)} entities, "
            f"{result.get('relationships_created', 0)} relationships (no AI cost)"
        )

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
    Celery task: Trigger cross-graph mapping after code analysis completes.

    Code knowledge graphs are now built DURING analysis (in code_analysis_service
    _extract_ontology_from_analysis) so this task only needs to trigger the
    algorithmic mapping between document and code graphs. Zero AI cost.
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

        # Graphs are already built during code analysis.
        # Just trigger cross-graph mapping (algorithmic, not AI).
        try:
            run_cross_graph_mapping.delay(tenant_id)
            logger.info(
                f"CODE_ONTOLOGY_TASK: Dispatched cross-graph mapping for tenant {tenant_id} "
                f"(code graphs already built during analysis)"
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

        # Deduct AI cost if any and log to usage_log
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

            # Log to usage_log so it appears in billing analytics
            try:
                crud.usage_log.log_usage(
                    db=db,
                    tenant_id=tenant_id,
                    user_id=None,
                    feature_type="document_analysis",
                    operation="cross_graph_mapping",
                    model_used="gemini-2.5-flash",
                    input_tokens=result.get("ai_input_tokens", 0),
                    output_tokens=result.get("ai_output_tokens", 0),
                    cost_usd=ai_cost / 84.0,
                    cost_inr=ai_cost,
                )
            except Exception as log_error:
                logger.warning(f"Mapping usage logging failed: {log_error}")

        # Auto-trigger synonym detection to keep the ontology clean
        if result.get("total_mappings", 0) > 0:
            try:
                detect_synonyms_task.delay(tenant_id)
                logger.info(f"Dispatched auto synonym detection for tenant {tenant_id}")
            except Exception as syn_err:
                logger.warning(f"Failed to dispatch synonym detection (non-critical): {syn_err}")

    except Exception as e:
        logger.error(f"CROSS_GRAPH_MAPPING failed for tenant {tenant_id}: {e}")
        try:
            self.retry(countdown=60)
        except self.MaxRetriesExceededError:
            logger.error(f"CROSS_GRAPH_MAPPING permanently failed for tenant {tenant_id}")
    finally:
        db.close()


@celery_app.task(name="detect_synonyms_task", bind=True, max_retries=1)
def detect_synonyms_task(self, tenant_id: int):
    """
    Celery task: Run synonym detection to clean up the ontology graph.

    Auto-triggered after cross-graph mapping completes, or manually via API.
    Uses a 1-hour cooldown per tenant to avoid redundant runs.
    """
    logger.info(f"SYNONYM_DETECTION started for tenant {tenant_id}")

    db = SessionLocal()
    try:
        # Time-guard: skip if ran for this tenant within the last hour
        try:
            from app.services.cache_service import cache_service
            cooldown_key = f"synonym_detection_cooldown:{tenant_id}"
            if cache_service.get_cached_analysis(content=cooldown_key, analysis_type="cooldown"):
                logger.info(f"SYNONYM_DETECTION skipped for tenant {tenant_id} (ran within last hour)")
                return {"status": "skipped", "reason": "cooldown"}
            # Set cooldown for 1 hour
            cache_service.set_cached_analysis(
                content=cooldown_key, analysis_type="cooldown",
                result={"ran": True}, ttl_seconds=3600
            )
        except Exception as cache_err:
            logger.warning(f"Synonym cooldown check failed (proceeding): {cache_err}")

        result = run_async(
            business_ontology_service.detect_synonyms(db=db, tenant_id=tenant_id)
        )

        logger.info(
            f"SYNONYM_DETECTION complete for tenant {tenant_id}: "
            f"{result.get('synonyms_found', 0)} synonyms found"
        )

        # Deduct cost if any
        cost_inr = result.get("cost_inr", 0)
        if cost_inr > 0:
            try:
                from app.services.billing_enforcement_service import billing_enforcement_service
                billing_enforcement_service.deduct_cost(
                    db=db, tenant_id=tenant_id, cost_inr=cost_inr,
                    description="Automatic synonym detection"
                )
            except Exception as billing_err:
                logger.warning(f"Synonym billing deduction failed (non-critical): {billing_err}")

            try:
                crud.usage_log.log_usage(
                    db=db,
                    tenant_id=tenant_id,
                    user_id=None,
                    feature_type="document_analysis",
                    operation="synonym_detection",
                    model_used="gemini-2.5-flash",
                    input_tokens=result.get("input_tokens", 0),
                    output_tokens=result.get("output_tokens", 0),
                    cost_usd=cost_inr / 84.0,
                    cost_inr=cost_inr,
                )
            except Exception as log_error:
                logger.warning(f"Synonym usage logging failed (non-critical): {log_error}")

        return {"status": "completed", "synonyms_found": result.get("synonyms_found", 0)}

    except Exception as e:
        logger.error(f"SYNONYM_DETECTION failed for tenant {tenant_id}: {e}")
        try:
            self.retry(countdown=60)
        except self.MaxRetriesExceededError:
            logger.error(f"SYNONYM_DETECTION permanently failed for tenant {tenant_id}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()
