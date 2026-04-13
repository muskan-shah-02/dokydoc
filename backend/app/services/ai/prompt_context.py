"""
PromptContext — Industry-Aware Prompt Injection (Phase 5)

Purpose
-------
Every Gemini call for a tenant now optionally carries a PromptContext that
prepends tenant-specific knowledge to the prompt:
  - Industry vocabulary (so AI understands domain terms correctly)
  - Applicable regulations (so AI flags compliance gaps)
  - Tenant glossary (custom overrides confirmed by the tenant's team)
  - Few-shot examples (tenant-contributed validation examples)
  - Verbatim prompt_injection preamble from the industry library

This context is built once per Gemini call using PromptContextBuilder and is
completely non-breaking — if context is absent or build fails, the caller
falls back to context-free prompts exactly as before Phase 5.

Usage
-----
    # In any Gemini method:
    from app.services.ai.prompt_context import build_prompt_context

    ctx = build_prompt_context(db, tenant_id=tenant_id)
    if not ctx.is_empty:
        prompt = ctx.render_full_preamble() + prompt
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path

# Path to the industry context library JSON (co-located with this file)
_INDUSTRY_CONTEXT_PATH = Path(__file__).parent / "industry_context.json"

# Cache the JSON in memory — file is tiny (~8KB) and read-only at runtime
_industry_db: Optional[Dict] = None


def _load_industry_db() -> Dict:
    global _industry_db
    if _industry_db is None:
        try:
            with open(_INDUSTRY_CONTEXT_PATH, "r", encoding="utf-8") as f:
                _industry_db = json.load(f)
        except Exception:
            _industry_db = {}
    return _industry_db


@dataclass
class PromptContext:
    """
    Immutable context bag injected into every Gemini prompt for a tenant.

    Fields
    ------
    industry          Industry slug (e.g. "fintech/payments")
    sub_domain        Optional specialization (e.g. "lending")
    glossary          Tenant-confirmed term overrides {"term": "definition"}
    regulatory        Applicable regulatory frameworks ["PCI-DSS", "GDPR", ...]
    industry_vocabulary  Domain vocabulary from the industry library
    prompt_injection  Verbatim preamble block to prepend to AI prompts
    """

    industry: str = ""
    sub_domain: str = ""
    glossary: Dict[str, str] = field(default_factory=dict)
    regulatory: List[str] = field(default_factory=list)
    industry_vocabulary: Dict[str, str] = field(default_factory=dict)
    prompt_injection: str = ""

    @property
    def is_empty(self) -> bool:
        """True when this context carries no meaningful information."""
        return not self.industry and not self.glossary and not self.prompt_injection

    def render_industry_block(self) -> str:
        """Render the industry + regulatory block as prompt text."""
        if not self.industry:
            return ""
        lines = [f"Industry: {self.industry}"]
        if self.sub_domain:
            lines.append(f"Sub-domain: {self.sub_domain}")
        if self.regulatory:
            lines.append(f"Applicable regulations: {', '.join(self.regulatory)}")
        return "\n".join(lines)

    def render_glossary_block(self) -> str:
        """Render tenant glossary as a bullet list for prompt injection."""
        if not self.glossary:
            return ""
        items = [f"  - {term}: {defn}" for term, defn in list(self.glossary.items())[:20]]
        return "TENANT GLOSSARY (use these definitions):\n" + "\n".join(items)

    def render_vocabulary_block(self) -> str:
        """Render industry vocabulary as a compact reference block."""
        if not self.industry_vocabulary:
            return ""
        items = [
            f"  - {term}: {defn}"
            for term, defn in list(self.industry_vocabulary.items())[:15]
        ]
        return "DOMAIN VOCABULARY:\n" + "\n".join(items)

    def render_full_preamble(self) -> str:
        """
        Render the complete context preamble to prepend to any Gemini prompt.

        Returns empty string if context is empty — callers can safely concatenate.

        Priority order:
          1. Verbatim industry prompt_injection (most authoritative)
          2. Tenant glossary overrides
          3. Industry vocabulary reference
        """
        parts = []

        if self.prompt_injection:
            parts.append(self.prompt_injection)

        glossary_block = self.render_glossary_block()
        if glossary_block:
            parts.append(glossary_block)

        if parts:
            return "\n\n".join(parts) + "\n\n"
        return ""

    def __repr__(self) -> str:
        return (
            f"PromptContext(industry={self.industry!r}, "
            f"glossary_terms={len(self.glossary)}, "
            f"regulatory={self.regulatory}, "
            f"has_injection={bool(self.prompt_injection)})"
        )


def build_prompt_context(
    db,
    tenant_id: int,
    example_type: Optional[str] = None,
) -> PromptContext:
    """
    Build a PromptContext from the tenant's settings + industry library.

    This is the single entry point called from every Gemini method.
    Never raises — returns an empty PromptContext on any failure.

    Args:
        db          SQLAlchemy session
        tenant_id   Tenant to build context for
        example_type  Hint for future few-shot selection ("validation", "atomization")

    Returns:
        PromptContext — populated or empty (caller checks .is_empty)
    """
    try:
        from app.models.tenant import Tenant

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return PromptContext()

        tenant_settings: Dict = tenant.settings or {}
        industry_slug: str = tenant_settings.get("industry", "")
        sub_domain: str = tenant_settings.get("sub_domain", "")
        glossary: Dict = tenant_settings.get("glossary", {})
        regulatory_ctx: List = tenant_settings.get("regulatory_context", [])

        # Load industry data from the JSON library
        industry_db = _load_industry_db()
        industry_data = industry_db.get(industry_slug, {})

        # Merge: regulatory from tenant settings UNION library defaults
        lib_regulatory = industry_data.get("regulatory", [])
        merged_regulatory = list(dict.fromkeys(regulatory_ctx + lib_regulatory))

        return PromptContext(
            industry=industry_slug,
            sub_domain=sub_domain,
            glossary=glossary if isinstance(glossary, dict) else {},
            regulatory=merged_regulatory,
            industry_vocabulary=industry_data.get("vocabulary", {}),
            prompt_injection=industry_data.get("prompt_injection", ""),
        )

    except Exception:
        # Context building MUST never break the Gemini call
        return PromptContext()
