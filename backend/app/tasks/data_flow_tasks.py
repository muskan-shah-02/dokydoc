"""
Phase 3 — P3.6: Celery tasks for data-flow edge backfill and rebuild.

Two tasks:
  * backfill_data_flow_edges(repository_id, tenant_id)
      Rebuild edges for every CodeComponent in a repository whose analysis
      is already complete. Safe to run repeatedly — idempotent per component.

  * rebuild_component_data_flow(component_id, tenant_id)
      One-off rebuild for a single component (invoked after re-analysis).
"""
from typing import Any
from app.worker import celery_app
from app.core.logging import get_logger

logger = get_logger("data_flow_tasks")


@celery_app.task(name="backfill_data_flow_edges", bind=True, max_retries=2)
def backfill_data_flow_edges(
    self,
    repository_id: int,
    tenant_id: int,
) -> dict[str, Any]:
    """Rebuild flow edges for every analyzed CodeComponent in a repo."""
    from app.db.session import SessionLocal
    from app.models.code_component import CodeComponent
    from app.services.data_flow_service import data_flow_service

    db = SessionLocal()
    processed = 0
    edges_written = 0
    failed = 0

    try:
        components = (
            db.query(CodeComponent)
            .filter(
                CodeComponent.repository_id == repository_id,
                CodeComponent.tenant_id == tenant_id,
                CodeComponent.analysis_status.in_(("completed", "complete")),
                CodeComponent.structured_analysis.isnot(None),
            )
            .all()
        )
        total = len(components)
        logger.info(
            "[P3.6] Backfill starting repo=%s tenant=%s components=%d",
            repository_id, tenant_id, total,
        )
        for c in components:
            try:
                count = data_flow_service.build_flow_for_component(db=db, component=c)
                edges_written += count
                processed += 1
            except Exception as per_err:
                failed += 1
                logger.warning(
                    "[P3.6] Edge build failed for component %s: %s", c.id, per_err,
                )
            # Progress updates — enables frontend polling card.
            if processed % 10 == 0:
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "processed": processed,
                        "total": total,
                        "edges_written": edges_written,
                        "failed": failed,
                    },
                )

        result = {
            "repository_id": repository_id,
            "tenant_id": tenant_id,
            "processed": processed,
            "total": total,
            "edges_written": edges_written,
            "failed": failed,
        }
        logger.info("[P3.6] Backfill complete: %s", result)
        return result

    except Exception as exc:
        logger.error("[P3.6] Backfill failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


@celery_app.task(name="rebuild_component_data_flow", bind=True, max_retries=1)
def rebuild_component_data_flow(
    self,
    component_id: int,
    tenant_id: int,
) -> dict[str, Any]:
    """One-off rebuild for a single component."""
    from app.db.session import SessionLocal
    from app.models.code_component import CodeComponent
    from app.services.data_flow_service import data_flow_service

    db = SessionLocal()
    try:
        component = (
            db.query(CodeComponent)
            .filter(
                CodeComponent.id == component_id,
                CodeComponent.tenant_id == tenant_id,
            )
            .first()
        )
        if not component:
            return {"component_id": component_id, "edges_written": 0, "skipped": True}
        count = data_flow_service.build_flow_for_component(db=db, component=component)
        return {
            "component_id": component_id,
            "tenant_id": tenant_id,
            "edges_written": count,
        }
    except Exception as exc:
        logger.error("[P3.6] Rebuild failed for component %s: %s", component_id, exc)
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
