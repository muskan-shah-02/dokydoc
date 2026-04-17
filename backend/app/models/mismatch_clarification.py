"""P5C-03: MismatchClarification — BA ↔ Developer clarification thread on a mismatch."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User
    from .mismatch import Mismatch


class MismatchClarification(Base):
    """
    A clarification request attached to a mismatch.
    BA asks a question → developer answers → BA closes.
    Lifecycle: open → answered → closed
    """
    __tablename__ = "mismatch_clarifications"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'answered', 'closed')", name="ck_clarification_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mismatch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mismatches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    assignee_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    requester: Mapped["User"] = relationship("User", foreign_keys=[requested_by_user_id])
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assignee_user_id])
