"""
Cost calculation service — Phase 9 refactor.

Supports multi-model pricing (Gemini Flash, Gemini Flash-Lite, Claude Sonnet, Claude Haiku)
and applies a transparent 15% platform markup on every calculation.

Markup is always shown separately from raw cost so customers see exactly what
Google/Anthropic charged us vs. what DokyDoc adds.
"""
import httpx
from typing import Dict, Any, Optional
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger("cost_service")

# ---------------------------------------------------------------------------
# MARKUP
# ---------------------------------------------------------------------------
MARKUP_PERCENT = Decimal("15.00")   # flat 15% on raw AI cost (Phase 9 — never hidden)


# ---------------------------------------------------------------------------
# PRICING TIERS
# ---------------------------------------------------------------------------
@dataclass
class PricingTier:
    """Per-model pricing in USD per 1M tokens."""
    model_id: str
    display_name: str
    provider: str                         # "google" | "anthropic"
    tier: str                             # "free" | "paid"
    input_per_1m_usd: Decimal
    output_per_1m_usd: Decimal
    thinking_per_1m_usd: Decimal = Decimal("0")
    cached_per_1m_usd: Decimal = Decimal("0")
    description: str = ""


# Gemini 2.0 Flash  (paid lane default — replaces deprecated 2.5 Flash June 17 2026)
# Source: https://ai.google.dev/pricing (verify before shipping)
GEMINI_FLASH_PRICING = PricingTier(
    model_id="gemini-2.0-flash",
    display_name="Gemini Flash",
    provider="google",
    tier="paid",
    input_per_1m_usd=Decimal("0.10"),
    output_per_1m_usd=Decimal("0.40"),
    thinking_per_1m_usd=Decimal("0.40"),
    cached_per_1m_usd=Decimal("0.025"),
    description="Fast, capable — best for most documents",
)

# Gemini 2.0 Flash-Lite  (free lane — cheap enough to absorb ₹100 free credit)
GEMINI_FLASH_LITE_PRICING = PricingTier(
    model_id="gemini-2.0-flash-lite",
    display_name="Gemini Flash-Lite",
    provider="google",
    tier="free",
    input_per_1m_usd=Decimal("0.075"),
    output_per_1m_usd=Decimal("0.30"),
    thinking_per_1m_usd=Decimal("0"),
    cached_per_1m_usd=Decimal("0.01875"),
    description="Lightweight, fast — used for free-tier users",
)

# Claude Sonnet 4.6  (premium paid lane — best reasoning quality)
CLAUDE_SONNET_PRICING = PricingTier(
    model_id="claude-sonnet-4-6",
    display_name="Claude Sonnet 4.6",
    provider="anthropic",
    tier="paid",
    input_per_1m_usd=Decimal("3.00"),
    output_per_1m_usd=Decimal("15.00"),
    thinking_per_1m_usd=Decimal("0"),
    cached_per_1m_usd=Decimal("0"),
    description="Deep reasoning — best for complex regulatory documents",
)

# Claude Haiku 4.5  (paid lane — fast + affordable Anthropic option)
CLAUDE_HAIKU_PRICING = PricingTier(
    model_id="claude-haiku-4-5-20251001",
    display_name="Claude Haiku 4.5",
    provider="anthropic",
    tier="paid",
    input_per_1m_usd=Decimal("0.80"),
    output_per_1m_usd=Decimal("4.00"),
    thinking_per_1m_usd=Decimal("0"),
    cached_per_1m_usd=Decimal("0"),
    description="Fast Anthropic model — good balance of speed and quality",
)

# Legacy pricing kept for migration history only — NOT used for new requests
GEMINI_25_FLASH_PRICING = PricingTier(
    model_id="gemini-2.5-flash",
    display_name="Gemini 2.5 Flash (deprecated)",
    provider="google",
    tier="paid",
    input_per_1m_usd=Decimal("0.15"),
    output_per_1m_usd=Decimal("3.50"),
    thinking_per_1m_usd=Decimal("3.50"),
    cached_per_1m_usd=Decimal("0.0375"),
    description="DEPRECATED — use gemini-2.0-flash instead",
)

