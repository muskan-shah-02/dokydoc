"""WalletTransaction model — prepaid credit ledger for Phase 9 billing."""
from datetime import datetime
from typing import Optional
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # "credit" | "debit" | "refund" | "signup_bonus"
    txn_type: Mapped[str] = mapped_column(String(30), nullable=False)

    amount_inr: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    balance_after_inr: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    usage_log_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("usage_logs.id", ondelete="SET NULL"), nullable=True
    )

    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<WalletTransaction(id={self.id}, tenant={self.tenant_id}, "
            f"type={self.txn_type}, amount=₹{self.amount_inr})>"
        )
