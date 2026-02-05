"""
Cost calculation service for tracking AI API usage and billing.
Provides accurate token counting and cost estimation in INR.

PRICING TRANSPARENCY: All formulas and rates are exposed via get_pricing_info()
for display on billing dashboards.
"""
import tiktoken
from typing import Dict, Any
from decimal import Decimal
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger("cost_service")


@dataclass
class PricingTier:
    """Pricing information for a specific model/tier."""
    model: str
    input_per_1m_usd: Decimal
    output_per_1m_usd: Decimal
    cached_per_1m_usd: Decimal  # Context caching discount
    search_per_1k_usd: Decimal  # Grounding with Google Search
    description: str


# ============================================================================
# GEMINI 2.5 FLASH PRICING (2026)
# Source: Google AI Pricing Page
# Last Updated: February 2026
#
# CRITICAL: These values MUST match Google's official pricing!
# ============================================================================

GEMINI_25_FLASH_PRICING = PricingTier(
    model="gemini-2.5-flash",
    input_per_1m_usd=Decimal("0.30"),      # $0.30 per 1M input tokens
    output_per_1m_usd=Decimal("2.50"),     # $2.50 per 1M output tokens (⚠️ HIGH!)
    cached_per_1m_usd=Decimal("0.03"),     # $0.03 per 1M cached tokens (90% discount)
    search_per_1k_usd=Decimal("14.00"),    # $14.00 per 1K search queries
    description="Gemini 2.5 Flash - Fast, cost-effective for document analysis"
)

# For reference: older model pricing
GEMINI_15_FLASH_PRICING = PricingTier(
    model="gemini-1.5-flash",
    input_per_1m_usd=Decimal("0.075"),
    output_per_1m_usd=Decimal("0.30"),
    cached_per_1m_usd=Decimal("0.01875"),
    search_per_1k_usd=Decimal("14.00"),
    description="Gemini 1.5 Flash - Legacy model"
)


