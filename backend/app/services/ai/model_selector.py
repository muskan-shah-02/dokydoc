"""
Model Selector — Phase 9 multi-model routing.

Two lanes:
  free  → gemini-2.0-flash-lite   (absorb ₹100 signup credit cheaply)
  paid  → caller-chosen model, defaulting to tenant.preferred_model or
           settings.GEMINI_MODEL (gemini-2.0-flash)

Decision order:
  1. explicit model passed by caller (e.g. per-document override)
  2. tenant.preferred_model (set in billing settings)
  3. settings.GEMINI_MODEL (server default — always a paid model)

Free-lane override: if tenant.wallet_balance_inr == 0 AND wallet_free_credit_inr > 0
  the tenant is still on signup credit → route to free model regardless.
"""
from typing import Optional
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("model_selector")

# Models that require paid wallet balance
PAID_MODELS = {
    "gemini-2.0-flash",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
}

FREE_MODEL = settings.GEMINI_FREE_MODEL   # gemini-2.0-flash-lite
DEFAULT_PAID_MODEL = settings.GEMINI_MODEL  # gemini-2.0-flash


class ModelSelector:
    """Resolve which AI model to use for a given analysis request."""

    def resolve(
        self,
        tenant=None,               # Tenant ORM object (optional for unauthenticated previews)
        requested_model: Optional[str] = None,
        force_free: bool = False,
    ) -> str:
        """
        Return the model ID to use.

        Args:
            tenant:           Tenant ORM row (provides wallet balance + preferred_model).
            requested_model:  Caller-specified model — honoured if tenant can afford it.
            force_free:       Skip all routing logic and use the free model.
        """
        if force_free:
            logger.debug("force_free=True → using free model")
            return FREE_MODEL

        if tenant is not None:
            balance = float(getattr(tenant, "wallet_balance_inr", 0) or 0)
            free_credit = float(getattr(tenant, "wallet_free_credit_inr", 0) or 0)

            # No real balance — route to free lane if still on signup credit
            if balance <= 0 and free_credit > 0:
                logger.info(
                    f"tenant={tenant.id} on free credit only "
                    f"(balance=₹{balance:.2f}, free=₹{free_credit:.2f}) → {FREE_MODEL}"
                )
                return FREE_MODEL

        # Honour caller request (paid model) if wallet has funds or no wallet check needed
        if requested_model and requested_model in PAID_MODELS:
            logger.debug(f"Using caller-requested model: {requested_model}")
            return requested_model

        # Tenant preference
        if tenant is not None:
            pref = getattr(tenant, "preferred_model", None)
            if pref and pref in PAID_MODELS:
                logger.debug(f"Using tenant preferred model: {pref}")
                return pref

        logger.debug(f"Using server default model: {DEFAULT_PAID_MODEL}")
        return DEFAULT_PAID_MODEL


model_selector = ModelSelector()
