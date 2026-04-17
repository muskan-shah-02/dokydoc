"""P5C-08: ComplianceScoreSnapshot — daily compliance score per document for trend tracking."""
from datetime import datetime, date
from sqlalchemy import Integer, Float, ForeignKey, DateTime, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base


class ComplianceScoreSnapshot(Base):
    """
    Daily compliance score snapshot per document.
    Created by a nightly Celery beat task and after each validation scan.
    Unique constraint on (document_id, snapshot_date) — one row per document per day (UPSERT).
    """
    __tablename__ = "compliance_score_snapshots"
    __table_args__ = (
        UniqueConstraint("document_id", "snapshot_date", name="uq_snapshot_document_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    total_atoms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    covered_atoms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    open_mismatches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_mismatches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
