from datetime import datetime

from sqlalchemy import Integer, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class ConsolidatedAnalysis(Base):
    """Stores a persisted consolidated analysis for a document."""
    __tablename__ = "consolidated_analyses"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_consolidated_analyses_document"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)

    # The consolidated JSON blob synthesized from segment analyses
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Optional relationship back to Document for convenience
    document = relationship("Document", backref="consolidated_analysis")


