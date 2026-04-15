"""
PromptContext — Industry-Aware Prompt Injection (Phase 5 + Phase 6 Smart Context)

Purpose
-------
Every Gemini call for a tenant optionally carries a PromptContext that prepends
tenant-specific knowledge to the prompt:
  - Industry vocabulary (so AI understands domain terms correctly)
  - Applicable regulations (from tenant's compliance selections + library defaults)
  - Tenant glossary (custom overrides confirmed by the tenant's team)
  - Verbatim prompt_injection preamble from the industry library

Phase 6 additions
-----------------
1. Context Budget Enforcement
   Each operation type (atomization, validation, coverage) has a character budget.
   The preamble is hard-capped to prevent context window overrun.

2. Selective Glossary Injection
   When a content_hint is supplied, only the glossary terms that appear in the
   hint text are injected (up to max_terms).  This avoids sending 50 irrelevant
   terms for every API call.

3. Compressed Context Cache
   The expensive parts (industry library lookup + regulatory merge) are stored
   as `compressed_context` in tenant.settings.  On the next build the cached
   version is returned without any JSON-file I/O.
   Cache is invalidated whenever tenant settings change (PATCH /tenants/me/settings
   calls _invalidate_compressed_cache, PUT /tenants/me/compliance does the same).

Usage
-----
    from app.services.ai.prompt_context import build_prompt_context

    ctx = build_prompt_context(db, tenant_id=tenant_id,
                               content_hint=doc_text[:500],
                               operation="atomization")
    preamble = ctx.render_full_preamble(content_hint=doc_text[:500],
                                        operation="atomization")
    prompt = preamble + your_prompt
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

# ─── Industry context library ─────────────────────────────────────────────────

_INDUSTRY_CONTEXT_PATH = Path(__file__).parent / "industry_context.json"
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


# ─── Context budgets (chars = tokens × 4 approx) ─────────────────────────────

CONTEXT_BUDGETS: Dict[str, int] = {
    "atomization":  3200,   # ~800 tokens — BRD docs are large; leave room
    "validation":   2000,   # ~500 tokens — code analysis already fills the window
    "coverage":     1200,   # ~300 tokens — lightweight matrix computation
    "default":      2400,   # ~600 tokens — fallback
}

# Maximum glossary terms per operation
GLOSSARY_LIMITS: Dict[str, int] = {
    "atomization": 8,   # more domain terms useful when decomposing BRD
    "validation":  5,   # keep tight during validation pass
    "coverage":    3,
    "default":     6,
}

# Compressed context cache TTL
_CACHE_TTL_HOURS = 24


# ─── PromptContext dataclass ──────────────────────────────────────────────────

@dataclass
class PromptContext:
    """
    Immutable context bag injected into every Gemini prompt for a tenant.
    """

    industry: str = ""
    sub_domain: str = ""
    glossary: Dict[str, str] = field(default_factory=dict)
    regulatory: List[str] = field(default_factory=list)
    industry_vocabulary: Dict[str, str] = field(default_factory=dict)
    prompt_injection: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.industry and not self.glossary and not self.prompt_injection

    # ── Rendering helpers ─────────────────────────────────────────────────────

    def render_industry_block(self) -> str:
        if not self.industry:
            return ""
        lines = [f"Industry: {self.industry}"]
        if self.sub_domain:
            lines.append(f"Sub-domain: {self.sub_domain}")
        if self.regulatory:
            lines.append(f"Applicable regulations: {', '.join(self.regulatory[:8])}")
        return "\n".join(lines)

    def render_glossary_block(self, content_hint: str = "", max_terms: Optional[int] = None) -> str:
        """
        Render tenant glossary as a bullet list.

        Selective injection: if content_hint is provided, terms whose key appears
        in the hint are promoted to the front.  Only max_terms are included.

        Args:
            content_hint  Sample of the document/code being analyzed (first 500 chars).
            max_terms     Override the default term limit.
        """
        if not self.glossary:
            return ""

        limit = max_terms or GLOSSARY_LIMITS["default"]

        if content_hint:
            hint_lower = content_hint.lower()
            # Score: 2 if term itself appears, 1 if any word of the term appears
            scored: List[tuple] = []
            for term, defn in self.glossary.items():
                term_lower = term.lower()
                score = 2 if term_lower in hint_lower else (
                    1 if any(w in hint_lower for w in term_lower.split() if len(w) > 3)
                    else 0
                )
                scored.append((score, term, defn))
            scored.sort(key=lambda x: x[0], reverse=True)
            terms = [(t, d) for _, t, d in scored[:limit]]
        else:
            terms = list(self.glossary.items())[:limit]

        items = [f"  - {term}: {defn}" for term, defn in terms]
        return "TENANT GLOSSARY (use these definitions):\n" + "\n".join(items)

    def render_vocabulary_block(self, content_hint: str = "", max_terms: int = 8) -> str:
        """Render industry vocabulary with selective injection."""
        if not self.industry_vocabulary:
            return ""

        if content_hint:
            hint_lower = content_hint.lower()
            scored = [
                (2 if k.lower() in hint_lower else 0, k, v)
                for k, v in self.industry_vocabulary.items()
            ]
            scored.sort(reverse=True)
            items_list = [(k, v) for _, k, v in scored[:max_terms]]
        else:
            items_list = list(self.industry_vocabulary.items())[:max_terms]

        items = [f"  - {term}: {defn}" for term, defn in items_list]
        return "DOMAIN VOCABULARY:\n" + "\n".join(items)

    def render_full_preamble(
        self,
        content_hint: str = "",
        operation: str = "default",
    ) -> str:
        """
        Render the full context preamble with budget enforcement.

        Args:
            content_hint  First ~500 chars of document/code — drives selective injection.
            operation     "atomization" | "validation" | "coverage" | "default"

        Returns:
            String to prepend to the Gemini prompt.  Empty string if no context.
        """
        budget_chars = CONTEXT_BUDGETS.get(operation, CONTEXT_BUDGETS["default"])
        max_terms = GLOSSARY_LIMITS.get(operation, GLOSSARY_LIMITS["default"])

        parts: List[str] = []

        # 1. Verbatim industry prompt injection (most authoritative, highest priority)
        if self.prompt_injection:
            parts.append(self.prompt_injection)

        # 2. Selective glossary
        glossary_block = self.render_glossary_block(
            content_hint=content_hint,
            max_terms=max_terms,
        )
        if glossary_block:
            parts.append(glossary_block)

        # 3. Vocabulary — only for atomization (needs domain terms most)
        if operation == "atomization" and self.industry_vocabulary:
            vocab_block = self.render_vocabulary_block(
                content_hint=content_hint,
                max_terms=5,
            )
            if vocab_block:
                parts.append(vocab_block)

        if not parts:
            return ""

        preamble = "\n\n".join(parts) + "\n\n"

        # ── Budget enforcement: hard-cap the preamble ──────────────────────────
        if len(preamble) > budget_chars:
            preamble = preamble[:budget_chars].rsplit("\n", 1)[0] + "\n[context truncated]\n\n"

        return preamble

    def __repr__(self) -> str:
        return (
            f"PromptContext(industry={self.industry!r}, "
            f"glossary_terms={len(self.glossary)}, "
            f"regulatory={self.regulatory[:3]}, "
            f"has_injection={bool(self.prompt_injection)})"
        )


# ─── Compressed context cache helpers ────────────────────────────────────────

def _build_compressed_cache(
    industry_slug: str,
    sub_domain: str,
    regulatory_from_settings: List[str],
) -> Dict:
    """
    Pre-compute the expensive parts of context into a JSON-serialisable dict.
    Stored in tenant.settings["compressed_context"] by build_prompt_context.
    """
    industry_db = _load_industry_db()
    industry_data = industry_db.get(industry_slug, {})
    lib_regulatory = industry_data.get("regulatory", [])
    merged_regulatory = list(dict.fromkeys(regulatory_from_settings + lib_regulatory))

    return {
        "industry": industry_slug,
        "sub_domain": sub_domain,
        "regulatory": merged_regulatory,
        "industry_vocabulary": industry_data.get("vocabulary", {}),
        "prompt_injection": industry_data.get("prompt_injection", ""),
        "generated_at": datetime.utcnow().isoformat(),
    }


def _cache_is_fresh(cached: Dict) -> bool:
    """Return True if the cached context is within TTL."""
    try:
        generated_at = datetime.fromisoformat(cached["generated_at"])
        return datetime.utcnow() - generated_at < timedelta(hours=_CACHE_TTL_HOURS)
    except Exception:
        return False


def invalidate_compressed_cache(db, tenant_id: int) -> None:
    """
    Remove the compressed_context from tenant.settings.
    Called when settings change so next build re-generates the cache.
    Non-blocking — never raises.
    """
    try:
        from app.models.tenant import Tenant
        from sqlalchemy import text as sa_text

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant and tenant.settings:
            settings = dict(tenant.settings)
            if "compressed_context" in settings:
                settings.pop("compressed_context")
                db.execute(
                    sa_text("UPDATE tenants SET settings = :s WHERE id = :id"),
                    {"s": json.dumps(settings), "id": tenant_id},
                )
                db.commit()
    except Exception:
        pass


# ─── Public API ───────────────────────────────────────────────────────────────

def build_prompt_context(
    db,
    tenant_id: int,
    example_type: Optional[str] = None,
    content_hint: str = "",
    operation: str = "default",
) -> PromptContext:
    """
    Build a PromptContext for a tenant.

    Phase 6: Tries to use the cached compressed_context from tenant.settings
    before doing any library lookups.  Falls back to full build on cache miss.

    Args:
        db            SQLAlchemy session
        tenant_id     Tenant to build context for
        example_type  Deprecated hint (kept for backward compat)
        content_hint  First ~500 chars of document/code for selective injection
        operation     "atomization" | "validation" | "coverage" — affects budget

    Returns:
        PromptContext — populated or empty (caller checks .is_empty)
    """
    try:
        from app.models.tenant import Tenant

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return PromptContext()

        tenant_settings: Dict = tenant.settings or {}
        glossary: Dict = tenant_settings.get("glossary", {})
        if not isinstance(glossary, dict):
            glossary = {}

        # ── Try compressed context cache first ────────────────────────────────
        cached = tenant_settings.get("compressed_context")
        if cached and isinstance(cached, dict) and _cache_is_fresh(cached):
            return PromptContext(
                industry=cached.get("industry", ""),
                sub_domain=cached.get("sub_domain", ""),
                glossary=glossary,
                regulatory=cached.get("regulatory", []),
                industry_vocabulary=cached.get("industry_vocabulary", {}),
                prompt_injection=cached.get("prompt_injection", ""),
            )

        # ── Full build ─────────────────────────────────────────────────────────
        industry_slug: str = tenant_settings.get("industry", "")
        sub_domain: str = tenant_settings.get("sub_domain", "")

        # Regulatory: from tenant compliance selections (P6) + settings legacy field
        compliance_codes: List[str] = tenant_settings.get("compliance_frameworks", [])
        regulatory_ctx: List[str] = tenant_settings.get("regulatory_context", [])
        merged_from_settings = list(dict.fromkeys(compliance_codes + regulatory_ctx))

        # Build and store compressed cache (non-blocking)
        try:
            compressed = _build_compressed_cache(industry_slug, sub_domain, merged_from_settings)
            # Persist cache back to settings asynchronously via DB
            from sqlalchemy import text as sa_text
            updated_settings = dict(tenant_settings)
            updated_settings["compressed_context"] = compressed
            db.execute(
                sa_text("UPDATE tenants SET settings = :s WHERE id = :id"),
                {"s": json.dumps(updated_settings), "id": tenant_id},
            )
            db.commit()
        except Exception:
            # Cache write failure is non-fatal — build context without caching
            compressed = _build_compressed_cache(industry_slug, sub_domain, merged_from_settings)

        return PromptContext(
            industry=compressed["industry"],
            sub_domain=compressed["sub_domain"],
            glossary=glossary,
            regulatory=compressed["regulatory"],
            industry_vocabulary=compressed["industry_vocabulary"],
            prompt_injection=compressed["prompt_injection"],
        )

    except Exception:
        # Context building MUST never break the Gemini call
        return PromptContext()
