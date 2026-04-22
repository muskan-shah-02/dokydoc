"""EnterpriseContactRequest model — enterprise sales pipeline for Phase 9."""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class EnterpriseContactRequest(Base):
    __tablename__ = "enterprise_contact_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    company_name: Mapped[str] = mapped_column(String(300), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(300), nullable=False)
    email: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # "1-10" | "11-50" | "51-200" | "200+"
    team_size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    use_case: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True
    )
    submitted_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # "new" | "contacted" | "qualified" | "demo_scheduled" | "closed_won" | "closed_lost"
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new", index=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<EnterpriseContactRequest(id={self.id}, company={self.company_name!r}, "
            f"email={self.email!r}, status={self.status!r})>"
        )
