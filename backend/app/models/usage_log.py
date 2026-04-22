"""
Usage Log model for tracking all AI API calls across features.
Provides granular visibility into token usage and costs per operation.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, Numeric, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base_class import Base


class FeatureType(str, enum.Enum):
    """Types of features that use AI API calls."""
    DOCUMENT_ANALYSIS = "document_analysis"
    CODE_ANALYSIS = "code_analysis"
    VALIDATION = "validation"
    CHAT = "chat"
    SUMMARY = "summary"
    OTHER = "other"


class OperationType(str, enum.Enum):
    """Specific operations within features."""
    # Document Analysis Operations
    PASS_1_COMPOSITION = "pass_1_composition"
    PASS_2_SEGMENTING = "pass_2_segmenting"
    PASS_3_EXTRACTION = "pass_3_extraction"

    # Code Analysis Operations
    CODE_REVIEW = "code_review"
    CODE_EXPLANATION = "code_explanation"
    CODE_GENERATION = "code_generation"

    # Validation Operations
    REQUIREMENT_VALIDATION = "requirement_validation"
    CODE_VALIDATION = "code_validation"
    TRACEABILITY_CHECK = "traceability_check"

    # Other Operations
    CHAT_RESPONSE = "chat_response"
    DOCUMENT_SUMMARY = "document_summary"
    CUSTOM = "custom"


class UsageLog(Base):
    """
    Database model for tracking all AI API usage.

    Enables:
    - Cost breakdown by feature (document analysis, code analysis, etc.)
    - Time-based analytics (daily, weekly, monthly)
    - Token usage tracking (input/output)
    - Per-document and aggregate reporting
    """
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Tenant isolation (required)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # User who triggered the action (optional - some are system-triggered)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Document reference (optional - not all operations are document-related)
    document_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("documents.id"), nullable=True, index=True)

    # Feature and operation classification
    feature_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=FeatureType.OTHER.value
    )
    operation: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=OperationType.CUSTOM.value
    )

    # Model information
    model_used: Mapped[str] = mapped_column(String(100), nullable=False, default="gemini-2.5-flash")

    # Token counts
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Computed total tokens (for convenience)
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    # Cost tracking
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0.0)
    cost_inr: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0.0)

    # Phase 9: Markup transparency
    raw_cost_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    markup_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    markup_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    thinking_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Processing time in seconds
    processing_time_seconds: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Additional context data (JSON for flexibility)
    # Note: Can't use 'metadata' as it's reserved by SQLAlchemy
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
        index=True  # Indexed for time-based queries
    )

    # Relationships
    # tenant = relationship("Tenant", back_populates="usage_logs")
    # user = relationship("User", back_populates="usage_logs")
    # document = relationship("Document", back_populates="usage_logs")

    def __repr__(self):
        return f"<UsageLog(id={self.id}, feature={self.feature_type}, tokens={self.total_tokens}, cost_inr={self.cost_inr})>"