# Single source of truth for all supported model pricing
PRICING_REGISTRY: Dict[str, PricingTier] = {
    "gemini-2.0-flash": GEMINI_FLASH_PRICING,
    "gemini-2.0-flash-lite": GEMINI_FLASH_LITE_PRICING,
    "claude-sonnet-4-6": CLAUDE_SONNET_PRICING,
    "claude-haiku-4-5-20251001": CLAUDE_HAIKU_PRICING,
    # legacy — costs still calculable for historical records
    "gemini-2.5-flash": GEMINI_25_FLASH_PRICING,
    "gemini-1.5-flash": PricingTier(
        model_id="gemini-1.5-flash", display_name="Gemini 1.5 Flash (legacy)",
        provider="google", tier="paid",
        input_per_1m_usd=Decimal("0.075"), output_per_1m_usd=Decimal("0.30"),
        description="Legacy model",
    ),
}

# Metadata surfaced to the frontend model selector
SUPPORTED_MODELS = [
    {
        "model_id": "gemini-2.0-flash",
        "display_name": "Gemini Flash",
        "provider": "Google",
        "tier": "paid",
        "description": "Fast, capable — best for most documents",
        "cost_per_doc_estimate": "₹2–6",
    },
    {
        "model_id": "gemini-2.0-flash-lite",
        "display_name": "Gemini Flash-Lite",
        "provider": "Google",
        "tier": "free",
        "description": "Lightweight — used for free-tier analyses",
        "cost_per_doc_estimate": "₹1–3",
    },
    {
        "model_id": "claude-sonnet-4-6",
        "display_name": "Claude Sonnet 4.6",
        "provider": "Anthropic",
        "tier": "paid",
        "description": "Deep reasoning — best for complex regulatory documents",
        "cost_per_doc_estimate": "₹15–30",
    },
    {
        "model_id": "claude-haiku-4-5-20251001",
        "display_name": "Claude Haiku 4.5",
        "provider": "Anthropic",
        "tier": "paid",
        "description": "Fast Anthropic model — good balance of speed and quality",
        "cost_per_doc_estimate": "₹4–10",
    },
]


def get_pricing_for_model(model_id: str) -> PricingTier:
    """Return pricing tier for a model. Falls back to Gemini Flash if unknown."""
    pricing = PRICING_REGISTRY.get(model_id)
    if not pricing:
        logger.warning(f"Unknown model '{model_id}' — defaulting to gemini-2.0-flash pricing")
        return GEMINI_FLASH_PRICING
    return pricing


