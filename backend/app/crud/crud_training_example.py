from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.training_example import TrainingExample, FeedbackSource
from app.schemas.training_example import TrainingExampleCreate, TrainingExampleUpdate


class CRUDTrainingExample(CRUDBase[TrainingExample, TrainingExampleCreate, TrainingExampleUpdate]):

    def capture(
        self,
        db: Session,
        *,
        tenant_id: int,
        task_type: str,
        input_text: str,
        ai_output: str,
        ai_confidence: Optional[float] = None,
        model_name: Optional[str] = None,
        source_mismatch_id: Optional[int] = None,
    ) -> TrainingExample:
        """
        Record an AI judgment. Called automatically — no human involved yet.
        feedback_source defaults to 'auto'.
        """
        obj = TrainingExample(
            tenant_id=tenant_id,
            task_type=task_type,
            input_text=input_text,
            ai_output=ai_output,
            ai_confidence=ai_confidence,
            model_name=model_name,
            feedback_source=FeedbackSource.auto,
            source_mismatch_id=source_mismatch_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def apply_feedback(
        self,
        db: Session,
        *,
        example_id: int,
        tenant_id: int,
        feedback_source: str,
        human_label: Optional[str] = None,
        reviewer_id: Optional[int] = None,
    ) -> Optional[TrainingExample]:
        """
        Record human feedback on an AI judgment.
        feedback_source: 'accept' | 'reject' | 'edit'
        human_label: required when feedback_source == 'edit'
        """
        obj = db.query(TrainingExample).filter(
            TrainingExample.id == example_id,
            TrainingExample.tenant_id == tenant_id,
        ).first()
        if not obj:
            return None

        obj.feedback_source = FeedbackSource(feedback_source)
        obj.feedback_at = datetime.utcnow()
        obj.updated_at = datetime.utcnow()
        if reviewer_id:
            obj.reviewer_id = reviewer_id
        if human_label is not None:
            obj.human_label = human_label
        elif feedback_source == "accept":
            # Accept = human confirms AI output is correct
            obj.human_label = obj.ai_output

        db.commit()
        db.refresh(obj)
        return obj

    def get_unlabeled(
        self,
        db: Session,
        *,
        tenant_id: int,
        task_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[TrainingExample]:
        """Fetch examples that haven't received human review yet."""
        q = db.query(TrainingExample).filter(
            TrainingExample.tenant_id == tenant_id,
            TrainingExample.feedback_source == FeedbackSource.auto,
        )
        if task_type:
            q = q.filter(TrainingExample.task_type == task_type)
        return q.order_by(TrainingExample.created_at.desc()).limit(limit).all()

    def get_labeled(
        self,
        db: Session,
        *,
        tenant_id: int,
        task_type: Optional[str] = None,
        limit: int = 1000,
    ) -> List[TrainingExample]:
        """Fetch examples with human labels — these are the training gold set."""
        q = db.query(TrainingExample).filter(
            TrainingExample.tenant_id == tenant_id,
            TrainingExample.feedback_source != FeedbackSource.auto,
            TrainingExample.human_label.isnot(None),
        )
        if task_type:
            q = q.filter(TrainingExample.task_type == task_type)
        return q.order_by(TrainingExample.created_at.desc()).limit(limit).all()

    def stats(self, db: Session, *, tenant_id: int) -> dict:
        """Return counts per task_type and feedback_source for the flywheel dashboard."""
        from sqlalchemy import func
        rows = (
            db.query(
                TrainingExample.task_type,
                TrainingExample.feedback_source,
                func.count(TrainingExample.id).label("cnt"),
            )
            .filter(TrainingExample.tenant_id == tenant_id)
            .group_by(TrainingExample.task_type, TrainingExample.feedback_source)
            .all()
        )
        result: dict = {}
        for task_type, feedback_source, cnt in rows:
            result.setdefault(task_type, {})[feedback_source] = cnt
        return result


training_example = CRUDTrainingExample(TrainingExample)
