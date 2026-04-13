"""
P5B-12: BRD Sign-Off model — formal BA sign-off with tamper-evident certificate.
"""
import hashlib
import json
from typing import Optional, TYPE_CHECKING
from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User  # noqa: F401
    from .document import Document  # noqa: F401


class BRDSignOff(Base):
    """
    Formal sign-off record for a document validation review.

    After a BA/admin reviews all mismatches and is satisfied, they sign off.
    A tamper-evident certificate_hash is generated from the sign-off content.
    """
    __tablename__ = "brd_sign_offs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_version_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True
    )
    repository_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
    )
    signed_by_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    signed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    # Snapshot of compliance state at sign-off time
    compliance_score_at_signoff: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    open_mismatches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_mismatches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Mismatch IDs the BA explicitly acknowledged (accepted risk)
    acknowledged_mismatch_ids: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    sign_off_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_unresolved_critical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Tamper-evident hash of the sign-off content
    certificate_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship("Document")
    signed_by: Mapped["User"] = relationship("User", foreign_keys=[signed_by_user_id])

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    def generate_certificate_hash(self) -> str:
        """
        Generate SHA-256 hash of the sign-off content for tamper detection.
        Any change to the referenced data will produce a different hash.
        """
        content = {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "document_id": self.document_id,
            "signed_by_user_id": self.signed_by_user_id,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
            "compliance_score": self.compliance_score_at_signoff,
            "open_mismatches": self.open_mismatches_count,
            "critical_mismatches": self.critical_mismatches_count,
            "acknowledged_ids": sorted(self.acknowledged_mismatch_ids or []),
        }
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
