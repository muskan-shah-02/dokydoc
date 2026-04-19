"""
P5C-05: Celery task for async test suite generation.
Stores result in Redis with 1-hour TTL.
"""
from app.worker import celery_app
from app.core.logging import get_logger

logger = get_logger("test_generation_tasks")


@celery_app.task(name="generate_test_suite", bind=True, max_retries=2)
def generate_test_suite(self, document_id: int, tenant_id: int, doc_title: str):
    """
    Celery task: generate test suite zip and store result in Redis.
    Result stored under key: test_suite:{document_id}:{tenant_id}
    TTL: 1 hour (3600 seconds)
    """
    from app.db.session import SessionLocal
    from app.services.test_suite_service import test_suite_service

    db = SessionLocal()
    try:
        zip_bytes = test_suite_service.generate_zip_sync(
            db=db,
            document_id=document_id,
            tenant_id=tenant_id,
            doc_title=doc_title,
        )
        # Store in Redis with 1-hour TTL
        try:
            from app.core.redis import get_redis_client
            redis = get_redis_client()
            redis_key = f"test_suite:{document_id}:{tenant_id}"
            redis.set(redis_key, zip_bytes, ex=3600)
            logger.info(f"[P5C-05] Test suite stored for doc {document_id}, {len(zip_bytes)} bytes")
        except Exception as redis_err:
            logger.warning(f"[P5C-05] Redis store failed: {redis_err}")
    except Exception as exc:
        logger.error(f"[P5C-05] Test suite generation failed for doc {document_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
