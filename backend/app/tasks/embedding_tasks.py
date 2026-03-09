"""
Sprint 4: Embedding Generation Celery Tasks

Background tasks for generating vector embeddings for ontology concepts
and knowledge graph versions. These run after analysis completes.
"""

from app.worker import celery_app
from app.db.session import SessionLocal
from app.core.logging import logger


@celery_app.task(name="generate_concept_embeddings", bind=True, max_retries=1)
def generate_concept_embeddings(self, concept_ids: list, tenant_id: int):
    """
    Generate embeddings for a list of ontology concept IDs.
    Called after concept extraction completes.
    """
    logger.info(f"EMBEDDING_TASK started: {len(concept_ids)} concepts for tenant {tenant_id}")

    db = SessionLocal()
    try:
        from app.services.embedding_service import embedding_service
        stats = embedding_service.embed_concepts_batch(db, tenant_id, concept_ids)
        logger.info(
            f"EMBEDDING_TASK completed: embedded={stats['embedded']}, "
            f"failed={stats['failed']}, skipped={stats['skipped']}"
        )
        return stats
    except Exception as e:
        logger.error(f"EMBEDDING_TASK failed: {e}")
        try:
            self.retry(countdown=60)
        except self.MaxRetriesExceededError:
            pass
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="generate_graph_embedding", bind=True, max_retries=1)
def generate_graph_embedding(self, version_id: int, tenant_id: int):
    """
    Generate embedding for a knowledge graph version.
    Called after graph versioning saves a new snapshot.
    """
    logger.info(f"GRAPH_EMBEDDING_TASK started: version {version_id}, tenant {tenant_id}")

    db = SessionLocal()
    try:
        from app.services.embedding_service import embedding_service
        success = embedding_service.embed_graph_version(db, version_id, tenant_id)
        logger.info(f"GRAPH_EMBEDDING_TASK {'completed' if success else 'failed'} for version {version_id}")
        return {"status": "completed" if success else "failed", "version_id": version_id}
    except Exception as e:
        logger.error(f"GRAPH_EMBEDDING_TASK failed: {e}")
        try:
            self.retry(countdown=60)
        except self.MaxRetriesExceededError:
            pass
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="embed_all_tenant_concepts", bind=True, max_retries=0)
def embed_all_tenant_concepts(self, tenant_id: int):
    """
    Batch job: embed all un-embedded concepts for a tenant.
    Can be triggered manually from admin or on schedule.
    """
    logger.info(f"BATCH_EMBED_TASK started for tenant {tenant_id}")

    db = SessionLocal()
    try:
        from app.services.embedding_service import embedding_service
        stats = embedding_service.embed_all_concepts(db, tenant_id)
        logger.info(f"BATCH_EMBED_TASK completed for tenant {tenant_id}: {stats}")
        return stats
    except Exception as e:
        logger.error(f"BATCH_EMBED_TASK failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()
