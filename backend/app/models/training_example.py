"""
TrainingExample — Data Flywheel

Every AI judgment + human correction gets stored here.
This data trains future, cheaper, domain-specific models.
It can NEVER be recovered retroactively — capture must start now.

Schema designed for LoRA fine-tuning export:
  - input_text: what the model saw
  - ai_output: what the model predicted
  - human_label: what the human said the correct answer is (null = not yet reviewed)
  - feedback_source: 'accept' | 'reject' | 'edit' | 'auto' (auto = no human review)
"""
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime,
    ForeignKey, Enum as SAEnum, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base


class FeedbackSource(str, enum.Enum):
    accept = "accept"    # Human clicked "accept" on AI output
    reject = "reject"    # Human clicked "reject" on AI output
    edit   = "edit"      # Human edited the AI output
    auto   = "auto"      # No human review — captured for volume/baseline


class TrainingExample(Base):
    __tablename__ = "training_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # --- Tenant & source context ---
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    # e.g. "mismatch_detection", "concept_mapping", "gap_analysis", "requirement_atom"

    # --- The AI's input/output ---
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    ai_output: Mapped[str] = mapped_column(Text, nullable=False)
    ai_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=True)

    # --- Human correction (null until a human acts) ---
    human_label: Mapped[str] = mapped_column(Text, nullable=True)
    feedback_source: Mapped[str] = mapped_column(
        SAEnum(FeedbackSource, name="feedback_source_enum"),
        nullable=False,
        default=FeedbackSource.auto,
    )
    feedback_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reviewer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # --- Optional FK to the source object (for traceability) ---
    source_mismatch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mismatches.id", ondelete="SET NULL"), nullable=True
    )

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # --- Relationships ---
    reviewer = relationship("User", foreign_keys=[reviewer_id])

    __table_args__ = (
        Index("idx_training_examples_tenant_task", "tenant_id", "task_type"),
        Index("idx_training_examples_feedback_source", "feedback_source"),
        Index("idx_training_examples_created_at", "created_at"),
    )
