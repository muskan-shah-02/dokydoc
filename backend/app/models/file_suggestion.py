"""P5C-01: FileSuggestion — AI-generated suggestion of which code files to upload."""
from typing import Optional
from datetime import datetime
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY
from app.db.base_class import Base


class FileSuggestion(Base):
    """
    AI-generated suggestion of which code files to upload to cover BRD atoms.
    Created after atomization completes. Marked fulfilled when the file is uploaded.
    """
    __tablename__ = "file_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    suggested_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    atom_ids: Mapped[list] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    atom_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fulfilled_by_component_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("code_components.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
