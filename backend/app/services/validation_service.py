# backend/app/services/validation_service.py

import asyncio
import hashlib
import httpx
from collections import defaultdict
from typing import List, Optional
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app import crud, models, schemas
from app.db.session import SessionLocal
from app.services.ai.gemini import (
    call_gemini_for_validation, ValidationType, ValidationContext,
    gemini_service,
)
from app.models.document_code_link import DocumentCodeLink
# Phase 1: Data Flywheel — capture AI judgments for training
from app.services.flywheel import capture_mismatch_judgment
from app.core.logging import LoggerMixin
from app.core.exceptions import ValidationException, AIAnalysisException

# Your semaphore for rate limiting is preserved
GEMINI_API_SEMAPHORE = asyncio.Semaphore(5)

class ValidationService(LoggerMixin):
    
    def __init__(self):
        super().__init__()
    
    @staticmethod
    @asynccontextmanager
    async def get_db_session():
        """
        Your robust async context manager for database sessions is preserved.
        """
        db: Session = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    async def run_validation_scan(self, user_id: int, document_ids: List[int], tenant_id: int = None):
        """
        Run validation scan for documents.

        SPRINT 2 Phase 6: Added tenant_id for multi-tenancy isolation.

        Args:
            user_id: User ID who triggered the scan
            document_ids: List of document IDs to validate
            tenant_id: Tenant ID for isolation (SPRINT 2)
        """
        if not document_ids:
            self.logger.warning(f"No document IDs provided for user {user_id}")
            return

        self.logger.info(
            f"Starting validation scan for user_id: {user_id}, tenant_id: {tenant_id} "
            f"on documents: {document_ids}"
        )
        async with ValidationService.get_db_session() as db:
            try:
                # SPRINT 2 Phase 6: Filter by tenant_id for isolation
                filters = [
                    models.Document.owner_id == user_id,
                    models.Document.id.in_(document_ids)
                ]
                if tenant_id:
                    filters.append(models.Document.tenant_id == tenant_id)

                user_documents = db.query(models.Document).filter(and_(*filters)).all()

                found_doc_ids = [doc.id for doc in user_documents]
                if len(found_doc_ids) != len(document_ids):
                    missing_docs = set(document_ids) - set(found_doc_ids)
                    self.logger.warning(f"Some documents not found or not owned by user {user_id}: {missing_docs}")

                if not found_doc_ids:
                    self.logger.warning(f"No valid documents found for user {user_id}")
                    return

                # SPRINT 2 Phase 6: Filter links by tenant_id
                link_filters = [
                    models.Document.owner_id == user_id,
                    models.DocumentCodeLink.document_id.in_(found_doc_ids)
                ]
                if tenant_id:
                    link_filters.append(models.Document.tenant_id == tenant_id)

                links = db.query(models.DocumentCodeLink).join(models.Document).filter(
                    and_(*link_filters)
                ).all()

                if not links:
                    self.logger.info(
                        f"No document-code links found for documents {found_doc_ids} "
                        f"for user {user_id} (tenant_id={tenant_id})"
                    )
                    return

                # SPRINT 2 Phase 6: Pass tenant_id to validate_single_link
                tasks = [self.validate_single_link(link, user_id, tenant_id) for link in links]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                successful_validations = 0
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        self.logger.error(f"Validation failed for link {links[i].id}: {result}")
                    else:
                        successful_validations += 1

                self.logger.info(f"Validation completed: {successful_validations}/{len(links)} links processed successfully")

            except Exception as e:
                self.logger.error(f"Top-level error in validation scan for user {user_id}: {e}", exc_info=True)
                raise
            finally:
                self.logger.info(f"Validation scan finished for user_id: {user_id}")

    async def atomize_document(self, db, document, tenant_id: int, user_id: int) -> list:
        """
        Sprint 10: BRD Atomization.

        Decomposes a document's text into typed RequirementAtoms — one-time per document
        version. Results are stored in the `requirement_atoms` table and returned from
        cache on subsequent calls (no AI cost when document hasn't changed).

        Cache key: (document_id, document.version)
        Source text: document.raw_text (capped at 12,000 chars), falls back to
                     structured_analysis summaries from AnalysisResult rows.

        Returns a list of RequirementAtom ORM objects.
        """
        if not gemini_service:
            self.logger.warning("GeminiService not available — skipping atomization")
            return []

        doc_version = getattr(document, "version", None) or "1.0"

        # Check cache: atoms already stored for this (document_id, version)?
        cached = crud.requirement_atom.get_by_document_version(
            db, document_id=document.id, document_version=doc_version
        )
        if cached:
            self.logger.info(
                f"Using {len(cached)} cached atoms for doc {document.id} v{doc_version}"
            )
            return cached

        # Build source text for atomization
        doc_text = ""
        raw = getattr(document, "raw_text", None) or ""
        if raw and len(raw) >= 200:
            doc_text = raw[:12000]
        else:
            # Fallback: synthesise from AnalysisResult.structured_data fields
            try:
                analysis_rows = crud.analysis_result.get_multi_by_document(
                    db=db, document_id=document.id
                )
                parts = []
                for row in (analysis_rows or []):
                    sd = row.structured_data or {}
                    for key in ("summary", "key_requirements", "business_rules",
                                "api_contracts", "data_models", "purpose"):
                        val = sd.get(key)
                        if isinstance(val, list):
                            parts.extend(str(v)[:300] for v in val[:10])
                        elif isinstance(val, str) and val:
                            parts.append(val[:500])
                doc_text = "\n".join(parts)[:12000]
            except Exception as e:
                self.logger.warning(f"Could not build doc text from analysis rows: {e}")

        if not doc_text or len(doc_text) < 50:
            self.logger.warning(
                f"Document {document.id} has insufficient text for atomization "
                f"(raw_text length: {len(raw)}, fallback length: {len(doc_text)})"
            )
            return []

        self.logger.info(
            f"Atomizing document {document.id} '{document.filename}' "
            f"({len(doc_text)} chars) — version {doc_version}"
        )

        atoms_data = await gemini_service.call_gemini_for_atomization(
            doc_text, tenant_id=tenant_id, user_id=user_id
        )

        if not atoms_data:
            self.logger.warning(f"Atomization returned 0 atoms for doc {document.id}")
            return []

        # Delete any stale atoms for this document (different version) then bulk-insert
        crud.requirement_atom.delete_by_document(db, document_id=document.id)
        new_atoms = crud.requirement_atom.create_atoms_bulk(
            db,
            tenant_id=tenant_id,
            document_id=document.id,
            document_version=doc_version,
            atoms_data=atoms_data,
        )
        self.logger.info(
            f"Stored {len(new_atoms)} RequirementAtoms for doc {document.id}"
        )
        return new_atoms

    async def validate_single_link(self, link: DocumentCodeLink, user_id: int, tenant_id: int = None):
        """
        Sprint 10: Full 9-pass atomic validation engine.

        Pass structure:
          Forward passes (1–8): One AI call per RequirementAtom type present in the BRD.
            Each call checks atoms of that specific type against the code's structured_analysis.
            Mismatches stored with direction="forward" and requirement_atom_id FK.
          Reverse pass (9): One AI call asking "what did the developer build that the BA never specified?"
            Mismatches stored with direction="reverse" and details.classification set.

        Falls back to legacy 3-pass engine if atomization yields 0 atoms.
        """
        async with GEMINI_API_SEMAPHORE:
            async with ValidationService.get_db_session() as db:
                try:
                    # ── Load document and code component ──────────────────────────────
                    doc_filters = [models.Document.id == link.document_id]
                    if tenant_id:
                        doc_filters.append(models.Document.tenant_id == tenant_id)
                    document = db.query(models.Document).filter(and_(*doc_filters)).first()

                    code_filters = [models.CodeComponent.id == link.code_component_id]
                    if tenant_id:
                        code_filters.append(models.CodeComponent.tenant_id == tenant_id)
                    code_component = db.query(models.CodeComponent).filter(and_(*code_filters)).first()

                    if not document or not code_component:
                        self.logger.error(
                            f"Missing document or code component for link {link.id} "
                            f"(tenant_id={tenant_id})"
                        )
                        return

                    if not code_component.structured_analysis:
                        self.logger.warning(
                            f"Skipping link {link.id}: code component not yet analyzed"
                        )
                        return

                    self.logger.info(
                        f"[Link {link.id}] Validating: '{document.filename}' vs '{code_component.name}'"
                    )

                    # ── Step 1: Atomize document (cached or fresh) ────────────────────
                    atoms = await self.atomize_document(db, document, tenant_id, user_id)

                    # ── Step 2: Clear old mismatches for this link ────────────────────
                    crud.mismatch.remove_by_link(
                        db=db,
                        document_id=document.id,
                        code_component_id=code_component.id,
                        tenant_id=tenant_id,
                    )

                    code_analysis = code_component.structured_analysis
                    total_cost_inr = 0.0
                    total_cost_usd = 0.0

                    if atoms:
                        # ── Step 3: Group atoms by type ───────────────────────────────
                        # Build atom_id (REQ-001) → DB id map for FK resolution
                        atom_id_to_db_id = {a.atom_id: a.id for a in atoms}
                        # Build plain dicts for passing to AI (ORM objects aren't serialisable)
                        atoms_by_type: dict[str, list] = defaultdict(list)
                        for atom in atoms:
                            atoms_by_type[atom.atom_type].append({
                                "atom_id": atom.atom_id,
                                "content": atom.content,
                                "criticality": atom.criticality,
                            })

                        self.logger.info(
                            f"[Link {link.id}] {len(atoms)} atoms across "
                            f"{len(atoms_by_type)} types: {list(atoms_by_type.keys())}"
                        )

                        # ── Step 4: Run all typed forward passes in parallel ──────────
                        if gemini_service:
                            forward_tasks = [
                                gemini_service.call_gemini_for_typed_validation(
                                    atom_type=atype,
                                    atoms=atype_atoms,
                                    code_analysis=code_analysis,
                                    tenant_id=tenant_id,
                                    user_id=user_id,
                                )
                                for atype, atype_atoms in atoms_by_type.items()
                            ]
                            forward_results = await asyncio.gather(
                                *forward_tasks, return_exceptions=True
                            )

                            for result in forward_results:
                                if isinstance(result, Exception):
                                    self.logger.error(
                                        f"[Link {link.id}] Forward pass error: {result}"
                                    )
                                    continue

                                mismatches = result.get("mismatches", [])
                                for m in mismatches:
                                    # Resolve atom_local_id → DB id
                                    local_id = m.pop("atom_local_id", None)
                                    db_atom_id = atom_id_to_db_id.get(local_id) if local_id else None

                                    try:
                                        new_mismatch = crud.mismatch.create_with_link(
                                            db=db,
                                            obj_in={
                                                **m,
                                                "direction": "forward",
                                                "requirement_atom_id": db_atom_id,
                                            },
                                            link_id=link.id,
                                            owner_id=user_id,
                                            tenant_id=tenant_id,
                                        )
                                        # Phase 1: Capture AI judgment for data flywheel
                                        try:
                                            capture_mismatch_judgment(
                                                db=db,
                                                mismatch=new_mismatch,
                                                tenant_id=tenant_id,
                                            )
                                        except Exception:
                                            pass  # Never block validation for flywheel failure
                                    except Exception as store_err:
                                        self.logger.warning(
                                            f"[Link {link.id}] Could not store forward mismatch: {store_err}"
                                        )

                                cost_info = result.get("_cost") or {}
                                total_cost_inr += cost_info.get("cost_inr", 0)
                                total_cost_usd += cost_info.get("cost_usd", 0)

                        # ── Step 5: Build atoms summary for reverse pass ──────────────
                        atoms_summary_lines = [
                            f"[{a.atom_type}] {a.atom_id}: {a.content[:150]}"
                            for a in atoms
                        ]
                        atoms_summary = "\n".join(atoms_summary_lines)

                        # ── Step 6: Run reverse pass ──────────────────────────────────
                        if gemini_service:
                            reverse_result = await gemini_service.call_gemini_for_reverse_validation(
                                code_analysis=code_analysis,
                                atoms_summary=atoms_summary,
                                tenant_id=tenant_id,
                                user_id=user_id,
                            )
                            for m in reverse_result.get("mismatches", []):
                                try:
                                    crud.mismatch.create_with_link(
                                        db=db,
                                        obj_in={**m, "direction": "reverse"},
                                        link_id=link.id,
                                        owner_id=user_id,
                                        tenant_id=tenant_id,
                                    )
                                except Exception as store_err:
                                    self.logger.warning(
                                        f"[Link {link.id}] Could not store reverse mismatch: {store_err}"
                                    )

                            rev_cost = (reverse_result.get("_cost") or {})
                            total_cost_inr += rev_cost.get("cost_inr", 0)
                            total_cost_usd += rev_cost.get("cost_usd", 0)

                    else:
                        # ── Fallback: legacy 3-pass engine when atomization yields 0 atoms ──
                        self.logger.warning(
                            f"[Link {link.id}] Atomization yielded 0 atoms — "
                            "falling back to legacy 3-pass engine"
                        )
                        doc_analysis_objects = crud.analysis_result.get_multi_by_document(
                            db=db, document_id=document.id
                        )
                        document_analysis_data = [
                            res.structured_data for res in (doc_analysis_objects or [])
                            if res.structured_data
                        ]

                        if document_analysis_data:
                            legacy_tasks = [
                                call_gemini_for_validation(
                                    ValidationContext(
                                        focus_area=vtype,
                                        document_analysis=document_analysis_data,
                                        code_analysis=code_analysis,
                                    )
                                )
                                for vtype in [
                                    ValidationType.API_ENDPOINT_MISSING,
                                    ValidationType.BUSINESS_LOGIC_MISSING,
                                    ValidationType.GENERAL_CONSISTENCY,
                                ]
                            ]
                            legacy_results = await asyncio.gather(
                                *legacy_tasks, return_exceptions=True
                            )
                            for result in legacy_results:
                                if isinstance(result, Exception):
                                    continue
                                for m in result.get("mismatches", []):
                                    try:
                                        crud.mismatch.create_with_link(
                                            db=db,
                                            obj_in={**m, "direction": "forward"},
                                            link_id=link.id,
                                            owner_id=user_id,
                                            tenant_id=tenant_id,
                                        )
                                    except Exception:
                                        pass
                                cost_info = result.get("_cost") or {}
                                total_cost_inr += cost_info.get("cost_inr", 0)
                                total_cost_usd += cost_info.get("cost_usd", 0)

                    # ── Step 7: Log billing ───────────────────────────────────────────
                    if total_cost_inr > 0:
                        try:
                            from app.services.billing_enforcement_service import billing_enforcement_service
                            billing_enforcement_service.deduct_cost(
                                db=db, tenant_id=tenant_id, cost_inr=total_cost_inr,
                                description=f"Validation: {document.filename}",
                            )
                        except Exception as billing_err:
                            self.logger.warning(f"Billing deduction failed (non-critical): {billing_err}")

                        try:
                            crud.usage_log.log_usage(
                                db=db, tenant_id=tenant_id, user_id=user_id,
                                feature_type="validation",
                                operation="atomic_validation",
                                model_used="gemini-2.5-flash",
                                input_tokens=0,
                                output_tokens=0,
                                cost_usd=total_cost_usd,
                                cost_inr=total_cost_inr,
                            )
                        except Exception as log_err:
                            self.logger.warning(f"Usage logging failed (non-critical): {log_err}")

                    self.logger.info(
                        f"[Link {link.id}] Validation complete. "
                        f"Atoms: {len(atoms)}, Cost: ₹{total_cost_inr:.4f}"
                    )

                except Exception as e:
                    self.logger.error(f"Error validating link {link.id}: {e}", exc_info=True)
                    raise

    async def generate_coverage_suggestions(
        self, document_id: int, user_id: int, tenant_id: int
    ) -> list:
        """
        Suggest additional code files to link based on existing mismatch records.

        Strategy:
        - Reads existing Mismatch records (free — already in DB)
        - Reads unlinked CodeComponent.structured_analysis summaries (free — already in DB)
        - One small AI call to score which unlinked files address the most gaps
        - Returns top 3 relevant files with reasons
        """
        import json
        from app.services.ai.gemini import gemini_service

        async with ValidationService.get_db_session() as db:
            try:
                # 1. Load existing mismatches for this document
                mismatches = db.query(models.Mismatch).filter(
                    models.Mismatch.document_id == document_id,
                    models.Mismatch.tenant_id == tenant_id,
                ).limit(30).all()

                if not mismatches:
                    return []

                # 2. Get IDs of already-linked code components
                linked_ids = {
                    link.code_component_id
                    for link in db.query(models.DocumentCodeLink).filter(
                        models.DocumentCodeLink.document_id == document_id,
                    ).all()
                }

                # 3. Get analyzed, unlinked code components for this tenant
                candidates = db.query(models.CodeComponent).filter(
                    models.CodeComponent.tenant_id == tenant_id,
                    models.CodeComponent.structured_analysis.isnot(None),
                    ~models.CodeComponent.id.in_(linked_ids) if linked_ids else True,
                ).limit(25).all()

                if not candidates:
                    return []

                # 4. Build gap summary from existing mismatch records
                gap_descriptions = [
                    f"[{m.mismatch_type}] {m.description[:200]}"
                    for m in mismatches
                ]

                # 5. Build compact candidate summaries (reuse stored structured_analysis)
                candidate_summaries = []
                for c in candidates:
                    analysis = c.structured_analysis or {}
                    candidate_summaries.append({
                        "id": c.id,
                        "name": c.name,
                        "summary": str(
                            analysis.get("summary", analysis.get("purpose", analysis.get("description", "")))
                        )[:300],
                        "functions": [
                            str(f)[:80] for f in
                            (analysis.get("functions", analysis.get("endpoints", analysis.get("methods", []))) or [])[:5]
                        ],
                    })

                # 6. Single AI call to score all candidates at once
                prompt = f"""You are a software validation expert.

A document was validated against linked code files and produced these gaps:

VALIDATION GAPS:
{chr(10).join(f"- {g}" for g in gap_descriptions[:15])}

CANDIDATE CODE FILES (not yet linked to this document):
{json.dumps(candidate_summaries, indent=2)}

Identify which candidate files (if any) would address the most validation gaps if linked.
Only recommend files with genuine relevance (relevance_score >= 0.55).
Return ONLY a JSON array of up to 3 files. If none are relevant, return [].

Required format:
[
  {{
    "component_id": <integer id>,
    "component_name": "<file name>",
    "relevance_score": <float 0.0-1.0>,
    "reason": "<one sentence: what this file provides that fills the gaps>",
    "gaps_addressed": ["<short gap label 1>", "<short gap label 2>"]
  }}
]"""

                response = await gemini_service.generate_content(
                    prompt,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    operation="coverage_suggestion",
                )
                text = response.text.strip().replace("```json", "").replace("```", "").strip()
                result = json.loads(text)
                if isinstance(result, list):
                    valid_ids = {c.id for c in candidates}
                    return [r for r in result if r.get("component_id") in valid_ids][:3]

            except Exception as e:
                self.logger.warning(f"Coverage suggestion for doc {document_id} failed: {e}")

        return []

    async def run_jira_validation_scan(
        self,
        *,
        tenant_id: int,
        user_id: int,
        repository_id: int,
        project_key: Optional[str] = None,
        epic_key: Optional[str] = None,
        sprint_name: Optional[str] = None,
    ) -> dict:
        """
        Sprint 9: Validate code against JIRA acceptance criteria.

        For each story/task with acceptance criteria in the given scope,
        asks Gemini whether the linked code satisfies each criterion.
        Stores results as Mismatch records with mismatch_type='jira_acceptance_criteria'.

        Returns summary: {checked, satisfied, partial, missing, errors}
        """
        stats = {"checked": 0, "satisfied": 0, "partial": 0, "missing": 0, "errors": []}

        async with ValidationService.get_db_session() as db:
            try:
                from app.crud.crud_jira_item import crud_jira_item
                from app.models.code_component import CodeComponent

                # Fetch JiraItems in scope
                jira_items = crud_jira_item.get_with_acceptance_criteria(
                    db,
                    tenant_id=tenant_id,
                    project_key=project_key,
                    epic_key=epic_key,
                    sprint_name=sprint_name,
                )

                if not jira_items:
                    self.logger.info(
                        f"No JIRA items with acceptance criteria found for "
                        f"project={project_key} epic={epic_key} sprint={sprint_name}"
                    )
                    return stats

                # Fetch code components for the repository
                components = (
                    db.query(CodeComponent)
                    .filter(
                        CodeComponent.repository_id == repository_id,
                        CodeComponent.tenant_id == tenant_id,
                    )
                    .limit(50)
                    .all()
                )

                # Build a compact code summary for context
                code_summary_parts = []
                for c in components[:20]:
                    summary = (getattr(c, "summary", None) or "")[:300]
                    code_summary_parts.append(f"- {c.location}: {summary}")
                code_context = "\n".join(code_summary_parts) if code_summary_parts else "No code components available."

                # Validate each item's acceptance criteria
                for item in jira_items:
                    for criterion in (item.acceptance_criteria or []):
                        if not criterion or not criterion.strip():
                            continue
                        try:
                            verdict, evidence = await self._check_jira_criterion(
                                criterion=criterion,
                                jira_key=item.external_key,
                                jira_title=item.title,
                                code_context=code_context,
                                tenant_id=tenant_id,
                                user_id=user_id,
                            )
                            stats["checked"] += 1
                            stats[verdict] = stats.get(verdict, 0) + 1

                            # Store as a Mismatch record
                            severity = "info" if verdict == "satisfied" else ("warning" if verdict == "partial" else "critical")
                            mismatch = models.Mismatch(
                                owner_id=user_id,
                                tenant_id=tenant_id,
                                description=f"[{item.external_key}] {criterion[:300]}",
                                category="jira_acceptance_criteria",
                                severity=severity,
                                status="open" if verdict != "satisfied" else "resolved",
                                details={
                                    "jira_key": item.external_key,
                                    "jira_title": item.title,
                                    "criterion": criterion,
                                    "verdict": verdict,
                                    "evidence": evidence,
                                    "repository_id": repository_id,
                                },
                            ) if hasattr(models, "Mismatch") else None

                            if mismatch:
                                db.add(mismatch)

                        except Exception as e:
                            self.logger.warning(
                                f"Criterion check failed [{item.external_key}]: {e}"
                            )
                            stats["errors"].append(f"{item.external_key}: {str(e)[:100]}")

                db.commit()
                self.logger.info(
                    f"JIRA validation complete — tenant={tenant_id} "
                    f"checked={stats['checked']} satisfied={stats['satisfied']} "
                    f"partial={stats['partial']} missing={stats['missing']}"
                )

            except Exception as e:
                self.logger.error(f"JIRA validation scan failed: {e}", exc_info=True)
                stats["errors"].append(str(e)[:200])

        return stats

    async def _check_jira_criterion(
        self,
        *,
        criterion: str,
        jira_key: str,
        jira_title: str,
        code_context: str,
        tenant_id: int,
        user_id: int,
    ) -> tuple[str, str]:
        """
        Ask Gemini whether the given code context satisfies a single acceptance criterion.
        Returns (verdict, evidence) where verdict is 'satisfied'|'partial'|'missing'.
        """
        prompt = f"""You are a QA validation engine. Determine if the codebase satisfies a JIRA acceptance criterion.

JIRA Ticket: {jira_key} — {jira_title}

Acceptance Criterion:
"{criterion}"

Code Components Summary:
{code_context[:4000]}

Answer in JSON with exactly this structure:
{{
  "verdict": "satisfied" | "partial" | "missing",
  "evidence": "<one sentence explaining your reasoning>"
}}

Rules:
- "satisfied": The code clearly implements or handles this criterion.
- "partial": Some evidence exists but implementation appears incomplete.
- "missing": No evidence this criterion is addressed in the code.
"""
        from app.services.ai.gemini import gemini_service
        async with GEMINI_API_SEMAPHORE:
            response = await gemini_service.generate_content(
                prompt,
                tenant_id=tenant_id,
                user_id=user_id,
                operation="jira_validation",
            )

        text = (response.text or "").strip()
        # Parse JSON response
        import json, re
        try:
            # Extract JSON from response
            match = re.search(r'\{[^{}]*"verdict"[^{}]*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                verdict = data.get("verdict", "missing")
                if verdict not in ("satisfied", "partial", "missing"):
                    verdict = "missing"
                evidence = data.get("evidence", "")
                return verdict, evidence
        except Exception:
            pass

        # Fallback: keyword scan
        lower = text.lower()
        if "satisfied" in lower:
            return "satisfied", text[:200]
        if "partial" in lower:
            return "partial", text[:200]
        return "missing", text[:200]


validation_service = ValidationService()