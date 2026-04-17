"""P5C-03: CRUD for MismatchClarification."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.models.mismatch_clarification import MismatchClarification


class CRUDMismatchClarification:

    def create(
        self,
        db: Session,
        *,
        tenant_id: int,
        mismatch_id: int,
        requested_by_user_id: int,
        assignee_user_id: Optional[int],
        question: str,
    ) -> MismatchClarification:
        if len(question.strip()) < 10:
            raise ValueError("Question must be at least 10 characters")
        obj = MismatchClarification(
            tenant_id=tenant_id,
            mismatch_id=mismatch_id,
            requested_by_user_id=requested_by_user_id,
            assignee_user_id=assignee_user_id,
            question=question.strip(),
            status="open",
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def answer(
        self,
        db: Session,
        *,
        clarification_id: int,
        tenant_id: int,
        answering_user_id: int,
        answer: str,
    ) -> MismatchClarification:
        obj = db.query(MismatchClarification).filter(
            MismatchClarification.id == clarification_id,
            MismatchClarification.tenant_id == tenant_id,
            MismatchClarification.status == "open",
        ).first()
        if not obj:
            raise ValueError("Clarification not found or already answered")
        if len(answer.strip()) < 5:
            raise ValueError("Answer must be at least 5 characters")
        obj.answer = answer.strip()
        obj.status = "answered"
        obj.answered_at = datetime.utcnow()
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def close(
        self,
        db: Session,
        *,
        clarification_id: int,
        tenant_id: int,
    ) -> MismatchClarification:
        obj = db.query(MismatchClarification).filter(
            MismatchClarification.id == clarification_id,
            MismatchClarification.tenant_id == tenant_id,
        ).first()
        if not obj:
            raise ValueError("Clarification not found")
        obj.status = "closed"
        obj.closed_at = datetime.utcnow()
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get_by_mismatch(
        self,
        db: Session,
        *,
        mismatch_id: int,
        tenant_id: int,
    ) -> list[MismatchClarification]:
        return db.query(MismatchClarification).filter(
            MismatchClarification.mismatch_id == mismatch_id,
            MismatchClarification.tenant_id == tenant_id,
        ).order_by(MismatchClarification.created_at.asc()).all()


crud_mismatch_clarification = CRUDMismatchClarification()
