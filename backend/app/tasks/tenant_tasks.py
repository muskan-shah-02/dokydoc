"""
Tenant background tasks — Phase 5: Industry-Aware Prompt Injection

P5-04: detect_tenant_industry
  Fires asynchronously after tenant registration when company_website is provided.
  Fetches the homepage, strips HTML to visible text, calls Gemini once to classify
  the industry slug, then writes it to tenant.settings["industry"].

  On success: tenant.settings["industry"] is set, onboarding Step 2 will show
              "Auto-detected: Fintech / Payments" with a confidence badge.
  On failure: task retries once, then exits silently — user manually picks in wizard.
"""

import json
import re
from typing import Optional

from app.worker import celery_app
from app.db.session import SessionLocal
from app.core.logging import logger


# ── Industry constants ────────────────────────────────────────────────────────

KNOWN_INDUSTRY_SLUGS = {
    "fintech/payments",
    "fintech/lending",
    "banking",
    "healthcare",
    "saas",
    "ecommerce",
    "logistics",
    "devtools",
}

# Minimum confidence to auto-set the industry (below this → user chooses manually)
MIN_AUTO_DETECT_CONFIDENCE = 0.40


# ── HTML stripping utility ────────────────────────────────────────────────────

def _strip_html(html: str) -> str:
    """Extract visible text from HTML, removing tags, scripts, and styles."""
    # Remove script and style blocks
    html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags
    html = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    html = re.sub(r"\s+", " ", html).strip()
    return html[:4000]  # Cap at 4000 chars for the Gemini call


# ── Celery task ───────────────────────────────────────────────────────────────

