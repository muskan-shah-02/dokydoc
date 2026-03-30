from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User  # noqa: F401
    from .document import Document  # noqa: F401
    from .code_component import CodeComponent  # noqa: F401
    from .requirement_atom import RequirementAtom  # noqa: F401

class Mismatch(Base):
    """
    Database model for storing validation mismatches.

    direction="forward"  — doc→code gap: developer missed something in the BRD
    direction="reverse"  — code→doc gap: developer built something not in the BRD
    """
    __tablename__ = "mismatches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)

    mismatch_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String, default="new", index=True, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # "forward" = doc→code (developer missed BRD requirement)
    # "reverse" = code→doc (developer built undocumented capability)
    direction: Mapped[Optional[str]] = mapped_column(String, default="forward", nullable=True)

    # Link to the specific RequirementAtom that triggered this mismatch (None for reverse/old records)
    requirement_atom_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("requirement_atoms.id"), nullable=True
    )

    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False)
    code_component_id: Mapped[int] = mapped_column(Integer, ForeignKey("code_components.id"), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))

    owner: Mapped["User"] = relationship("User")
    document: Mapped["Document"] = relationship("Document")
    code_component: Mapped["CodeComponent"] = relationship("CodeComponent")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
