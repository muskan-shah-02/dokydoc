"""
Cost calculation service for tracking AI API usage and billing.
Provides accurate token counting and cost estimation in INR.
"""
import tiktoken
from typing import Dict, Tuple
from decimal import Decimal

from app.core.logging import get_logger

logger = get_logger("cost_service")


class CostService:
    """
    Service for calculating AI API costs based on token usage.

    Pricing (Gemini 1.5 Flash - CORRECTED Feb 2025):
    IMPORTANT: These must match Google's official pricing!
    https://ai.google.dev/pricing

    Under 128K context window:
    - Input:  $0.075 per 1M tokens  = $0.000075 per 1K tokens
    - Output: $0.30 per 1M tokens   = $0.0003 per 1K tokens

    Over 128K context window:
    - Input:  $0.15 per 1M tokens
    - Output: $0.60 per 1M tokens

    USD to INR: ~84.0 (auto-updated from API)
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

        # CORRECTED: Gemini 1.5 Flash pricing (USD per 1000 tokens)
        # Under 128K context - this is what we use for document analysis
        self.cost_per_1k_input_usd = Decimal("0.000075")   # $0.075 per 1M tokens
        self.cost_per_1k_output_usd = Decimal("0.0003")    # $0.30 per 1M tokens

        # Exchange rate (USD to INR) with automatic updates
        self.usd_to_inr = Decimal("84.0")  # Fallback if API fetch fails

        # Try to fetch latest exchange rate on initialization
        if not self.update_exchange_rate():
            logger.warning(
                f"⚠️ Using fallback exchange rate: $1 = ₹{self.usd_to_inr}. "
                f"Automatic updates will retry later."
            )

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
    ) -> Dict[str, any]:
        """
        Calculate AI API cost for input/output text.

        Args:
            input_text: Prompt/input text sent to AI
            output_text: Response text received from AI

        Returns:
            Dict with:
                - input_tokens: int
                - output_tokens: int
                - cost_usd: Decimal
                - cost_inr: Decimal (float for DB compatibility)
        """
        input_tokens = self.count_tokens(input_text)
        output_tokens = self.count_tokens(output_text)

        # Calculate cost in USD
        input_cost_usd = (Decimal(input_tokens) / 1000) * self.cost_per_1k_input_usd
        output_cost_usd = (Decimal(output_tokens) / 1000) * self.cost_per_1k_output_usd
        total_cost_usd = input_cost_usd + output_cost_usd

        # Convert to INR
        cost_inr = float(total_cost_usd * self.usd_to_inr)

        logger.info(
            f"💰 Cost calculation: {input_tokens:,} input + {output_tokens:,} output = {input_tokens + output_tokens:,} total tokens | "
            f"${float(total_cost_usd):.6f} USD = ₹{cost_inr:.4f} INR"
        )

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": float(total_cost_usd),
            "cost_inr": cost_inr
        }

    def calculate_cost_from_actual_tokens(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, any]:
        """
        Calculate cost using actual token counts from Gemini API response.

        Use this when you have actual token counts from response.usage_metadata
        instead of estimating with tiktoken.

        Args:
            input_tokens: Actual prompt_token_count from Gemini
            output_tokens: Actual candidates_token_count from Gemini

        Returns:
            Dict with cost breakdown
        """
        # Calculate cost in USD using actual tokens
        input_cost_usd = (Decimal(input_tokens) / 1000) * self.cost_per_1k_input_usd
        output_cost_usd = (Decimal(output_tokens) / 1000) * self.cost_per_1k_output_usd
        total_cost_usd = input_cost_usd + output_cost_usd

        # Convert to INR
        cost_inr = float(total_cost_usd * self.usd_to_inr)

        logger.info(
            f"💰 ACTUAL TOKEN COST: {input_tokens:,} input + {output_tokens:,} output = {input_tokens + output_tokens:,} total | "
            f"${float(total_cost_usd):.6f} USD = ₹{cost_inr:.4f} INR"
        )

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": float(total_cost_usd),
            "cost_inr": cost_inr
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
                logger.info(f"✅ Exchange rate updated: ${1} = ₹{new_rate} (was ₹{old_rate})")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to update exchange rate: {e}")

        return False


# Global instance
cost_service = CostService()
