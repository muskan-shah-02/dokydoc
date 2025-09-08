from typing import TYPE_CHECKING, List
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .analysis_result import AnalysisResult  # noqa: F401
    from .document import Document  # noqa: F401


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
    
    # A segment belongs to one document.
    document: Mapped["Document"] = relationship("Document", back_populates="segments")
    
    # A segment can have multiple analysis results (e.g., from different profiles).
    analysis_results: Mapped[List["AnalysisResult"]] = relationship(
        "AnalysisResult", back_populates="segment", cascade="all, delete-orphan"
    )
    
    # Timestamp fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
