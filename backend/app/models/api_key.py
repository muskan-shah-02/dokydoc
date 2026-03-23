"""
ApiKey model — tenant-scoped programmatic access tokens.
Sprint 8: API Key Authentication.
"""
import secrets
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


def _generate_key_prefix() -> str:
    return "dk_live_"


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Display
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # The raw key is only returned at creation time.
    # We store a sha256 hash for comparison (never the raw key).
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # First 12 chars shown in UI as "dk_live_xxxx"
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    request_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
