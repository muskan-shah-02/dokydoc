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

    Pricing (Gemini 2.5 Flash - as of Jan 2025):
    - Input: $0.00001875 per 1K tokens
    - Output: $0.000075 per 1K tokens
    - USD to INR: ~84.0 (fetched from API in production)
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

        # Gemini 2.5 Flash pricing (USD per 1000 tokens)
        self.cost_per_1k_input_usd = Decimal("0.00001875")
        self.cost_per_1k_output_usd = Decimal("0.000075")

        # CONFIG-01 FIX: Exchange rate (USD to INR) with automatic updates
        self.usd_to_inr = Decimal("84.0")  # Fallback if API fetch fails

        # CONFIG-01 FIX: Try to fetch latest exchange rate on initialization
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

        logger.debug(
            f"Cost calculation: {input_tokens} input + {output_tokens} output tokens "
            f"= ${total_cost_usd:.6f} = ₹{cost_inr:.4f}"
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
