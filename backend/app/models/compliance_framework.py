"""
Phase 6: ComplianceFramework + TenantComplianceSelection models.
"""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class ComplianceFramework(Base):
    """
    System-wide or tenant-custom regulatory/compliance framework.

    System frameworks (is_system=True, tenant_id=None) are seeded by migration
    and visible to all tenants.  Tenant-custom frameworks are private.
    """
    __tablename__ = "compliance_frameworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    geography: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Industries this framework typically applies to (e.g. ["fintech/payments", "banking"])
    applicable_industries: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # System-seeded vs tenant-created
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("code", "tenant_id", name="uq_compliance_code_tenant"),
    )


class TenantComplianceSelection(Base):
    """
    Junction: which compliance frameworks a tenant has selected.
    """
    __tablename__ = "tenant_compliance_selections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    framework_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("compliance_frameworks.id", ondelete="CASCADE"), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    framework: Mapped["ComplianceFramework"] = relationship("ComplianceFramework")

    __table_args__ = (
        UniqueConstraint("tenant_id", "framework_id", name="uq_tenant_framework"),
    )
