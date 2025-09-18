from typing import TYPE_CHECKING, List, Optional
from datetime import datetime
from enum import Enum

from sqlalchemy import ForeignKey, Integer, String, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .analysis_result import AnalysisResult  # noqa: F401
    from .document import Document  # noqa: F401


class SegmentStatus(str, Enum):
    """Status of a document segment during analysis"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DocumentSegment(Base):
    """
    Represents a logical segment or "slice" of a parent document.
    This model allows us to analyze parts of a document without duplicating text.
    It points to a start and end character index within the parent's `raw_text`.
    """
    __tablename__ = "document_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # The type of content this segment represents, determined by Pass 1.
    # Example: "BRD", "API_DOCS", "UNKNOWN"
    segment_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    
    # Pointer to the start of the segment in the parent document's `raw_text`.
    start_char_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Pointer to the end of the segment in the parent document's `raw_text`.
    end_char_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    
    # Status and retry tracking for Phase 2 architecture
    status: Mapped[SegmentStatus] = mapped_column(
        SQLEnum(SegmentStatus), 
        default=SegmentStatus.PENDING, 
        nullable=False
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Link to the analysis run that created/processed this segment
    analysis_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("analysis_runs.id"), nullable=True)
    
    # A segment belongs to one document.
    document: Mapped["Document"] = relationship("Document", back_populates="segments")
    
    # Relationship to the analysis run
    analysis_run = relationship("AnalysisRun", backref="segments")
    
    # A segment can have multiple analysis results (e.g., from different profiles).
    analysis_results: Mapped[List["AnalysisResult"]] = relationship(
        "AnalysisResult", back_populates="segment", cascade="all, delete-orphan"
    )
    
    # Timestamp fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
