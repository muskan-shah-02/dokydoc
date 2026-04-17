"""
P5C-08: Celery beat tasks for analytics and compliance snapshot generation.
"""
from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger("analytics_tasks")


@celery_app.task(name="nightly_compliance_snapshots")
def nightly_compliance_snapshots():
    """
    Celery beat task: run every night at midnight UTC to snapshot compliance scores
    for all active documents (those with atoms).
    Configured in celery beat schedule in celery_app.py.
    """
    from app.db.session import SessionLocal
    from app.services.compliance_snapshot_service import compliance_snapshot_service

    db = SessionLocal()
    try:
        count = compliance_snapshot_service.capture_all_active_documents(db)
        logger.info(f"[P5C-08] Nightly snapshot completed: {count} documents")
        return {"status": "completed", "documents_snapshotted": count}
    except Exception as e:
        logger.error(f"[P5C-08] Nightly snapshot task failed: {e}")
        raise
    finally:
        db.close()
