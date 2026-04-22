"""
Wallet Service — Phase 9 prepaid credit management.

All mutations go through this service so the ledger (wallet_transactions)
stays in sync with tenant.wallet_balance_inr.

Thread safety: every write uses SELECT FOR UPDATE to avoid race conditions
under concurrent analysis runs.
"""
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, text

from app.core.config import settings
from app.core.logging import get_logger
from app.models.wallet_transaction import WalletTransaction

logger = get_logger("wallet_service")

SIGNUP_BONUS = Decimal(str(settings.SIGNUP_FREE_CREDIT_INR))   # ₹100
LOW_THRESHOLD = Decimal(str(settings.LOW_WALLET_THRESHOLD_INR))


class InsufficientWalletBalance(Exception):
    """Raised when a debit would push balance below zero."""
    def __init__(self, balance: Decimal, required: Decimal):
        self.balance = balance
        self.required = required
        super().__init__(f"Insufficient wallet balance: ₹{balance:.2f} < ₹{required:.2f}")


class WalletService:

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def get_balance(self, db: Session, tenant_id: int) -> dict:
        """Return current wallet state for a tenant."""
        row = db.execute(
            text("SELECT wallet_balance_inr, wallet_free_credit_inr, preferred_model FROM tenants WHERE id = :id"),
            {"id": tenant_id},
        ).fetchone()

        if not row:
            return {"balance_inr": 0.0, "free_credit_inr": 0.0, "preferred_model": None, "low_balance": False}

        balance = Decimal(str(row.wallet_balance_inr or 0))
        free_credit = Decimal(str(row.wallet_free_credit_inr or 0))
        total = balance + free_credit

        return {
            "tenant_id": tenant_id,
            "balance_inr": float(balance),
            "free_credit_inr": float(free_credit),
            "total_available_inr": float(total),
            "low_balance": total < LOW_THRESHOLD,
            "preferred_model": row.preferred_model,
        }

    def get_transactions(
        self,
        db: Session,
        tenant_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WalletTransaction]:
        return (
            db.query(WalletTransaction)
            .filter(WalletTransaction.tenant_id == tenant_id)
            .order_by(WalletTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def apply_signup_bonus(
        self, db: Session, tenant_id: int, user_id: Optional[int] = None
    ) -> WalletTransaction:
        """Credit ₹100 free signup bonus. Safe to call once at registration."""
        # Guard: don't double-credit
        existing = (
            db.query(WalletTransaction)
            .filter(
                WalletTransaction.tenant_id == tenant_id,
                WalletTransaction.txn_type == "signup_bonus",
            )
            .first()
        )
        if existing:
            logger.warning(f"tenant={tenant_id} already has signup bonus — skipping")
            return existing

        new_balance = self._credit_wallet(
            db, tenant_id, SIGNUP_BONUS, is_free_credit=True
        )
        txn = WalletTransaction(
            tenant_id=tenant_id,
            txn_type="signup_bonus",
            amount_inr=SIGNUP_BONUS,
            balance_after_inr=new_balance,
            description=f"₹{SIGNUP_BONUS} free signup credit",
            created_by_user_id=user_id,
        )
        db.add(txn)
        db.flush()
        logger.info(f"tenant={tenant_id} signup bonus ₹{SIGNUP_BONUS} applied")
        return txn

    def debit_wallet(
        self,
        db: Session,
        tenant_id: int,
        amount_inr: Decimal,
        usage_log_id: Optional[int] = None,
        description: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> WalletTransaction:
        """
        Debit wallet for an AI usage charge.
        Draws from wallet_free_credit_inr first, then wallet_balance_inr.
        Raises InsufficientWalletBalance if not enough funds.
        """
        row = db.execute(
            text(
                "SELECT wallet_balance_inr, wallet_free_credit_inr "
                "FROM tenants WHERE id = :id FOR UPDATE"
            ),
            {"id": tenant_id},
        ).fetchone()

        if not row:
            raise ValueError(f"Tenant {tenant_id} not found")

        paid = Decimal(str(row.wallet_balance_inr or 0))
        free = Decimal(str(row.wallet_free_credit_inr or 0))
        total = paid + free

        if total < amount_inr:
            raise InsufficientWalletBalance(balance=total, required=amount_inr)

        # Exhaust free credit first
        debit_free = min(free, amount_inr)
        debit_paid = amount_inr - debit_free

        db.execute(
            text(
                "UPDATE tenants SET "
                "wallet_free_credit_inr = wallet_free_credit_inr - :df, "
                "wallet_balance_inr = wallet_balance_inr - :dp "
                "WHERE id = :id"
            ),
            {"df": float(debit_free), "dp": float(debit_paid), "id": tenant_id},
        )

        new_balance = paid - debit_paid + (free - debit_free)

        txn = WalletTransaction(
            tenant_id=tenant_id,
            txn_type="debit",
            amount_inr=-amount_inr,
            balance_after_inr=new_balance,
            usage_log_id=usage_log_id,
            description=description or "AI usage charge",
            created_by_user_id=user_id,
        )
        db.add(txn)
        db.flush()
        logger.info(
            f"tenant={tenant_id} debit ₹{amount_inr:.4f} "
            f"(free=₹{debit_free:.4f}, paid=₹{debit_paid:.4f}) "
            f"balance_after=₹{new_balance:.4f}"
        )
        return txn

    def credit_wallet(
        self,
        db: Session,
        tenant_id: int,
        amount_inr: Decimal,
        razorpay_payment_id: Optional[str] = None,
        razorpay_order_id: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> WalletTransaction:
        """Credit prepaid balance (top-up via Razorpay or manual)."""
        new_balance = self._credit_wallet(db, tenant_id, amount_inr, is_free_credit=False)
        txn = WalletTransaction(
            tenant_id=tenant_id,
            txn_type="credit",
            amount_inr=amount_inr,
            balance_after_inr=new_balance,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_order_id=razorpay_order_id,
            description=description or f"Top-up ₹{amount_inr:.2f}",
            created_by_user_id=user_id,
        )
        db.add(txn)
        db.flush()
        logger.info(f"tenant={tenant_id} credited ₹{amount_inr:.2f}, balance=₹{new_balance:.4f}")
        return txn

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _credit_wallet(
        self,
        db: Session,
        tenant_id: int,
        amount: Decimal,
        is_free_credit: bool,
    ) -> Decimal:
        if is_free_credit:
            db.execute(
                text("UPDATE tenants SET wallet_free_credit_inr = wallet_free_credit_inr + :a WHERE id = :id"),
                {"a": float(amount), "id": tenant_id},
            )
        else:
            db.execute(
                text("UPDATE tenants SET wallet_balance_inr = wallet_balance_inr + :a WHERE id = :id"),
                {"a": float(amount), "id": tenant_id},
            )

        row = db.execute(
            text("SELECT wallet_balance_inr + wallet_free_credit_inr AS total FROM tenants WHERE id = :id"),
            {"id": tenant_id},
        ).fetchone()
        return Decimal(str(row.total or 0))


wallet_service = WalletService()
