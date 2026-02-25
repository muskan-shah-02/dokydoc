"""
ProviderRouter — Dual-Provider AI Routing (ADHOC-08)

Routes AI calls to the appropriate provider based on the task type:

  AI_PROVIDER_MODE="gemini" (default):
    - ALL tasks → Gemini (current behavior, no change)

  AI_PROVIDER_MODE="dual":
    - Code analysis → Claude (better at understanding codebases)
    - Document analysis → Gemini (better at structured data extraction)
    - Vision → Gemini (Claude doesn't have vision in this integration)

The router presents a unified interface so callers don't need to know
which provider they're using. If Claude is unavailable, falls back to Gemini.
"""

from typing import Dict, Optional
from app.core.config import settings
from app.core.logging import LoggerMixin


class ProviderRouter(LoggerMixin):
    """
    Routes AI calls to the correct provider based on configuration
    and task type. Provides automatic fallback to Gemini.
    """

    def __init__(self):
        super().__init__()
        self.mode = settings.AI_PROVIDER_MODE  # "gemini" or "dual"

        # Lazy import to avoid circular imports at module load time
        self._gemini = None
        self._claude = None

        self.logger.info(f"ProviderRouter initialized | mode={self.mode}")

    @property
    def gemini(self):
        if self._gemini is None:
            from app.services.ai.gemini import gemini_service
            self._gemini = gemini_service
        return self._gemini

    @property
    def claude(self):
        if self._claude is None:
            from app.services.ai.anthropic import anthropic_service
            self._claude = anthropic_service
        return self._claude

    @property
    def claude_available(self) -> bool:
        return self.claude is not None and self.claude.available

    @property
    def dual_mode(self) -> bool:
        return self.mode == "dual" and self.claude_available

    def get_provider_info(self) -> Dict:
        """Return current provider configuration for diagnostics."""
        return {
            "mode": self.mode,
            "gemini_available": self.gemini is not None,
            "claude_available": self.claude_available,
            "effective_mode": "dual" if self.dual_mode else "gemini",
            "code_provider": "claude" if self.dual_mode else "gemini",
            "document_provider": "gemini",
        }

    # ================================================================
    # CODE ANALYSIS ROUTING
    # ================================================================

    async def analyze_code(
        self, code_content: str, tenant_id: int = None, user_id: int = None,
    ) -> dict:
        """
        Route basic code analysis to the appropriate provider.
        Dual mode: Claude. Single mode: Gemini. Fallback: Gemini.
        """
        if self.dual_mode:
            try:
                self.logger.info("Routing code analysis → Claude")
                return await self.claude.call_claude_for_code_analysis(code_content)
            except Exception as e:
                self.logger.warning(f"Claude code analysis failed, falling back to Gemini: {e}")

        self.logger.info("Routing code analysis → Gemini")
        return await self.gemini.call_gemini_for_code_analysis(
            code_content, tenant_id=tenant_id, user_id=user_id,
        )

    async def analyze_code_enhanced(
        self, code_content: str, repo_name: str = "", file_path: str = "", language: str = "",
        tenant_id: int = None, user_id: int = None,
    ) -> dict:
        """
        Route enhanced semantic code analysis to the appropriate provider.
        Dual mode: Claude. Single mode: Gemini. Fallback: Gemini.
        """
        if self.dual_mode:
            try:
                self.logger.info(f"Routing enhanced analysis → Claude ({file_path})")
                return await self.claude.call_claude_for_enhanced_analysis(
                    code_content, repo_name, file_path, language
                )
            except Exception as e:
                self.logger.warning(f"Claude enhanced analysis failed, falling back to Gemini: {e}")

        self.logger.info(f"Routing enhanced analysis → Gemini ({file_path})")
        return await self.gemini.call_gemini_for_enhanced_analysis(
            code_content, repo_name, file_path, language,
            tenant_id=tenant_id, user_id=user_id,
        )

    async def analyze_delta(
        self, file_path: str, previous_analysis: dict, current_analysis: dict,
        tenant_id: int = None, user_id: int = None,
    ) -> dict:
        """
        Route delta analysis to the appropriate provider.
        Dual mode: Claude. Single mode: Gemini. Fallback: Gemini.
        """
        if self.dual_mode:
            try:
                self.logger.info(f"Routing delta analysis → Claude ({file_path})")
                return await self.claude.call_claude_for_delta_analysis(
                    file_path, previous_analysis, current_analysis
                )
            except Exception as e:
                self.logger.warning(f"Claude delta analysis failed, falling back to Gemini: {e}")

        self.logger.info(f"Routing delta analysis → Gemini ({file_path})")
        return await self.gemini.call_gemini_for_delta_analysis(
            file_path, previous_analysis, current_analysis,
            tenant_id=tenant_id, user_id=user_id,
        )

    # ================================================================
    # DOCUMENT ANALYSIS — ALWAYS GEMINI
    # ================================================================

    async def generate_content(self, prompt: str, **kwargs):
        """
        General-purpose content generation — always Gemini.
        Document analysis, composition, segmentation, extraction all use this.
        """
        return await self.gemini.generate_content(prompt, **kwargs)

    async def generate_content_with_vision(self, prompt: str, image, **kwargs):
        """Vision analysis — always Gemini (Claude vision not integrated)."""
        return await self.gemini.generate_content_with_vision(prompt, image, **kwargs)

    # ================================================================
    # COST TRACKING HELPERS
    # ================================================================

    def calculate_claude_cost(self, input_tokens: int, output_tokens: int) -> Dict:
        """
        Calculate Claude API cost.

        Claude Sonnet 4.5 pricing (per 1M tokens):
          Input:  $3.00
          Output: $15.00
        """
        from decimal import Decimal

        input_cost_usd = Decimal(input_tokens) / 1_000_000 * Decimal("3.00")
        output_cost_usd = Decimal(output_tokens) / 1_000_000 * Decimal("15.00")
        total_usd = input_cost_usd + output_cost_usd

        # Use same exchange rate as cost_service
        try:
            from app.services.cost_service import cost_service
            usd_to_inr = cost_service.usd_to_inr
        except Exception:
            usd_to_inr = Decimal("84.0")

        total_inr = float(total_usd * usd_to_inr)

        return {
            "provider": "claude",
            "model": settings.ANTHROPIC_MODEL,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": float(total_usd),
            "cost_inr": total_inr,
        }


# Global instance
provider_router = ProviderRouter()
