"""
AI Service Providers — Sprint 4 ADHOC-07/08

Exports:
  - gemini_service: Google Gemini (documents + fallback code analysis)
  - anthropic_service: Anthropic Claude (code analysis in dual mode)
  - provider_router: Unified AI routing interface
"""

from app.services.ai.gemini import gemini_service
from app.services.ai.provider_router import provider_router

__all__ = ["gemini_service", "provider_router"]
