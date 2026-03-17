"""
Document Version Model — tracks full-text snapshots of each document upload.
Sprint 8: Version Comparison Feature.
"""
from datetime import datetime
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base


class DocumentVersion(Base):
    """
    Stores a text snapshot every time a document is uploaded (or re-uploaded).
    Enables side-by-side diff between any two versions.
    """
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Full extracted text at this version (from document parser)
    content_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # SHA-256 of content_text for fast change detection
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # File metadata
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=True)
    # Who uploaded this version
    uploaded_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
