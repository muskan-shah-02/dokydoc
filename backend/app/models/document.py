from typing import TYPE_CHECKING, List
from datetime import datetime

from sqlalchemy import Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .analysis_result import AnalysisResult  # noqa: F401
    from .document_segment import DocumentSegment # noqa: F401


class Document(Base):
    """
    Database model for storing document metadata and content.
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String, index=True, nullable=False)
    
    # Document type classification (e.g., "BRD", "API_DOCS", "TECHNICAL_SPECS")
    document_type: Mapped[str] = mapped_column(String, nullable=True)
    
    # Document version for tracking changes
    version: Mapped[str] = mapped_column(String, default="1.0")
    
    # Owner of the document (links to users table)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Storage path for the original file
    storage_path: Mapped[str] = mapped_column(String, nullable=True)
    
    # The pristine, unmodified text content extracted from the document.
    # All other analyses and segments will reference this single source of truth.
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Stores the output of Pass 1 (Composition & Classification).
    # Example: {"BRD": 80, "API_DOCS": 20}
    composition_analysis: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    status: Mapped[str] = mapped_column(String, default="uploaded")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    
    # File size in KB
    file_size_kb: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # Legacy content field for backward compatibility
    content: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timestamp fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    # A document is composed of many segments.
    # The 'cascade' option ensures that when a document is deleted,
    # all of its associated segments are also deleted.
    segments: Mapped[List["DocumentSegment"]] = relationship(
        "DocumentSegment", back_populates="document", cascade="all, delete-orphan"
    )
    
    # Owner of the document
    owner: Mapped["User"] = relationship("User", back_populates="documents")
