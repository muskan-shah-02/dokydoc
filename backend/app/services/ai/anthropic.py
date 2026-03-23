"""
AnthropicService — Claude API Integration (ADHOC-07)

Mirrors the GeminiService pattern but uses Anthropic's Claude API.
Designed for CODE ANALYSIS where Claude excels at understanding
entire codebases, architectural patterns, and complex logic.

Provider routing (ADHOC-08) determines when this service is used:
  - AI_PROVIDER_MODE="dual"  → Claude for code, Gemini for docs
  - AI_PROVIDER_MODE="gemini" → Gemini for everything (default)

Cost: Claude Sonnet 4.5 pricing (per 1M tokens):
  - Input:  $3.00
  - Output: $15.00
"""

import json
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import LoggerMixin
from app.services.ai.prompt_manager import prompt_manager, PromptType


class AnthropicService(LoggerMixin):
    """
    Service for interacting with Anthropic's Claude API.
    Provides code analysis capabilities with retry logic and cost tracking.
    """

    def __init__(self):
        super().__init__()

        if not settings.ANTHROPIC_API_KEY:
            self.logger.warning(
                "ANTHROPIC_API_KEY not configured. "
                "AnthropicService will be unavailable. Set it in .env to enable Claude."
            )
            self.client = None
            self.available = False
            return

        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            self.model = settings.ANTHROPIC_MODEL
            self.max_tokens = settings.ANTHROPIC_MAX_TOKENS
            self.available = True
            self.logger.info(
                f"AnthropicService initialized | model={self.model} | max_tokens={self.max_tokens}"
            )
        except ImportError:
            self.logger.warning(
                "anthropic package not installed. Run: pip install anthropic"
            )
            self.client = None
            self.available = False
        except Exception as e:
            self.logger.error(f"Failed to initialize AnthropicService: {e}")
            self.client = None
            self.available = False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def generate_content(self, prompt: str, system: str = None) -> Dict[str, Any]:
        """
        Generate content using Claude API.

        Returns a dict with:
          - text: The response text
          - input_tokens: Number of input tokens consumed
          - output_tokens: Number of output tokens consumed
        """
        if not self.available:
            raise RuntimeError("AnthropicService not available (missing API key or anthropic package)")

        prompt_length = len(prompt)
        self.logger.info(f"CLAUDE API CALL - Prompt length: {prompt_length} chars")

        messages = [{"role": "user", "content": prompt}]

        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        try:
            response = self.client.messages.create(**kwargs)

            response_text = response.content[0].text if response.content else ""
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            self.logger.info(
                f"CLAUDE API SUCCESS - Response: {len(response_text)} chars | "
                f"Tokens: {input_tokens} input + {output_tokens} output = "
                f"{input_tokens + output_tokens} total"
            )

            return {
                "text": response_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

        except Exception as e:
            self.logger.error(f"CLAUDE API ERROR: {e}")
            raise

    async def call_claude_for_code_analysis(self, code_content: str) -> dict:
        """
        Analyze code using Claude — universal adaptive prompt.
        Same interface as GeminiService.call_gemini_for_code_analysis().
        """
        prompt = prompt_manager.get_prompt(PromptType.CODE_ANALYSIS)
        full_prompt = f"{prompt}\n\nCODE TO ANALYZE:\n{code_content}"

        result = await self.generate_content(full_prompt)
        return self._parse_json_response(result["text"], "code analysis")

    async def call_claude_for_enhanced_analysis(
        self, code_content: str, repo_name: str = "", file_path: str = "", language: str = ""
    ) -> dict:
        """
        Enhanced semantic analysis using Claude.
        Same interface as GeminiService.call_gemini_for_enhanced_analysis().
        """
        language_guidance = prompt_manager.get_language_guidance(language)

        prompt = prompt_manager.get_prompt(
            PromptType.ENHANCED_SEMANTIC_ANALYSIS,
            repo_name=repo_name or "unknown",
            file_path=file_path or "unknown",
            language=language or "auto-detect",
            language_specific_guidance=language_guidance,
        )

        full_prompt = f"{prompt}\n{code_content}"

        result = await self.generate_content(
            full_prompt,
            system="You are an expert software architect. Analyze code precisely and return valid JSON."
        )
        return self._parse_json_response(result["text"], f"enhanced analysis for {file_path}")

    async def call_claude_for_delta_analysis(
        self, file_path: str, previous_analysis: dict, current_analysis: dict
    ) -> dict:
        """
        Delta analysis using Claude.
        Same interface as GeminiService.call_gemini_for_delta_analysis().
        """
        prompt = prompt_manager.get_prompt(
            PromptType.DELTA_ANALYSIS,
            file_path=file_path,
            previous_analysis=json.dumps(previous_analysis, indent=2),
            current_analysis=json.dumps(current_analysis, indent=2),
        )

        result = await self.generate_content(prompt)
        return self._parse_json_response(result["text"], f"delta analysis for {file_path}")

    def _parse_json_response(self, text: str, context: str = "") -> dict:
        """Parse JSON from Claude response with cleanup fallback."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            cleaned = text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse Claude JSON for {context}: {e}")
                return {
                    "summary": f"Analysis completed but JSON parsing failed ({context})",
                    "structured_analysis": {
                        "language_info": {"primary_language": "Unknown", "framework": "Unknown", "file_type": "Unknown"},
                        "components": [],
                        "dependencies": [],
                        "exports": [],
                        "patterns_and_architecture": {"design_patterns": [], "architectural_style": "Unknown", "key_concepts": []},
                        "quality_assessment": "Parse error",
                        "business_rules": [],
                        "api_contracts": [],
                        "data_model_relationships": [],
                        "security_patterns": [],
                    },
                }


# Global instance — safe to create even without API key (will be unavailable)
anthropic_service = AnthropicService()
