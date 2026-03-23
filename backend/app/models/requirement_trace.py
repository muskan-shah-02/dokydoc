"""
Requirement Trace Model

Links individual BRD requirements to their implementing code concepts/functions.
Part of the 3-layer hybrid validation system (Layer 2: Requirement-Level Traceability).

Layer 1 (Graph Mapping) → coverage scan ("85% mapped")
Layer 2 (RequirementTrace) → granular linking ("Req 3.1 → auth_handler.verify_mfa()")
Layer 3 (Logic Validation) → correctness check ("code says 3 attempts, BRD says 5")
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base_class import Base


class RequirementTrace(Base):
    __tablename__ = "requirement_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    initiative_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("initiatives.id", ondelete="CASCADE"),
        nullable=True, index=True
    )

    # Source: which document and requirement
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    requirement_key: Mapped[str] = mapped_column(String(100), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Target: code concepts and files that implement this requirement
    code_concept_ids: Mapped[dict] = mapped_column(JSONB, default=list)
    code_component_ids: Mapped[dict] = mapped_column(JSONB, default=list)

    # Coverage status
    coverage_status: Mapped[str] = mapped_column(
        String(30), default="not_covered", nullable=False
    )  # fully_covered | partially_covered | not_covered | contradicted

    # Validation status
    validation_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending | validated | failed
    validation_details: Mapped[dict] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return (
            f"<RequirementTrace(id={self.id}, key='{self.requirement_key}', "
            f"coverage='{self.coverage_status}')>"
        )
