from typing import TYPE_CHECKING
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .document import Document  # noqa: F401 - Keep for potential future direct links
    from .document_segment import DocumentSegment # noqa: F401


class AnalysisResult(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # The structured JSON output from Pass 3 of the analysis.
    structured_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # An analysis result is now linked to a specific segment of a document.
    segment_id: Mapped[int] = mapped_column(ForeignKey("document_segments.id"), nullable=False)
    
    # The original document_id is now nullable. The primary relationship is through the segment.
    # We keep it for now for easier querying, but it's technically redundant.
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=True)

    segment: Mapped["DocumentSegment"] = relationship(
        "DocumentSegment", back_populates="analysis_results"
    )
    
    # Timestamp fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
