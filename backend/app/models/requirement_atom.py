from typing import TYPE_CHECKING, Optional, List
from datetime import datetime

from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .document import Document  # noqa: F401


class RequirementAtom(Base):
    """
    A single, discrete, typed requirement extracted from a BRD/document.

    Instead of comparing the full document prose against code, the validation engine
    first decomposes the document into atoms — each representing exactly one testable
    requirement. Validation then checks each atom individually against the code.

    Atom types:
      API_CONTRACT          - HTTP endpoints, methods, request/response shapes
      BUSINESS_RULE         - Conditions, calculations, eligibility, pricing
      FUNCTIONAL_REQUIREMENT - System capabilities (shall/must/should statements)
      DATA_CONSTRAINT       - Field types, validations, length/range rules
      WORKFLOW_STEP         - Ordered process steps, state transitions
      ERROR_SCENARIO        - Error cases, exception handling, failure behaviors
      SECURITY_REQUIREMENT  - Auth, RBAC, encryption, compliance
      NFR                   - Performance, scalability, latency requirements
      INTEGRATION_POINT     - External system calls, webhooks, third-party
    """
    __tablename__ = "requirement_atoms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)

    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Human-readable ID: REQ-001, REQ-002, etc. (scoped per document)
    atom_id: Mapped[str] = mapped_column(String(20), nullable=False)

    # Type of requirement — drives which validation pass checks this atom
    atom_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # The original requirement sentence from the BRD
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # How critical this requirement is to business goals
    criticality: Mapped[str] = mapped_column(String(20), default="standard", nullable=False)

    # Document version at time of atomization — used to detect when re-atomization is needed
    document_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # P4-01: True when atoms were extracted eagerly at upload time
    # (vs lazily at first validation run). Enables hit-rate analytics.
    atomized_at_upload: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # P5B-01: SHA-256 of normalized content — enables change detection between versions
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # P5B-01: Links this atom to its equivalent in the previous document version
    # NULL = new atom (first version or no prior version)
    previous_atom_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("requirement_atoms.id", ondelete="SET NULL"), nullable=True
    )

    # P5B-01: Change classification vs prior version
    # "added" | "modified" | "unchanged" | NULL (first version)
    delta_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    # P5B-08: Regulatory frameworks applicable to this atom (e.g. ["PCI-DSS", "RBI"])
    regulatory_tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)

    document: Mapped["Document"] = relationship("Document")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
