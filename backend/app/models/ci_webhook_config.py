"""P5C-06: CIWebhookConfig — per-tenant CI webhook secret for receiving test results."""
import secrets
from typing import Optional
from datetime import datetime
from sqlalchemy import Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base


class CIWebhookConfig(Base):
    """
    Per-tenant CI webhook configuration.
    Stores the HMAC-SHA256 secret used to verify incoming CI test result payloads.
    One row per tenant (unique constraint on tenant_id).
    """
    __tablename__ = "ci_webhook_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    webhook_secret: Mapped[str] = mapped_column(String(64), nullable=False)
    document_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    @staticmethod
    def generate_secret() -> str:
        return secrets.token_hex(32)  # 64 hex chars