# ---------------------------------------------------------------------------
# COST BREAKDOWN DATACLASS
# ---------------------------------------------------------------------------
@dataclass
class CostBreakdown:
    """
    Full cost breakdown for a single AI call, with markup separated from raw cost.

    raw_cost_inr  = what Google/Anthropic charged us
    markup_inr    = our 15% platform fee
    total_cost_inr = raw + markup (what the customer pays)
    """
    model_id: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int = 0
    cached_tokens: int = 0

    # USD breakdown
    input_cost_usd: Decimal = Decimal("0")
    output_cost_usd: Decimal = Decimal("0")
    thinking_cost_usd: Decimal = Decimal("0")
    cached_cost_usd: Decimal = Decimal("0")
    raw_cost_usd: Decimal = Decimal("0")

    # INR breakdown
    input_cost_inr: Decimal = Decimal("0")
    output_cost_inr: Decimal = Decimal("0")
    thinking_cost_inr: Decimal = Decimal("0")
    raw_cost_inr: Decimal = Decimal("0")

    # Markup
    markup_percent: Decimal = MARKUP_PERCENT
    markup_inr: Decimal = Decimal("0")
    total_cost_inr: Decimal = Decimal("0")

    # Exchange rate used
    usd_to_inr: Decimal = Decimal("84.0")

    # Alias so callers that used the old API still work
    @property
    def cost_inr(self) -> float:
        return float(self.total_cost_inr)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise for API responses and usage_log extra_data."""
        return {
            "model_id": self.model_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "thinking_tokens": self.thinking_tokens,
            "cached_tokens": self.cached_tokens,
            "total_tokens": self.input_tokens + self.output_tokens + self.thinking_tokens,
            # USD
            "input_cost_usd": float(self.input_cost_usd),
            "output_cost_usd": float(self.output_cost_usd),
            "thinking_cost_usd": float(self.thinking_cost_usd),
            "raw_cost_usd": float(self.raw_cost_usd),
            # INR
            "input_cost_inr": float(self.input_cost_inr),
            "output_cost_inr": float(self.output_cost_inr),
            "thinking_cost_inr": float(self.thinking_cost_inr),
            "raw_cost_inr": float(self.raw_cost_inr),
            # Markup
            "markup_percent": float(self.markup_percent),
            "markup_inr": float(self.markup_inr),
            "total_cost_inr": float(self.total_cost_inr),
            "cost_inr": float(self.total_cost_inr),   # legacy compat
            "usd_to_inr": float(self.usd_to_inr),
        }

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Backward-compatible dict matching the old calculate_cost_from_actual_tokens() shape."""
        d = self.to_dict()
        # Old callers expected cost_inr = total (with markup already baked in)
        d["cost_usd"] = float(self.raw_cost_usd)
        return d


