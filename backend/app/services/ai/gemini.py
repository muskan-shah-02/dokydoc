# backend/app/services/ai/gemini.py

import json
import asyncio
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import LoggerMixin
from app.services.ai.prompt_manager import prompt_manager, PromptType

class GeminiService(LoggerMixin):
    """
    Service class for interacting with Google's Gemini AI API.
    Provides both text and vision capabilities with retry logic and error handling.
    """

    def __init__(self):
        super().__init__()

        if not settings.GEMINI_API_KEY or "YOUR_GEMINI_API_KEY_HERE" in settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured correctly")

        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        self.vision_model = genai.GenerativeModel(settings.GEMINI_VISION_MODEL)
        self.logger.info("GeminiService initialized successfully")

    @staticmethod
    def extract_token_usage(response) -> Dict[str, int]:
        """
        Extract ALL token counts from a Gemini API response, including thinking tokens.

        Gemini 2.5 Flash has thinking mode ON by default. The usage_metadata contains:
        - prompt_token_count: Input tokens
        - candidates_token_count: Visible output tokens
        - thoughts_token_count: Hidden reasoning/thinking tokens (CRITICAL for billing!)
        - total_token_count: Sum of all tokens

        Thinking tokens are billed at $3.50/1M (same as output) but are NOT included
        in candidates_token_count. They must be tracked separately.
        """
        usage = getattr(response, 'usage_metadata', None)
        if not usage:
            return {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "total_tokens": 0}

        input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
        output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
        thinking_tokens = getattr(usage, 'thoughts_token_count', 0) or 0
        total_tokens = getattr(usage, 'total_token_count', 0) or (input_tokens + output_tokens + thinking_tokens)

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "thinking_tokens": thinking_tokens,
            "total_tokens": total_tokens,
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_content(
        self, prompt: str,
        *,
        tenant_id: int = None,
        user_id: int = None,
        operation: str = None,
        **kwargs
    ) -> genai.types.GenerateContentResponse:
        """
        Generate content with retry logic, error handling, and CENTRALIZED BILLING.

        Returns the full response object including usage_metadata for token tracking.

        When tenant_id is provided, automatically:
        1. Calculates cost from actual token usage
        2. Deducts cost from tenant billing balance
        3. Logs usage to usage_logs table for the billing portal

        This ensures EVERY Gemini API call is tracked — no more billing gaps.
        """
        try:
            # Enhanced logging for API call tracking
            prompt_length = len(prompt)
            self.logger.info(f"🤖 GEMINI API CALL - Prompt length: {prompt_length} chars")
            self.logger.debug(f"Prompt preview: {prompt[:200]}...")

            response = await self.model.generate_content_async(prompt, **kwargs)

            # Extract ALL token counts including thinking tokens
            tokens = self.extract_token_usage(response)
            response_length = len(response.text) if response.text else 0

            self.logger.info(
                f"✅ GEMINI API SUCCESS - Response: {response_length} chars | "
                f"Tokens: {tokens['input_tokens']} input + {tokens['output_tokens']} output + "
                f"{tokens['thinking_tokens']} thinking = {tokens['total_tokens']} total"
            )

            # CENTRALIZED BILLING: auto-log cost when tenant context is provided
            if tenant_id and (tokens['input_tokens'] > 0 or tokens['output_tokens'] > 0):
                self._auto_log_cost(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    operation=operation or "gemini_api_call",
                    tokens=tokens,
                )

            return response
        except Exception as e:
            self.logger.error(f"❌ GEMINI API ERROR: {e}")
            raise

    def _auto_log_cost(
        self,
        tenant_id: int,
        user_id: int = None,
        operation: str = "gemini_api_call",
        tokens: dict = None,
    ):
        """
        Centralized cost logging — called after EVERY Gemini API call.
        Calculates cost, deducts from tenant billing, and logs to usage_logs.

        Uses a dedicated DB session so it never interferes with the caller's transaction.
        """
        if not tokens:
            return

        try:
            from app.services.cost_service import cost_service
            cost_data = cost_service.calculate_cost_from_actual_tokens(
                input_tokens=tokens.get("input_tokens", 0),
                output_tokens=tokens.get("output_tokens", 0),
                thinking_tokens=tokens.get("thinking_tokens", 0),
            )
            cost_inr = cost_data.get("cost_inr", 0)
            cost_usd = cost_data.get("cost_usd", 0)

            if cost_inr <= 0:
                return

            # Use a dedicated DB session for billing (isolated from caller's transaction)
            from app.db.session import SessionLocal
            from app import crud
            billing_db = SessionLocal()
            try:
                # 1. Deduct from tenant billing balance
                from app.services.billing_enforcement_service import billing_enforcement_service
                billing_enforcement_service.deduct_cost(
                    db=billing_db,
                    tenant_id=tenant_id,
                    cost_inr=cost_inr,
                    description=f"Auto: {operation}",
                )

                # 2. Log to usage_logs for the billing portal
                crud.usage_log.log_usage(
                    db=billing_db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    feature_type="code_analysis" if "code" in operation or "analysis" in operation else "document_analysis",
                    operation=operation,
                    model_used="gemini-2.5-flash",
                    input_tokens=tokens.get("input_tokens", 0),
                    output_tokens=tokens.get("output_tokens", 0) + tokens.get("thinking_tokens", 0),
                    cost_usd=cost_usd,
                    cost_inr=cost_inr,
                    extra_data={"thinking_tokens": tokens.get("thinking_tokens", 0), "auto_logged": True},
                )

                billing_db.commit()
                self.logger.info(
                    f"💰 AUTO-BILLED: ₹{cost_inr:.4f} for {operation} (tenant={tenant_id})"
                )

            except Exception as billing_err:
                billing_db.rollback()
                self.logger.warning(f"Auto-billing failed (non-critical): {billing_err}")
            finally:
                billing_db.close()

        except Exception as e:
            self.logger.warning(f"Auto-cost-logging failed (non-critical): {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_content_with_vision(self, prompt: str, image, **kwargs) -> genai.types.GenerateContentResponse:
        """
        Generate content with vision capabilities and retry logic.
        """
        try:
            self.logger.debug("Sending vision request to Gemini API")
            response = await self.vision_model.generate_content_async([prompt, image], **kwargs)
            self.logger.debug("Gemini Vision API response received successfully")
            return response
        except Exception as e:
            self.logger.error(f"Error calling Gemini Vision API: {e}")
            raise

    async def call_gemini_for_enhanced_analysis(
        self, code_content: str, repo_name: str = "", file_path: str = "", language: str = "",
        tenant_id: int = None, user_id: int = None, product_context: str = "",
    ) -> dict:
        """
        SPRINT 3 Day 5 (AI-02): Enhanced semantic analysis with business rules,
        API contracts, data models, and security pattern extraction.
        Uses language-specific guidance when available.
        product_context: BOE context envelope injected for cross-file understanding.
        """
        try:
            self.logger.info(f"Enhanced analysis for {file_path} ({language})")

            language_guidance = prompt_manager.get_language_guidance(language)

            prompt = prompt_manager.get_prompt(
                PromptType.ENHANCED_SEMANTIC_ANALYSIS,
                repo_name=repo_name or "unknown",
                file_path=file_path or "unknown",
                language=language or "auto-detect",
                language_specific_guidance=language_guidance
            )

            # Inject BOE product context if available
            if product_context and product_context != "No prior context available for this file.":
                full_prompt = f"{prompt}\n\nPRODUCT CONTEXT (from previously analyzed files):\n{product_context}\n\nCODE TO ANALYZE:\n{code_content}"
            else:
                full_prompt = f"{prompt}\n{code_content}"

            response = await self.generate_content(
                full_prompt,
                tenant_id=tenant_id,
                user_id=user_id,
                operation=f"enhanced_analysis:{file_path}",
            )
            response_text = response.text

            # Extract ALL token counts including thinking tokens
            tokens = self.extract_token_usage(response)

            try:
                analysis_data = json.loads(response_text)
                self.logger.info(f"Enhanced analysis completed for {file_path}")
            except json.JSONDecodeError:
                # Try to repair JSON
                cleaned = response_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                try:
                    analysis_data = json.loads(cleaned)
                except json.JSONDecodeError as e:
                    # Handle "Extra data" — Gemini appended text after valid JSON
                    # Find the end of the first complete JSON object
                    extracted = None
                    if "Extra data" in str(e) or "extra data" in str(e):
                        try:
                            decoder = json.JSONDecoder()
                            extracted, _ = decoder.raw_decode(cleaned)
                        except json.JSONDecodeError:
                            pass
                    if extracted is not None:
                        self.logger.warning(f"Extracted first JSON object for {file_path} (extra data trimmed)")
                        analysis_data = extracted
                    else:
                        self.logger.error(f"Failed to parse enhanced analysis JSON for {file_path}: {e}")
                        analysis_data = {
                            "summary": f"Enhanced analysis completed but response parsing failed for {file_path}",
                            "structured_analysis": {
                                "language_info": {"primary_language": language or "Unknown", "framework": "Unknown", "file_type": "Unknown"},
                                "business_rules": [],
                                "api_contracts": [],
                                "data_model_relationships": [],
                                "security_patterns": [],
                                "components": [],
                                "dependencies": [],
                                "exports": [],
                                "patterns_and_architecture": {"design_patterns": [], "architectural_style": "Unknown", "key_concepts": []},
                                "quality_assessment": "Analysis failed due to response parsing error"
                            }
                        }

            # Always include token usage for cost tracking (including thinking tokens!)
            analysis_data["_token_usage"] = {
                "input_tokens": tokens["input_tokens"],
                "output_tokens": tokens["output_tokens"],
                "thinking_tokens": tokens["thinking_tokens"],
                "total_tokens": tokens["total_tokens"],
                "prompt_length": len(full_prompt),
                "response_length": len(response_text) if response_text else 0,
            }
            return analysis_data

        except Exception as e:
            self.logger.error(f"Error in enhanced analysis for {file_path}: {e}")
            raise

    async def call_gemini_for_markdown_analysis(
        self, doc_content: str, repo_name: str = "", file_path: str = "",
        tenant_id: int = None, user_id: int = None,
    ) -> dict:
        """
        SPRINT 5: Specialized analysis for Markdown documentation files.
        Extracts purpose, referenced code, business rules, architecture decisions,
        and key concepts so they appear in the knowledge graph and RAG pipeline.
        """
        try:
            self.logger.info(f"Markdown analysis for {file_path}")

            prompt = prompt_manager.get_prompt(
                PromptType.MARKDOWN_ANALYSIS,
                repo_name=repo_name or "unknown",
                file_path=file_path or "unknown",
            )
            full_prompt = f"{prompt}\n{doc_content}"

            response = await self.generate_content(
                full_prompt,
                tenant_id=tenant_id,
                user_id=user_id,
                operation=f"markdown_analysis:{file_path}",
            )
            response_text = response.text
            tokens = self.extract_token_usage(response)

            try:
                analysis_data = json.loads(response_text)
            except json.JSONDecodeError:
                cleaned = response_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                try:
                    analysis_data = json.loads(cleaned)
                except json.JSONDecodeError as e:
                    extracted = None
                    if "Extra data" in str(e) or "extra data" in str(e):
                        try:
                            decoder = json.JSONDecoder()
                            extracted, _ = decoder.raw_decode(cleaned)
                        except json.JSONDecodeError:
                            pass
                    if extracted is not None:
                        self.logger.warning(f"Extracted first JSON object for markdown {file_path}")
                        analysis_data = extracted
                    else:
                        self.logger.error(f"Failed to parse markdown analysis JSON for {file_path}: {e}")
                        analysis_data = {
                            "summary": f"Markdown documentation file: {file_path}",
                            "structured_analysis": {
                                "language_info": {"primary_language": "Markdown", "file_type": "Documentation", "doc_type": "OTHER"},
                                "purpose": f"Documentation file at {file_path}",
                                "topics": [],
                                "components": [],
                                "referenced_code_files": [],
                                "api_contracts": [],
                                "business_rules": [],
                                "architecture_decisions": [],
                                "data_model_relationships": [],
                                "patterns_and_architecture": {"design_patterns": [], "architectural_style": "Unknown", "key_concepts": []},
                                "setup_instructions": None,
                                "quality_assessment": "Analysis failed due to response parsing error",
                                "dependencies": [],
                                "exports": [],
                                "security_patterns": [],
                                "component_interactions": [],
                                "data_flows": [],
                            }
                        }

            analysis_data["_token_usage"] = {
                "input_tokens": tokens["input_tokens"],
                "output_tokens": tokens["output_tokens"],
                "thinking_tokens": tokens["thinking_tokens"],
                "total_tokens": tokens["total_tokens"],
                "prompt_length": len(full_prompt),
                "response_length": len(response_text) if response_text else 0,
            }
            return analysis_data

        except Exception as e:
            self.logger.error(f"Error in markdown analysis for {file_path}: {e}")
            raise

    async def call_gemini_for_delta_analysis(
        self, file_path: str, previous_analysis: dict, current_analysis: dict,
        tenant_id: int = None, user_id: int = None,
    ) -> dict:
        """
        SPRINT 3 Day 5 (AI-02): Compares new analysis with previous analysis
        to detect meaningful changes (added, removed, modified components).
        """
        try:
            self.logger.info(f"Delta analysis for {file_path}")

            prompt = prompt_manager.get_prompt(
                PromptType.DELTA_ANALYSIS,
                file_path=file_path,
                previous_analysis=json.dumps(previous_analysis, indent=2),
                current_analysis=json.dumps(current_analysis, indent=2)
            )

            response = await self.generate_content(
                prompt,
                tenant_id=tenant_id,
                user_id=user_id,
                operation=f"delta_analysis:{file_path}",
            )
            response_text = response.text

            # Extract ALL token counts including thinking tokens
            tokens = self.extract_token_usage(response)

            try:
                delta_data = json.loads(response_text)
            except json.JSONDecodeError:
                cleaned = response_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                try:
                    delta_data = json.loads(cleaned)
                except json.JSONDecodeError:
                    self.logger.warning(f"Delta analysis JSON parse failed for {file_path}")
                    delta_data = {
                        "has_changes": False,
                        "change_summary": "Delta analysis response parsing failed",
                        "changes": {"added": [], "removed": [], "modified": []},
                        "risk_assessment": {
                            "overall_risk": "none",
                            "breaking_changes_count": 0,
                            "requires_doc_update": False,
                            "requires_test_update": False,
                            "reasoning": "Parse error"
                        }
                    }

            # Always include token usage for cost tracking (including thinking tokens!)
            delta_data["_token_usage"] = {
                "input_tokens": tokens["input_tokens"],
                "output_tokens": tokens["output_tokens"],
                "thinking_tokens": tokens["thinking_tokens"],
                "total_tokens": tokens["total_tokens"],
            }
            return delta_data

        except Exception as e:
            self.logger.error(f"Error in delta analysis for {file_path}: {e}")
            raise

    async def call_gemini_for_code_analysis(
        self, code_content: str,
        tenant_id: int = None, user_id: int = None,
    ) -> dict:
        """
        Analyzes ANY file's content using a universal, adaptive prompt.
        Works with any programming language, framework, or architectural pattern.
        Returns analysis data with token usage for cost tracking.
        """
        try:
            self.logger.info("Making a real call to the Gemini API for universal code analysis...")

            # Use the prompt manager for code analysis
            prompt = prompt_manager.get_prompt(PromptType.CODE_ANALYSIS)

            # Prepare the full prompt with the code content
            full_prompt = f"{prompt}\n\nCODE TO ANALYZE:\n{code_content}"

            # Call Gemini API
            response = await self.generate_content(
                full_prompt,
                tenant_id=tenant_id,
                user_id=user_id,
                operation="code_analysis",
            )
            response_text = response.text

            # Extract ALL token counts including thinking tokens
            tokens = self.extract_token_usage(response)

            # Parse the JSON response (strip markdown code fences if present)
            try:
                analysis_data = json.loads(response_text)
                self.logger.info("Code analysis completed successfully")
            except json.JSONDecodeError:
                # Gemini often wraps JSON in ```json...``` markdown fences — strip them
                cleaned = response_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                try:
                    analysis_data = json.loads(cleaned)
                    self.logger.info("Code analysis completed (stripped markdown fences)")
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse Gemini response as JSON: {e}")
                    analysis_data = {
                        "summary": "Code analysis completed but response parsing failed",
                        "structured_analysis": {
                            "language_info": {"primary_language": "Unknown", "framework": "Unknown", "file_type": "Unknown"},
                            "components": [],
                            "dependencies": [],
                            "exports": [],
                            "patterns_and_architecture": {"design_patterns": [], "architectural_style": "Unknown", "key_concepts": []},
                            "quality_assessment": "Analysis failed due to response parsing error"
                        }
                    }

            # Always include token usage for cost tracking (including thinking tokens!)
            analysis_data["_token_usage"] = {
                "input_tokens": tokens["input_tokens"],
                "output_tokens": tokens["output_tokens"],
                "thinking_tokens": tokens["thinking_tokens"],
                "total_tokens": tokens["total_tokens"],
                "prompt_length": len(full_prompt),
                "response_length": len(response_text) if response_text else 0,
            }
            return analysis_data

        except Exception as e:
            self.logger.error(f"Error in code analysis: {e}")
            raise

    async def call_gemini_for_atomization(
        self,
        doc_text: str,
        tenant_id: int = None,
        user_id: int = None,
    ) -> list:
        """
        Sprint 10: BRD Atomization Pass.

        Decomposes a BRD into discrete, typed requirement atoms. Each atom is exactly
        one testable requirement. Atoms are cached per document version so this runs
        only once per document unless the document changes.

        Atom types:
          API_CONTRACT | BUSINESS_RULE | FUNCTIONAL_REQUIREMENT | DATA_CONSTRAINT |
          WORKFLOW_STEP | ERROR_SCENARIO | SECURITY_REQUIREMENT | NFR | INTEGRATION_POINT

        Returns list of dicts: [{"atom_id": "REQ-001", "atom_type": "...", "content": "...", "criticality": "..."}]
        """
        prompt = f"""You are a requirements engineering expert. Decompose the following Business Requirements Document (BRD) into atomic, typed requirements.

RULES:
1. Each atom must represent exactly ONE testable requirement — not a paragraph.
2. Assign an atom_type from this exact list:
   API_CONTRACT | BUSINESS_RULE | FUNCTIONAL_REQUIREMENT | DATA_CONSTRAINT |
   WORKFLOW_STEP | ERROR_SCENARIO | SECURITY_REQUIREMENT | NFR | INTEGRATION_POINT
3. Set criticality: "critical" (must work for launch), "standard" (important), "informational" (nice to have).
4. Keep content as the verbatim or minimally paraphrased requirement sentence.
5. Number atoms REQ-001, REQ-002, ... in order.
6. Extract ALL distinct requirements — aim for completeness. A 5-page BRD typically yields 30-80 atoms.

Return ONLY a valid JSON array. No explanations, no markdown fences.

REQUIRED FORMAT:
[
  {{
    "atom_id": "REQ-001",
    "atom_type": "API_CONTRACT",
    "content": "POST /auth/login returns a JWT token containing user_id and role",
    "criticality": "critical"
  }}
]

BRD TEXT:
{doc_text[:12000]}
"""
        try:
            response = await self.generate_content(
                prompt,
                tenant_id=tenant_id,
                user_id=user_id,
                operation="brd_atomization",
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()
            result = json.loads(text)
            if isinstance(result, list):
                valid_types = {
                    "API_CONTRACT", "BUSINESS_RULE", "FUNCTIONAL_REQUIREMENT",
                    "DATA_CONSTRAINT", "WORKFLOW_STEP", "ERROR_SCENARIO",
                    "SECURITY_REQUIREMENT", "NFR", "INTEGRATION_POINT",
                }
                cleaned = []
                for i, atom in enumerate(result):
                    if not isinstance(atom, dict) or not atom.get("content"):
                        continue
                    atom_type = atom.get("atom_type", "FUNCTIONAL_REQUIREMENT")
                    if atom_type not in valid_types:
                        atom_type = "FUNCTIONAL_REQUIREMENT"
                    cleaned.append({
                        "atom_id": atom.get("atom_id") or f"REQ-{i+1:03d}",
                        "atom_type": atom_type,
                        "content": str(atom["content"])[:1000],
                        "criticality": atom.get("criticality", "standard"),
                    })
                self.logger.info(f"Atomization produced {len(cleaned)} atoms")
                return cleaned
            return []
        except Exception as e:
            self.logger.error(f"BRD atomization failed: {e}", exc_info=True)
            return []

    # Atom type → focused validation instructions
    _ATOM_TYPE_INSTRUCTIONS = {
        "API_CONTRACT": (
            "API CONTRACTS: For each atom, check whether the code implements the specified "
            "HTTP endpoint with the correct method, path, authentication requirement, request "
            "parameters, and response shape. Flag: missing endpoints, wrong HTTP method, missing "
            "auth enforcement, wrong response structure, incorrect status codes."
        ),
        "BUSINESS_RULE": (
            "BUSINESS RULES: For each atom, check whether the code implements the stated "
            "condition, calculation, or eligibility logic. Verify all branches are covered. "
            "Flag: missing rule, wrong formula, missing edge-case handling, incorrect conditions."
        ),
        "FUNCTIONAL_REQUIREMENT": (
            "FUNCTIONAL REQUIREMENTS: For each atom, check whether the system capability "
            "described is implemented. Flag: missing features, partial implementation, or "
            "capabilities that exist in name only without the specified behaviour."
        ),
        "DATA_CONSTRAINT": (
            "DATA CONSTRAINTS: For each atom, check whether the specified field exists with "
            "the correct type and stated validation enforced (max length, required, regex, range). "
            "Flag: missing fields, wrong type, absent validation, no uniqueness enforcement."
        ),
        "WORKFLOW_STEP": (
            "WORKFLOW STEPS: For each atom, check whether all steps occur in the correct order "
            "and compensating actions (rollback, cleanup) exist for failure paths. "
            "Flag: missing steps, wrong order, no rollback, missing post-step side effects."
        ),
        "ERROR_SCENARIO": (
            "ERROR SCENARIOS: For each atom, check whether the error case is handled, returns "
            "the specified HTTP status, and produces the correct message. "
            "Flag: unhandled error, wrong status code, missing/misleading error message."
        ),
        "SECURITY_REQUIREMENT": (
            "SECURITY REQUIREMENTS: For each atom, check whether the stated auth check, RBAC "
            "enforcement, or encryption is implemented. "
            "Flag: missing auth decorator, absent permission check, sensitive data not masked."
        ),
        "NFR": (
            "NON-FUNCTIONAL REQUIREMENTS: For each atom, check whether performance/scalability "
            "constraints are reflected (pagination, caching, async, timeouts, retry). "
            "Flag: no pagination on list endpoints, no timeout on external calls, blocking ops."
        ),
        "INTEGRATION_POINT": (
            "INTEGRATION POINTS: For each atom, check whether the external service call is "
            "implemented on the correct trigger and includes failure handling. "
            "Flag: missing call, wrong trigger, no retry, missing webhook handler."
        ),
    }

    async def call_gemini_for_typed_validation(
        self,
        atom_type: str,
        atoms: list,
        code_analysis: dict,
        tenant_id: int = None,
        user_id: int = None,
    ) -> dict:
        """
        Sprint 10: One typed forward-pass validation.

        Checks a group of same-type RequirementAtoms against the code's structured_analysis.
        Each mismatch includes atom_local_id (REQ-001 string) which the caller resolves
        to the DB RequirementAtom.id for the requirement_atom_id FK.

        Returns {"mismatches": [...], "_cost": {...}}
        """
        instructions = self._ATOM_TYPE_INSTRUCTIONS.get(
            atom_type,
            "Check each requirement against the code and report genuine implementation gaps."
        )
        atoms_json = json.dumps([
            {"atom_id": a["atom_id"], "content": a["content"], "criticality": a.get("criticality", "standard")}
            for a in atoms
        ], indent=2)

        prompt = f"""You are a senior software architect performing a focused validation check.

TASK: For each requirement atom below, determine whether the code analysis shows it is implemented.
Flag ONLY genuine, high-confidence gaps. Do not flag things that are clearly implemented.

VALIDATION FOCUS — {atom_type}:
{instructions}

Return ONLY a valid JSON array. If ALL atoms are satisfied, return [].

RESPONSE FORMAT:
[
  {{
    "atom_local_id": "REQ-003",
    "mismatch_type": "{atom_type}",
    "description": "One-sentence summary of the gap.",
    "severity": "High",
    "confidence": "High",
    "details": {{
      "expected": "What the requirement atom specifies.",
      "actual": "What the code shows (or 'Not found').",
      "evidence_document": "Quote from the requirement atom.",
      "evidence_code": "Quote or reference from the code analysis.",
      "suggested_action": "What the developer should do to fix this."
    }}
  }}
]

REQUIREMENT ATOMS ({atom_type}):
{atoms_json}

CODE ANALYSIS:
{json.dumps(code_analysis, indent=2)[:5000]}
"""
        try:
            response = await self.generate_content(
                prompt,
                tenant_id=tenant_id,
                user_id=user_id,
                operation=f"typed_validation:{atom_type}",
            )
            tokens = self.extract_token_usage(response)
            from app.services.cost_service import cost_service
            cost_data = cost_service.calculate_cost_from_actual_tokens(
                input_tokens=tokens["input_tokens"],
                output_tokens=tokens["output_tokens"],
                thinking_tokens=tokens["thinking_tokens"],
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()
            result = json.loads(text)
            mismatches = result if isinstance(result, list) else []
            self.logger.info(f"Typed validation [{atom_type}]: {len(mismatches)} mismatches")
            return {"mismatches": mismatches, "_cost": cost_data}
        except Exception as e:
            self.logger.error(f"Typed validation [{atom_type}] failed: {e}", exc_info=True)
            return {"mismatches": [], "_cost": None}

    async def call_gemini_for_reverse_validation(
        self,
        code_analysis: dict,
        atoms_summary: str,
        tenant_id: int = None,
        user_id: int = None,
    ) -> dict:
        """
        Sprint 10: Reverse pass — code → doc (BA Accountability).

        Finds code capabilities that have NO corresponding BRD requirement.
        Gives the BA their report: "Your BRD doesn't cover these X capabilities."

        Classifications:
          SCOPE_CREEP         — feature built but never discussed
          IMPLICIT_REQUIREMENT — probably intended but not written down
          UNDOCUMENTED        — unclear origin; needs clarification

        Returns {"mismatches": [...], "_cost": {...}}
        """
        prompt = f"""You are a BA accountability auditor reviewing code against a requirements document.

TASK: Identify code capabilities that have NO corresponding BRD requirement.
This is the REVERSE direction — you look at what was BUILT and ask "was this SPECIFIED?"

BRD REQUIREMENTS SUMMARY (for reference):
{atoms_summary[:3000]}

CODE ANALYSIS:
{json.dumps(code_analysis, indent=2)[:5000]}

INSTRUCTIONS:
- Examine every implemented endpoint, business function, integration call, and data model operation.
- For each one, check: is there a BRD requirement that justifies this capability?
- Only flag capabilities that are clearly undocumented — skip obvious infrastructure (logging, DB sessions, config loading, etc.).
- Classify each finding:
    SCOPE_CREEP         — feature built but never in the BRD
    IMPLICIT_REQUIREMENT — probably intended but not written
    UNDOCUMENTED        — unclear; needs clarification with BA/PM

Return ONLY a valid JSON array. If all code is covered by requirements, return [].

RESPONSE FORMAT:
[
  {{
    "mismatch_type": "Undocumented Capability",
    "description": "One-sentence description of the undocumented capability.",
    "severity": "Medium",
    "confidence": "High",
    "details": {{
      "expected": "No BRD requirement found for this capability.",
      "actual": "Code implements: <what it does>.",
      "evidence_document": "No matching requirement atom.",
      "evidence_code": "Function/endpoint name and summary of behaviour.",
      "suggested_action": "BA should either document this requirement or developer should remove this capability.",
      "classification": "SCOPE_CREEP"
    }}
  }}
]
"""
        try:
            response = await self.generate_content(
                prompt,
                tenant_id=tenant_id,
                user_id=user_id,
                operation="reverse_validation",
            )
            tokens = self.extract_token_usage(response)
            from app.services.cost_service import cost_service
            cost_data = cost_service.calculate_cost_from_actual_tokens(
                input_tokens=tokens["input_tokens"],
                output_tokens=tokens["output_tokens"],
                thinking_tokens=tokens["thinking_tokens"],
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()
            result = json.loads(text)
            mismatches = result if isinstance(result, list) else []
            self.logger.info(f"Reverse validation: {len(mismatches)} undocumented capabilities")
            return {"mismatches": mismatches, "_cost": None}
        except Exception as e:
            self.logger.error(f"Reverse validation failed: {e}", exc_info=True)
            return {"mismatches": [], "_cost": None}


# Legacy compatibility - create a global instance
try:
    gemini_service = GeminiService()
    model = gemini_service.model  # For backward compatibility
except Exception as e:
    print(f"Warning: Could not initialize GeminiService: {e}")
    model = None
    gemini_service = None

# --- FUNCTION 1: CODE ANALYSIS (INTACT) ---
async def call_gemini_for_code_analysis(code_content: str) -> dict:
    """
    Legacy function for backward compatibility.
    """
    if gemini_service:
        return await gemini_service.call_gemini_for_code_analysis(code_content)
    else:
        raise RuntimeError("GeminiService not available")

# --- FUNCTION 3: SEMANTIC VALIDATION ENGINE (FULLY UPGRADED) ---

import logging as _logging
logger = _logging.getLogger("app.gemini_validation")

class ValidationType(Enum):
    """
    Defines the specific types of validation checks the engine can perform.
    This allows for focused, role-based analysis.
    """
    API_ENDPOINT_MISSING = "API Endpoint Missing"
    PARAMETER_MISMATCH = "Parameter Mismatch"
    BUSINESS_LOGIC_MISSING = "Business Logic Missing"
    DATA_FLOW_INCONSISTENCY = "Data Flow Inconsistency"
    SECURITY_REQUIREMENT_UNMET = "Security Requirement Unmet"
    PERFORMANCE_CONSTRAINT_UNMET = "Performance Constraint Unmet"
    GENERAL_CONSISTENCY = "General Consistency Check"

@dataclass
class ValidationContext:
    """
    **This is the upgraded context.** It holds structured analysis data,
    NOT raw text, which is the core of our intelligent strategy.
    """
    focus_area: ValidationType
    document_analysis: Optional[List[Dict]] = field(default_factory=list)
    code_analysis: Optional[Dict] = field(default_factory=dict)

def _build_validation_instructions(focus_area: ValidationType) -> str:
    """
    This helper generates detailed, specific instructions for the AI.
    This is the key to enabling different validation profiles for different user roles.
    """
    if focus_area == ValidationType.API_ENDPOINT_MISSING:
        return "API ENDPOINTS: Compare the functional requirements for API endpoints described in the document analysis against the implemented functions/classes in the code analysis. Identify any required endpoints that are completely missing from the code."
    if focus_area == ValidationType.BUSINESS_LOGIC_MISSING:
        return "BUSINESS LOGIC: Compare the high-level business requirements from the document analysis against the code's overall summary and component purposes. Identify any core business concepts or rules that are not mentioned or implemented in the code."
    return "GENERAL CONSISTENCY: Perform a general consistency check. Look for any other clear contradictions between the document's stated goals and the code's implementation details as presented in their respective analyses."

async def call_gemini_for_validation(
    context: ValidationContext, tenant_id: int = None, user_id: int = None,
) -> List[dict]:
    """
    **This is the upgraded validation function.**
    It sends structured data to the AI with a focused, role-based prompt.
    Now uses centralized generate_content() for automatic billing.
    """
    if not gemini_service:
        raise RuntimeError("GeminiService not available")

    logger.info(f"Starting focused Gemini validation for: {context.focus_area.value}")
    
    validation_instructions = _build_validation_instructions(context.focus_area)

    prompt = f"""
    You are an expert software architect acting as a semantic validation engine.
    Your task is to perform a highly focused validation check by comparing the structured analysis of a technical document against the structured analysis of a code file.

    CRITICAL INSTRUCTIONS:
    1.  **FOCUS**: Adhere strictly to the 'VALIDATION AREA' defined below.
    2.  **PRECISION**: Only flag genuine, high-impact mismatches. Be precise and actionable.
    3.  **SEMANTICS**: Understand intent. 'getUser' is equivalent to 'fetch_user_data'.
    4.  **EVIDENCE**: The 'expected' field MUST come from the DOCUMENT ANALYSIS. The 'actual' field MUST come from the CODE ANALYSIS.

    VALIDATION AREA:
    {validation_instructions}

    STRICT RESPONSE FORMAT:
    Return ONLY a valid JSON array of mismatch objects. Each object must follow this exact schema:
    {{
        "mismatch_type": "{context.focus_area.value}",
        "description": "A clear, one-sentence summary of the core mismatch.",
        "severity": "High | Medium | Low",
        "confidence": "High | Medium | Low",
        "details": {{
            "expected": "What the document's structured analysis specifies.",
            "actual": "What the code's structured analysis shows (or 'Missing').",
            "evidence_document": "A direct quote or summary from the document analysis.",
            "evidence_code": "A direct quote or summary from the code analysis.",
            "suggested_action": "A brief, actionable recommendation for a developer to fix the issue."
        }}
    }}
    If no mismatches are found for this specific validation area, you MUST return an empty array: [].

    DOCUMENT ANALYSIS (The "Source of Truth"):
    ```json
    {json.dumps(context.document_analysis, indent=2)}
    ```

    CODE ANALYSIS (The "Implementation"):
    ```json
    {json.dumps(context.code_analysis, indent=2)}
    ```
    """
    try:
        # Use centralized generate_content() for automatic billing tracking
        response = await gemini_service.generate_content(
            prompt,
            tenant_id=tenant_id,
            user_id=user_id,
            operation=f"validation:{context.focus_area.value}",
        )

        # Extract token counts for cost reporting
        tokens = GeminiService.extract_token_usage(response)
        from app.services.cost_service import cost_service
        cost_data = cost_service.calculate_cost_from_actual_tokens(
            input_tokens=tokens["input_tokens"],
            output_tokens=tokens["output_tokens"],
            thinking_tokens=tokens["thinking_tokens"],
        )
        logger.info(
            f"Validation API cost: ₹{cost_data['cost_inr']:.4f} "
            f"({tokens['input_tokens']} in + {tokens['output_tokens']} out + {tokens['thinking_tokens']} thinking)"
        )

        cleaned_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        result = json.loads(cleaned_text)
        logger.info(f"Validation for {context.focus_area.value} complete: {len(result)} mismatches found.")
        # Cost is now auto-logged by generate_content(), but still attach for callers
        return {"mismatches": result if isinstance(result, list) else [], "_cost": cost_data, "_tokens": tokens}
    except Exception as e:
        logger.error(f"Gemini validation for {context.focus_area.value} failed: {e}", exc_info=True)
        return {"mismatches": [], "_cost": None, "_tokens": None}
    