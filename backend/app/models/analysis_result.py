from typing import TYPE_CHECKING, Optional
from datetime import datetime
from enum import Enum

from sqlalchemy import ForeignKey, Integer, DateTime, Enum as SQLEnum, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .document import Document  # noqa: F401 - Keep for potential future direct links
    from .document_segment import DocumentSegment # noqa: F401


class AnalysisResultStatus(str, Enum):
    """Status of an analysis result"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class AnalysisResult(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # The structured JSON output from Pass 3 of the analysis.
    # Make this nullable since failed results won't have structured data
    structured_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # An analysis result is now linked to a specific segment of a document.
    segment_id: Mapped[int] = mapped_column(ForeignKey("document_segments.id"), nullable=False)
    
    # The original document_id is now nullable. The primary relationship is through the segment.
    # We keep it for now for easier querying, but it's technically redundant.
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=True)
    
    # Status and error tracking for Phase 2 architecture
    status: Mapped[AnalysisResultStatus] = mapped_column(
        SQLEnum(AnalysisResultStatus), 
        default=AnalysisResultStatus.PENDING, 
        nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    segment: Mapped["DocumentSegment"] = relationship(
        "DocumentSegment", back_populates="analysis_results"
    )
    
    # Timestamp fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
