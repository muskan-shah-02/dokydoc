from typing import TYPE_CHECKING, List
import enum
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .analysis_result import AnalysisResult  # noqa: F401
    from .document_segment import DocumentSegment  # noqa: F401
    from .user import User  # noqa: F401


# --- Re-introducing Enums (required by the model) ---
class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    PARSING_FAILED = "parsing_failed"
    ANALYSIS_FAILED = "analysis_failed"
    UNKNOWN = "unknown"
    # --- ADDED per architect plan (UX-02)  ---
    PASS_1_COMPOSITION = "pass_1_composition"
    PASS_2_SEGMENTING = "pass_2_segmenting"
    PASS_3_EXTRACTION = "pass_3_extraction"


class DocumentType(str, enum.Enum):
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    TEST_PLAN = "test_plan"
    USER_MANUAL = "user_manual"
    API_DOCS = "api_docs"
    OTHER = "other"
# --- End of Enums ---


class Document(Base):
    """Database model for storing document metadata and content."""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)  # Multi-tenancy support
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
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Stores the output of Pass 1 (Composition & Classification).
    # Example: {"BRD": 80, "API_DOCS": 20}
    composition_analysis: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    status: Mapped[str] = mapped_column(String, default=DocumentStatus.UPLOADED.value)  # Using enum default
    progress: Mapped[int] = mapped_column(Integer, default=0)
    
    # --- NEW COLUMN FOR DAE-01 (Architect's Plan)  ---
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # File size in KB
    file_size_kb: Mapped[int] = mapped_column(Integer, nullable=True)

    # --- Cost Tracking Fields (Sprint 1: BE-COST-02) ---
    # Total AI cost for this document in INR (Indian Rupees)
    ai_cost_inr: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)

    # Token counts for cost calculation
    token_count_input: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_count_output: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Cost breakdown by analysis pass: {"pass1": 0.001, "pass2": 0.003, "pass3": 0.005}
    cost_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=True)

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
    
    # --- ADDED: Missing relationship ---
    analysis_results: Mapped[List["AnalysisResult"]] = relationship(
        "AnalysisResult", back_populates="document", cascade="all, delete-orphan"
    )
    
    # Owner of the document
    owner: Mapped["User"] = relationship("User", back_populates="documents")