class CostService:
    """
    Service for calculating AI API costs based on token usage.

    ═══════════════════════════════════════════════════════════════════════════
    GEMINI 2.5 FLASH PRICING (February 2026)
    ═══════════════════════════════════════════════════════════════════════════

    ┌─────────────────────┬────────────────────┬─────────────────────────────┐
    │ Factor              │ Price (USD)        │ Notes                       │
    ├─────────────────────┼────────────────────┼─────────────────────────────┤
    │ Input Tokens        │ $0.30 / 1M tokens  │ Prompts, documents, context │
    │ Output Tokens       │ $2.50 / 1M tokens  │ ⚠️ THE EXPENSIVE ONE!       │
    │ Cached Tokens       │ $0.03 / 1M tokens  │ 90% discount if cached      │
    │ Search Queries      │ $14.00 / 1K queries│ Grounding with Google Search│
    └─────────────────────┴────────────────────┴─────────────────────────────┘

    FORMULA:
    ────────
    cost_usd = (input_tokens / 1,000,000 × $0.30) + (output_tokens / 1,000,000 × $2.50)
    cost_inr = cost_usd × exchange_rate

    ═══════════════════════════════════════════════════════════════════════════
    """

    def __init__(self):
        """Initialize cost service with tokenizer and exchange rates."""
        try:
            # Use GPT-4 tokenizer as proxy for Gemini (similar tokenization)
            self.encoder = tiktoken.encoding_for_model("gpt-4")
            logger.info("✅ Cost service initialized with tiktoken")
        except Exception as e:
            logger.error(f"❌ Failed to initialize tokenizer: {e}")
            self.encoder = None

        # Active pricing tier
        self.pricing = GEMINI_25_FLASH_PRICING

        # Convert to per-1K for calculation convenience
        self.cost_per_1k_input_usd = self.pricing.input_per_1m_usd / 1000   # $0.0003 per 1K
        self.cost_per_1k_output_usd = self.pricing.output_per_1m_usd / 1000  # $0.0025 per 1K
        self.cost_per_1k_cached_usd = self.pricing.cached_per_1m_usd / 1000  # $0.00003 per 1K

        # Exchange rate (USD to INR) with automatic updates
        self.usd_to_inr = Decimal("84.0")  # Fallback if API fetch fails

        # Try to fetch latest exchange rate on initialization
        if not self.update_exchange_rate():
            logger.warning(
                f"⚠️ Using fallback exchange rate: $1 = ₹{self.usd_to_inr}. "
                f"Automatic updates will retry later."
            )

        logger.info(
            f"💰 Cost Service Active | Model: {self.pricing.model} | "
            f"Input: ${self.pricing.input_per_1m_usd}/1M | "
            f"Output: ${self.pricing.output_per_1m_usd}/1M | "
            f"Exchange: ₹{self.usd_to_inr}/USD"
        )

    def get_pricing_info(self) -> Dict[str, Any]:
        """
        Get complete pricing information for display on billing dashboards.

        Returns all pricing factors, formulas, and current rates for
        complete transparency to users.
        """
        return {
            "model": self.pricing.model,
            "model_description": self.pricing.description,
            "last_updated": "February 2026",
            "source": "Google AI Pricing (ai.google.dev/pricing)",

            # Pricing rates in USD
            "rates_usd": {
                "input_per_1m_tokens": float(self.pricing.input_per_1m_usd),
                "output_per_1m_tokens": float(self.pricing.output_per_1m_usd),
                "cached_per_1m_tokens": float(self.pricing.cached_per_1m_usd),
                "search_per_1k_queries": float(self.pricing.search_per_1k_usd),
            },

            # Pricing rates in INR (converted)
            "rates_inr": {
                "input_per_1m_tokens": float(self.pricing.input_per_1m_usd * self.usd_to_inr),
                "output_per_1m_tokens": float(self.pricing.output_per_1m_usd * self.usd_to_inr),
                "cached_per_1m_tokens": float(self.pricing.cached_per_1m_usd * self.usd_to_inr),
                "search_per_1k_queries": float(self.pricing.search_per_1k_usd * self.usd_to_inr),
            },

            # Exchange rate
            "exchange_rate": {
                "usd_to_inr": float(self.usd_to_inr),
                "source": "exchangerate-api.com",
            },

            # The formula (for transparency)
            "formula": {
                "cost_usd": "(input_tokens / 1,000,000 × input_rate) + (output_tokens / 1,000,000 × output_rate)",
                "cost_inr": "cost_usd × exchange_rate",
                "example": {
                    "input_tokens": 10000,
                    "output_tokens": 5000,
                    "input_cost_usd": float(Decimal("10000") / 1000000 * self.pricing.input_per_1m_usd),
                    "output_cost_usd": float(Decimal("5000") / 1000000 * self.pricing.output_per_1m_usd),
                    "total_usd": float(
                        (Decimal("10000") / 1000000 * self.pricing.input_per_1m_usd) +
                        (Decimal("5000") / 1000000 * self.pricing.output_per_1m_usd)
                    ),
                    "total_inr": float(
                        ((Decimal("10000") / 1000000 * self.pricing.input_per_1m_usd) +
                         (Decimal("5000") / 1000000 * self.pricing.output_per_1m_usd)) * self.usd_to_inr
                    ),
                }
            },

            # Cost breakdown explanation
            "cost_factors": [
                {
                    "factor": "Input Tokens",
                    "rate_usd": f"${self.pricing.input_per_1m_usd} per 1M tokens",
                    "rate_inr": f"₹{float(self.pricing.input_per_1m_usd * self.usd_to_inr):.2f} per 1M tokens",
                    "description": "Tokens sent TO the AI (prompts, documents, context)",
                    "typical_usage": "Document text, system prompts, analysis instructions"
                },
                {
                    "factor": "Output Tokens",
                    "rate_usd": f"${self.pricing.output_per_1m_usd} per 1M tokens",
                    "rate_inr": f"₹{float(self.pricing.output_per_1m_usd * self.usd_to_inr):.2f} per 1M tokens",
                    "description": "Tokens received FROM the AI (⚠️ Most expensive!)",
                    "typical_usage": "JSON analysis results, extracted data, summaries",
                    "warning": "Output tokens cost 8.3x more than input tokens!"
                },
                {
                    "factor": "Cached Tokens",
                    "rate_usd": f"${self.pricing.cached_per_1m_usd} per 1M tokens",
                    "rate_inr": f"₹{float(self.pricing.cached_per_1m_usd * self.usd_to_inr):.2f} per 1M tokens",
                    "description": "90% discount when using context caching",
                    "typical_usage": "Repeated analysis of similar documents"
                },
                {
                    "factor": "Search Queries",
                    "rate_usd": f"${self.pricing.search_per_1k_usd} per 1K queries",
                    "rate_inr": f"₹{float(self.pricing.search_per_1k_usd * self.usd_to_inr):.2f} per 1K queries",
                    "description": "Grounding with Google Search (if enabled)",
                    "typical_usage": "Not currently used in document analysis"
                }
            ]
        }

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: Text to tokenize

        Returns:
            Token count (or estimated count if tokenizer unavailable)
        """
        if not text:
            return 0

        if self.encoder:
            try:
                return len(self.encoder.encode(text))
            except Exception as e:
                logger.error(f"Token counting error: {e}")

        # Fallback: rough estimate (4 chars ≈ 1 token)
        return len(text) // 4

    def calculate_cost(
        self,
        input_text: str,
        output_text: str
    ) -> Dict[str, Any]:
        """
        Calculate AI API cost for input/output text.

        Args:
            input_text: Prompt/input text sent to AI
            output_text: Response text received from AI

        Returns:
            Dict with complete cost breakdown
        """
        input_tokens = self.count_tokens(input_text)
        output_tokens = self.count_tokens(output_text)

        return self.calculate_cost_from_actual_tokens(input_tokens, output_tokens)

    def calculate_cost_from_actual_tokens(
        self,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        search_queries: int = 0
    ) -> Dict[str, Any]:
        """
        Calculate cost using actual token counts from Gemini API response.

        Use this when you have actual token counts from response.usage_metadata.

        Args:
            input_tokens: Actual prompt_token_count from Gemini
            output_tokens: Actual candidates_token_count from Gemini
            cached_tokens: Tokens served from cache (optional)
            search_queries: Number of search queries (optional)

        Returns:
            Dict with complete cost breakdown for transparency
        """
        # Calculate individual costs in USD
        input_cost_usd = (Decimal(input_tokens) / 1000) * self.cost_per_1k_input_usd
        output_cost_usd = (Decimal(output_tokens) / 1000) * self.cost_per_1k_output_usd
        cached_cost_usd = (Decimal(cached_tokens) / 1000) * self.cost_per_1k_cached_usd
        search_cost_usd = (Decimal(search_queries) / 1000) * self.pricing.search_per_1k_usd

        total_cost_usd = input_cost_usd + output_cost_usd + cached_cost_usd + search_cost_usd

        # Convert to INR
        input_cost_inr = float(input_cost_usd * self.usd_to_inr)
        output_cost_inr = float(output_cost_usd * self.usd_to_inr)
        cached_cost_inr = float(cached_cost_usd * self.usd_to_inr)
        search_cost_inr = float(search_cost_usd * self.usd_to_inr)
        total_cost_inr = float(total_cost_usd * self.usd_to_inr)

        logger.info(
            f"💰 COST CALCULATION | Model: {self.pricing.model}\n"
            f"   📥 Input:  {input_tokens:,} tokens × ${self.pricing.input_per_1m_usd}/1M = ${float(input_cost_usd):.6f} (₹{input_cost_inr:.4f})\n"
            f"   📤 Output: {output_tokens:,} tokens × ${self.pricing.output_per_1m_usd}/1M = ${float(output_cost_usd):.6f} (₹{output_cost_inr:.4f})\n"
            f"   💵 TOTAL:  ${float(total_cost_usd):.6f} USD = ₹{total_cost_inr:.4f} INR"
        )

        return {
            # Token counts
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_tokens": cached_tokens,
            "search_queries": search_queries,
            "total_tokens": input_tokens + output_tokens,

            # Cost breakdown in USD
            "input_cost_usd": float(input_cost_usd),
            "output_cost_usd": float(output_cost_usd),
            "cached_cost_usd": float(cached_cost_usd),
            "search_cost_usd": float(search_cost_usd),
            "cost_usd": float(total_cost_usd),

            # Cost breakdown in INR
            "input_cost_inr": input_cost_inr,
            "output_cost_inr": output_cost_inr,
            "cached_cost_inr": cached_cost_inr,
            "search_cost_inr": search_cost_inr,
            "cost_inr": total_cost_inr,

            # Rates used (for audit trail)
            "rates_applied": {
                "model": self.pricing.model,
                "input_per_1m_usd": float(self.pricing.input_per_1m_usd),
                "output_per_1m_usd": float(self.pricing.output_per_1m_usd),
                "usd_to_inr": float(self.usd_to_inr),
            },

            # Human-readable breakdown
            "breakdown_human": {
                "input": f"{input_tokens:,} tokens @ ${self.pricing.input_per_1m_usd}/1M = ₹{input_cost_inr:.4f}",
                "output": f"{output_tokens:,} tokens @ ${self.pricing.output_per_1m_usd}/1M = ₹{output_cost_inr:.4f}",
                "total": f"₹{total_cost_inr:.4f} INR (${float(total_cost_usd):.6f} USD)"
            }
        }

    def estimate_cost(self, text_length: int, is_input: bool = True) -> float:
        """
        Estimate cost for text without tokenizing (faster).

        Args:
            text_length: Character count
            is_input: True if input text, False if output text

        Returns:
            Estimated cost in INR
        """
        # Rough estimate: 4 chars ≈ 1 token
        estimated_tokens = text_length // 4

        if is_input:
            cost_usd = (Decimal(estimated_tokens) / 1000) * self.cost_per_1k_input_usd
        else:
            cost_usd = (Decimal(estimated_tokens) / 1000) * self.cost_per_1k_output_usd

        return float(cost_usd * self.usd_to_inr)

    def estimate_document_cost(self, doc_size_kb: float, passes: int = 3) -> Dict[str, Any]:
        """
        Estimate total cost for analyzing a document.

        Args:
            doc_size_kb: Document size in KB
            passes: Number of analysis passes (default: 3)

        Returns:
            Cost estimate with breakdown
        """
        # Rough estimates based on typical document analysis
        chars_per_kb = 1000
        tokens_per_char = 0.25  # 4 chars ≈ 1 token

        doc_tokens = int(doc_size_kb * chars_per_kb * tokens_per_char)

        # Typical input/output ratio per pass
        input_per_pass = doc_tokens + 500  # Document + prompt overhead
        output_per_pass = int(doc_tokens * 0.3)  # ~30% of doc size as output

        total_input = input_per_pass * passes
        total_output = output_per_pass * passes

        estimate = self.calculate_cost_from_actual_tokens(total_input, total_output)
        estimate["estimate_params"] = {
            "doc_size_kb": doc_size_kb,
            "passes": passes,
            "doc_tokens": doc_tokens,
            "input_per_pass": input_per_pass,
            "output_per_pass": output_per_pass,
        }

        return estimate

    def update_exchange_rate(self) -> bool:
        """
        Update USD to INR exchange rate from API.

        Returns:
            True if updated successfully
        """
        try:
            import httpx
            response = httpx.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                new_rate = Decimal(str(data["rates"]["INR"]))
                old_rate = self.usd_to_inr
                self.usd_to_inr = new_rate
                logger.info(f"✅ Exchange rate updated: $1 = ₹{new_rate} (was ₹{old_rate})")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to update exchange rate: {e}")

        return False


# Global instance
cost_service = CostService()
