from typing import TYPE_CHECKING
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User  # noqa: F401
    from .document import Document  # noqa: F401
    from .code_component import CodeComponent  # noqa: F401

class Mismatch(Base):
    """
    Database model for storing validation mismatches.
    """
    __tablename__ = "mismatches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    mismatch_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String, default="new", index=True, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # --- NEW COLUMNS TO ADD ---
    
    # The AI's confidence in this mismatch finding (e.g., "High", "Medium", "Low")
    confidence: Mapped[str] = mapped_column(String, nullable=True)
    
    # A field for users to add notes or context to a mismatch
    user_notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # --- END OF NEW COLUMNS ---

    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False)
    code_component_id: Mapped[int] = mapped_column(Integer, ForeignKey("code_components.id"), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))

    owner: Mapped["User"] = relationship("User")
    document: Mapped["Document"] = relationship("Document")
    code_component: Mapped["CodeComponent"] = relationship("CodeComponent")
    
    # Timestamp fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
