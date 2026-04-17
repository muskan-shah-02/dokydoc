"""P5C-04: UATChecklistItem — one manual UAT test item linked to a 'manual' testability atom."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

if TYPE_CHECKING:
    from .requirement_atom import RequirementAtom


class UATChecklistItem(Base):
    """
    One manual UAT test item, linked to a 'manual' testability atom.
    Created automatically after atomization. QA/BA checks off with result + notes.
    Lifecycle: unchecked (result=None) → pass | fail | blocked
    """
    __tablename__ = "uat_checklist_items"
    __table_args__ = (
        CheckConstraint(
            "result IS NULL OR result IN ('pass', 'fail', 'blocked')",
            name="ck_uat_result"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    atom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("requirement_atoms.id", ondelete="CASCADE"), nullable=False
    )
    checked_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    atom: Mapped["RequirementAtom"] = relationship("RequirementAtom")
