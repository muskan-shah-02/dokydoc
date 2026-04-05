"""
Training Examples API — Data Flywheel

Endpoints for recording AI judgments and capturing human feedback.
These records are the raw material for future model fine-tuning.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app import crud, models
from app.schemas.training_example import (
    TrainingExampleOut, FeedbackRequest
)

router = APIRouter()


@router.post("/{example_id}/feedback", response_model=TrainingExampleOut)
def submit_feedback(
    example_id: int,
    body: FeedbackRequest,
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Record human feedback on an AI judgment.

    - feedback_source: 'accept' | 'reject' | 'edit'
    - human_label: required when feedback_source == 'edit'; the corrected text
    """
    valid_sources = {"accept", "reject", "edit"}
    if body.feedback_source not in valid_sources:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"feedback_source must be one of: {valid_sources}"
        )
    if body.feedback_source == "edit" and not body.human_label:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="human_label is required when feedback_source is 'edit'"
        )

    result = crud.training_example.apply_feedback(
        db=db,
        example_id=example_id,
        tenant_id=tenant_id,
        feedback_source=body.feedback_source,
        human_label=body.human_label,
        reviewer_id=current_user.id,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training example not found")
    return result


@router.get("/", response_model=List[TrainingExampleOut])
def list_unlabeled(
    task_type: Optional[str] = None,
    limit: int = 50,
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """Return AI judgments that haven't been reviewed by a human yet."""
    return crud.training_example.get_unlabeled(
        db=db, tenant_id=tenant_id, task_type=task_type, limit=min(limit, 200)
    )


@router.get("/stats")
def flywheel_stats(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """Return counts per task_type + feedback_source for the flywheel dashboard."""
    return crud.training_example.stats(db=db, tenant_id=tenant_id)


@router.get("/export")
def export_labeled(
    task_type: Optional[str] = None,
    limit: int = 1000,
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Export labeled examples in JSONL format for fine-tuning.
    Each row: {"prompt": input_text, "completion": human_label}
    """
    examples = crud.training_example.get_labeled(
        db=db, tenant_id=tenant_id, task_type=task_type, limit=min(limit, 10000)
    )
    lines = [
        {"prompt": ex.input_text, "completion": ex.human_label, "task_type": ex.task_type}
        for ex in examples
    ]
    from fastapi.responses import JSONResponse
    return JSONResponse(content={"count": len(lines), "examples": lines})