# ---------------------------------------------------------------------------
# COST SERVICE
# ---------------------------------------------------------------------------
class CostService:
    """
    Multi-model cost calculator with transparent 15% markup.

    Usage:
        breakdown = cost_service.calculate_cost_from_actual_tokens(
            input_tokens=5000, output_tokens=2000, model="gemini-2.0-flash"
        )
        # breakdown.raw_cost_inr   — what Google/Anthropic charged
        # breakdown.markup_inr     — our 15% fee
        # breakdown.total_cost_inr — what the customer pays
    """

    def __init__(self):
        try:
            import tiktoken
            self.encoder = tiktoken.encoding_for_model("gpt-4")
        except Exception:
            self.encoder = None

        self.usd_to_inr = Decimal("84.0")
        self.update_exchange_rate()

        # Default model for fallback (always Gemini Flash, never the free model)
        from app.core.config import settings
        self._default_model = settings.GEMINI_MODEL

        logger.info(
            f"CostService ready | default={self._default_model} | "
            f"markup={MARKUP_PERCENT}% | rate=₹{self.usd_to_inr}/USD"
        )

    # ------------------------------------------------------------------
    # Core calculation
    # ------------------------------------------------------------------
    def calculate_cost_from_actual_tokens(
        self,
        input_tokens: int,
        output_tokens: int,
        thinking_tokens: int = 0,
        cached_tokens: int = 0,
        model: Optional[str] = None,
    ) -> CostBreakdown:
        """
        Calculate cost for actual token counts returned by the AI API.

        Returns a CostBreakdown with raw cost and 15% markup separated.
        """
        model_id = model or self._default_model
        pricing = get_pricing_for_model(model_id)

        inp = Decimal(input_tokens)
        out = Decimal(output_tokens)
        thi = Decimal(thinking_tokens)
        cac = Decimal(cached_tokens)

        input_cost_usd = inp / 1_000_000 * pricing.input_per_1m_usd
        output_cost_usd = out / 1_000_000 * pricing.output_per_1m_usd
        thinking_cost_usd = thi / 1_000_000 * pricing.thinking_per_1m_usd
        cached_cost_usd = cac / 1_000_000 * pricing.cached_per_1m_usd
        raw_cost_usd = input_cost_usd + output_cost_usd + thinking_cost_usd + cached_cost_usd

        r = self.usd_to_inr
        input_cost_inr = input_cost_usd * r
        output_cost_inr = output_cost_usd * r
        thinking_cost_inr = thinking_cost_usd * r
        raw_cost_inr = raw_cost_usd * r

        markup_inr = (raw_cost_inr * MARKUP_PERCENT / 100).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        total_cost_inr = raw_cost_inr + markup_inr

        bd = CostBreakdown(
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
            cached_tokens=cached_tokens,
            input_cost_usd=input_cost_usd,
            output_cost_usd=output_cost_usd,
            thinking_cost_usd=thinking_cost_usd,
            cached_cost_usd=cached_cost_usd,
            raw_cost_usd=raw_cost_usd,
            input_cost_inr=input_cost_inr,
            output_cost_inr=output_cost_inr,
            thinking_cost_inr=thinking_cost_inr,
            raw_cost_inr=raw_cost_inr,
            markup_percent=MARKUP_PERCENT,
            markup_inr=markup_inr,
            total_cost_inr=total_cost_inr,
            usd_to_inr=self.usd_to_inr,
        )

        logger.info(
            f"💰 COST | {model_id} | in={input_tokens} out={output_tokens} "
            f"think={thinking_tokens} | raw=₹{float(raw_cost_inr):.4f} "
            f"markup=₹{float(markup_inr):.4f} total=₹{float(total_cost_inr):.4f}"
        )
        return bd

    def calculate_cost(self, input_text: str, output_text: str, model: Optional[str] = None) -> CostBreakdown:
        """Estimate cost from raw text (tokenises internally)."""
        input_tokens = self.count_tokens(input_text)
        output_tokens = self.count_tokens(output_text)
        return self.calculate_cost_from_actual_tokens(input_tokens, output_tokens, model=model)

    def estimate_document_cost(
        self, doc_size_kb: float, passes: int = 3, model: Optional[str] = None
    ) -> CostBreakdown:
        """Quick estimate for a document before analysis starts (cost-preview modal)."""
        doc_tokens = int(doc_size_kb * 1000 * 0.25)
        input_per_pass = doc_tokens + 500
        output_per_pass = int(doc_tokens * 0.3)
        return self.calculate_cost_from_actual_tokens(
            input_tokens=input_per_pass * passes,
            output_tokens=output_per_pass * passes,
            thinking_tokens=int(output_per_pass * passes * 0.5),  # conservative thinking estimate
            model=model,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if self.encoder:
            try:
                return len(self.encoder.encode(text))
            except Exception:
                pass
        return len(text) // 4

    def update_exchange_rate(self) -> bool:
        try:
            response = httpx.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5.0)
            if response.status_code == 200:
                rate = Decimal(str(response.json()["rates"]["INR"]))
                self.usd_to_inr = rate
                logger.info(f"Exchange rate updated: ₹{rate}/USD")
                return True
        except Exception as e:
            logger.warning(f"Exchange rate fetch failed — using ₹{self.usd_to_inr}/USD fallback: {e}")
        return False

    def get_pricing_info(self) -> Dict[str, Any]:
        """Full pricing table for the billing/transparency dashboard."""
        return {
            "markup_percent": float(MARKUP_PERCENT),
            "usd_to_inr": float(self.usd_to_inr),
            "models": [
                {
                    **m,
                    "rates": {
                        "input_per_1m_usd": float(get_pricing_for_model(m["model_id"]).input_per_1m_usd),
                        "output_per_1m_usd": float(get_pricing_for_model(m["model_id"]).output_per_1m_usd),
                        "input_per_1m_inr": float(
                            get_pricing_for_model(m["model_id"]).input_per_1m_usd * self.usd_to_inr
                        ),
                        "output_per_1m_inr": float(
                            get_pricing_for_model(m["model_id"]).output_per_1m_usd * self.usd_to_inr
                        ),
                    },
                }
                for m in SUPPORTED_MODELS
            ],
        }


# Global singleton
cost_service = CostService()