@celery_app.task(
    name="detect_tenant_industry",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def detect_tenant_industry(self, tenant_id: int, website_url: str):
    """
    P5-04: Classify tenant industry from company website.

    Flow:
      1. Fetch website homepage (10s timeout)
      2. Strip HTML → visible text
      3. Single Gemini call: classify industry slug + confidence
      4. If confidence >= MIN_AUTO_DETECT_CONFIDENCE → write to tenant.settings
      5. If unknown industry → dispatch generate_industry_profile task

    Args:
        tenant_id    Tenant to update
        website_url  Company website URL (e.g. "https://acme.com")
    """
    logger.info(f"[P5-04] Detecting industry for tenant {tenant_id} from {website_url}")

    db = SessionLocal()
    try:
        # ── Step 1: Fetch website ─────────────────────────────────────────────
        website_text = _fetch_website_text(website_url)
        if not website_text or len(website_text) < 50:
            logger.warning(
                f"[P5-04] Website fetch returned insufficient content for tenant {tenant_id}"
            )
            return

        # ── Step 2: Classify with Gemini ──────────────────────────────────────
        classification = _classify_industry(website_text, tenant_id)
        if not classification:
            return

        detected_slug = classification.get("industry_slug", "").lower().strip()
        confidence = float(classification.get("confidence", 0.0))
        display_name = classification.get("display_name", detected_slug)
        parent_slug = classification.get("parent_slug")
        is_known = classification.get("is_known", detected_slug in KNOWN_INDUSTRY_SLUGS)

        logger.info(
            f"[P5-04] Tenant {tenant_id}: detected '{detected_slug}' "
            f"(confidence={confidence:.2f}, known={is_known})"
        )

        # ── Step 3: Apply if confidence is sufficient ─────────────────────────
        if confidence < MIN_AUTO_DETECT_CONFIDENCE:
            logger.info(
                f"[P5-04] Confidence {confidence:.2f} below threshold "
                f"{MIN_AUTO_DETECT_CONFIDENCE} — skipping auto-set for tenant {tenant_id}"
            )
            return

        # ── Step 4: Write to tenant.settings ─────────────────────────────────
        from app.models.tenant import Tenant

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            logger.warning(f"[P5-04] Tenant {tenant_id} not found")
            return

        current_settings = dict(tenant.settings or {})

        # Only set if industry not already manually chosen by user
        if not current_settings.get("industry"):
            current_settings["industry"] = detected_slug
            current_settings["industry_confidence"] = round(confidence, 2)
            current_settings["industry_display_name"] = display_name
            if parent_slug:
                current_settings["industry_parent"] = parent_slug

            tenant.settings = current_settings
            db.add(tenant)
            db.commit()
            logger.info(
                f"[P5-04] Set industry='{detected_slug}' for tenant {tenant_id}"
            )

        # ── Step 5: Trigger profile generation for unknown industries ─────────
        if not is_known and detected_slug:
            try:
                generate_industry_profile.delay(
                    slug=detected_slug,
                    display_name=display_name,
                    parent_slug=parent_slug,
                )
                logger.info(
                    f"[P5-04] Queued profile generation for unknown industry '{detected_slug}'"
                )
            except Exception as gen_err:
                logger.warning(f"[P5-04] Could not queue profile generation: {gen_err}")

    except Exception as exc:
        logger.error(f"[P5-04] Industry detection failed for tenant {tenant_id}: {exc}")
        try:
            self.retry(exc=exc)
        except Exception:
            pass  # Max retries reached — exit silently
    finally:
        db.close()


def _fetch_website_text(url: str) -> Optional[str]:
    """Fetch homepage HTML and return stripped visible text. Returns None on error."""
    try:
        import httpx
        # Ensure URL has scheme
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        with httpx.Client(timeout=10, follow_redirects=True) as client:
            response = client.get(
                url,
                headers={"User-Agent": "DokyDoc-IndustryDetector/1.0"},
            )
            response.raise_for_status()
            return _strip_html(response.text)
    except Exception as e:
        logger.warning(f"[P5-04] Website fetch failed for {url}: {e}")
        return None


def _classify_industry(website_text: str, tenant_id: int) -> Optional[dict]:
    """
    Single Gemini call to classify industry from website text.
    Returns classification dict or None on failure.
    """
    try:
        import google.generativeai as genai
        from app.core.config import settings as app_settings

        genai.configure(api_key=app_settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(app_settings.GEMINI_MODEL)

        prompt = f"""Analyze the following website text and classify the company's industry.

RESPOND WITH JSON ONLY (no explanations, no markdown fences):
{{
  "industry_slug": "<slug>",
  "parent_slug": "<parent_slug or null>",
  "is_known": true,
  "display_name": "<human readable name>",
  "confidence": 0.0,
  "reasoning": "<one sentence>"
}}

Valid known slugs: {', '.join(sorted(KNOWN_INDUSTRY_SLUGS))}

RULES:
- Use snake_case or parent/sub format (e.g. "fintech/payments", "healthcare")
- Set is_known=false if the slug is NOT in the known slugs list
- confidence: 0.0-1.0 (how certain you are of this classification)
- If website text is too generic to classify, set confidence < 0.4

WEBSITE TEXT:
{website_text}"""

        response = model.generate_content(prompt)
        text = response.text.strip()

        # Clean JSON fences if model adds them despite instructions
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        classification = json.loads(text)
        return classification

    except json.JSONDecodeError as je:
        logger.warning(f"[P5-04] JSON parse error in classification response: {je}")
        return None
    except Exception as e:
        logger.warning(f"[P5-04] Gemini classification failed for tenant {tenant_id}: {e}")
        return None


# ── Profile generation task (P5-13 stub) ─────────────────────────────────────

@celery_app.task(
    name="generate_industry_profile",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def generate_industry_profile(
    self,
    slug: str,
    display_name: str,
    parent_slug: Optional[str] = None,
):
    """
    P5-13: Generate an AI-powered industry profile for unknown/custom industries.

    For tenants in industries not in the built-in library (e.g. "insurtech",
    "agritech"), this task generates vocabulary, regulatory context, and a
    prompt_injection preamble on-the-fly and stores it for reuse.

    Currently stored in-memory via industry_context.json runtime cache.
    Future: persist to generated_industry_profiles DB table (migration s18a1).
    """
    logger.info(
        f"[P5-13] Generating profile for industry '{slug}' ({display_name})"
    )

    try:
        import google.generativeai as genai
        from app.core.config import settings as app_settings
        from app.services.ai.prompt_context import _load_industry_db

        genai.configure(api_key=app_settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(app_settings.GEMINI_MODEL)

        prompt = f"""Generate an industry context profile for a software documentation tool.
Industry: {display_name} (slug: {slug})
{f'Parent industry: {parent_slug}' if parent_slug else ''}

Return ONLY valid JSON (no markdown):
{{
  "display_name": "{display_name}",
  "regulatory": ["<regulation1>", "<regulation2>"],
  "vocabulary": {{
    "<term>": "<definition>",
    "<term2>": "<definition2>"
  }},
  "prompt_injection": "=== TENANT CONTEXT: {display_name.upper()} ===\\nKey compliance and validation areas for this industry.\\n=== END TENANT CONTEXT ==="
}}

Include 3-6 regulatory frameworks and 8-12 domain vocabulary terms."""

        response = model.generate_content(prompt)
        text = response.text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        profile = json.loads(text.strip())

        # Inject into runtime cache so subsequent prompt_context.build() calls use it
        industry_db = _load_industry_db()
        industry_db[slug] = profile
        logger.info(f"[P5-13] Profile for '{slug}' injected into runtime cache")

    except Exception as exc:
        logger.error(f"[P5-13] Profile generation failed for '{slug}': {exc}")
        try:
            self.retry(exc=exc)
        except Exception:
            pass
