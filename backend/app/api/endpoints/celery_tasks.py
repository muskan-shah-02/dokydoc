"""
Phase 3 — P3.12: Celery task status polling endpoint.

GET /tasks/{task_id}/status
  Returns Celery AsyncResult state + metadata. Used by the
  BackfillProgressCard to show live progress during edge backfill.
"""
from typing import Any
from fastapi import APIRouter, Depends

from app.api import deps
from app.models.user import User

router = APIRouter()


@router.get("/{task_id}/status")
def get_task_status(
    task_id: str,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Poll the status of a Celery task by ID.

    Returns:
      state: PENDING | STARTED | PROGRESS | SUCCESS | FAILURE | RETRY | REVOKED
      meta:  task-specific metadata (e.g. {processed, total, edges_written})
      result: populated when state == SUCCESS
    """
    from app.worker import celery_app
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)
    state = result.state
    meta: Any = None

    if state == "PROGRESS":
        meta = result.info  # dict from self.update_state(meta=...)
    elif state == "SUCCESS":
        meta = result.result
    elif state == "FAILURE":
        # Avoid leaking internal tracebacks — return message only.
        exc = result.info
        meta = {"error": str(exc) if exc else "Unknown error"}

    return {
        "task_id": task_id,
        "state": state,
        "meta": meta,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
    }
