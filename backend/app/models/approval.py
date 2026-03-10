"""
Approval model for formal approval gates on critical actions.
Sprint 6: Approval Workflow — supports multi-level approval chains.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class Approval(Base):
    """
    Generic approval record that can gate any entity type.

    Supports multi-level approval chains:
      Level 1 = Developer/BA (peer review)
      Level 2 = Lead/Admin (managerial sign-off)
      Level 3 = CXO (executive approval)
    """
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Tenant isolation
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=False, index=True
    )

    # What is being approved
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # "document" | "repository" | "mismatch_resolution" | "requirement_trace" | "validation_report"

    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)

    entity_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Approval status
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )  # "pending" | "approved" | "rejected" | "revision_requested"

    # Who requested the approval
    requested_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    requested_by_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Who resolved the approval (nullable until resolved)
    resolved_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    resolved_by_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Approval level required (1=peer, 2=lead, 3=CXO)
    approval_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Notes / reason
    request_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self):
        return (
            f"<Approval(id={self.id}, entity={self.entity_type}#{self.entity_id}, "
            f"status={self.status}, level={self.approval_level})>"
        )
