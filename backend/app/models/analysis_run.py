from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Integer, String, ForeignKey, DateTime, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class AnalysisRunStatus(str, Enum):
    """Status of an analysis run"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisRun(Base):
    """
    Tracks each analysis execution with proper lifecycle management.
    This replaces the simple in-memory locking with persistent run tracking.
    """
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Foreign key to document
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    
    # Who triggered this analysis
    triggered_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Run status and lifecycle
    status: Mapped[AnalysisRunStatus] = mapped_column(
        SQLEnum(AnalysisRunStatus), 
        default=AnalysisRunStatus.PENDING, 
        nullable=False
    )
    
    # Timestamps for tracking
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Progress tracking
    total_segments: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_segments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_segments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Error information if run failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Metadata about the run
    learning_mode: Mapped[bool] = mapped_column(default=False, nullable=False)
    run_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Relationships
    document = relationship("Document", backref="analysis_runs")
    triggered_by = relationship("User", backref="triggered_analysis_runs")
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate run duration in seconds"""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()
    
    @property
    def progress_percentage(self) -> float:
        """Calculate completion percentage"""
        if not self.total_segments or self.total_segments == 0:
            return 0.0
        return (self.completed_segments / self.total_segments) * 100
    
    def __repr__(self):
        return f"<AnalysisRun(id={self.id}, document_id={self.document_id}, status={self.status})>"
