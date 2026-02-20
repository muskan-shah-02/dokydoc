"""
SPRINT 3: Code Analysis Engine — Celery Workers (TASK-01)

Architecture:
  repo_analysis_task (orchestrator)
    └── for each file in repo:
           └── enhanced_analysis_worker (business rules, API contracts, data models, security + delta)

SPRINT 3 Day 5 (AI-02): Enhanced with:
  - Business rule extraction
  - API contract extraction
  - Data model relationship extraction
  - Security pattern detection
  - Language-specific analysis templates
  - Delta analysis (compare current vs previous)

The Repo Agent scans a repository's files and creates CodeComponent records
for each, linking them back to the parent Repository via repository_id.
"""

import asyncio
import hashlib
import json
import httpx
from typing import Optional

from app.worker import celery_app
from app.db.session import SessionLocal
from app import crud
from app.core.logging import logger
from app.tasks.utils import run_async as _run_async


def _hash_analysis(analysis: dict) -> str:
    """Create a stable hash of structured_analysis for delta detection."""
    if not analysis:
        return ""
    canonical = json.dumps(analysis, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


# ============================================================
# ENHANCED ANALYSIS WORKER (SPRINT 3 Day 5 — AI-02)
# ============================================================

@celery_app.task(name="static_analysis_worker", bind=True, max_retries=2)
def static_analysis_worker(
    self, component_id: int, tenant_id: int, code_content: str,
    repo_name: str = "", file_path: str = "", language: str = ""
):
    """
    Worker: Runs enhanced semantic analysis on a single file.

    SPRINT 3 Day 5 enhancements:
    - Uses ENHANCED_SEMANTIC_ANALYSIS prompt (business rules, API contracts,
      data models, security patterns) when repo context is available
    - Falls back to basic CODE_ANALYSIS for standalone components
    - Performs delta analysis when previous analysis exists
    - Language-specific guidance (Python/FastAPI, JS/React, Java/Spring, Go)
    """
    logger.info(
        f"ANALYSIS_WORKER started for component_id={component_id} "
        f"file={file_path} lang={language}"
    )

    db = SessionLocal()
    try:
        component = crud.code_component.get(db=db, id=component_id, tenant_id=tenant_id)
        if not component:
            logger.error(f"Analysis worker: Component {component_id} not found")
            return {"status": "error", "reason": "component_not_found"}

        # Save previous analysis for delta comparison
        previous_analysis = component.structured_analysis
        previous_hash = _hash_analysis(previous_analysis)

        # Update status
        crud.code_component.update(
            db, db_obj=component, obj_in={"analysis_status": "processing"}
        )

        # Check cache first
        from app.services.cache_service import cache_service
        cache_type = "enhanced_analysis" if repo_name else "code_analysis"
        cached = cache_service.get_cached_analysis(
            content=code_content, analysis_type=cache_type
        )

        if cached:
            logger.info(f"Cache HIT for component {component_id}")
            analysis_result = cached
        else:
            # Billing check
            from app.services.billing_enforcement_service import billing_enforcement_service
            try:
                check = billing_enforcement_service.check_can_afford_analysis(
                    db=db, tenant_id=tenant_id, estimated_cost_inr=3.0
                )
                if not check["can_proceed"]:
                    crud.code_component.update(
                        db, db_obj=component,
                        obj_in={"analysis_status": "failed"}
                    )
                    return {"status": "billing_blocked", "reason": check["reason"]}
            except Exception as billing_err:
                logger.warning(f"Billing check failed (proceeding): {billing_err}")

            # Route to AI provider (ADHOC-08: Claude for code in dual mode, Gemini otherwise)
            from app.services.ai.provider_router import provider_router

            if repo_name:
                # Enhanced analysis with business rules, API contracts, etc.
                analysis_result = _run_async(
                    provider_router.analyze_code_enhanced(
                        code_content,
                        repo_name=repo_name,
                        file_path=file_path,
                        language=language
                    )
                )
            else:
                # Fallback to basic analysis for standalone components
                analysis_result = _run_async(
                    provider_router.analyze_code(code_content)
                )

            # Cache the result
            cache_service.set_cached_analysis(
                content=code_content,
                analysis_type=cache_type,
                result=analysis_result,
                ttl_seconds=2592000  # 30 days
            )

            # Cost tracking for enhanced/basic analysis
            token_usage = analysis_result.get("_token_usage", {})
            if token_usage and token_usage.get("input_tokens", 0) > 0:
                try:
                    from app.services.cost_service import cost_service
                    cost_data = cost_service.calculate_cost_from_actual_tokens(
                        input_tokens=token_usage.get("input_tokens", 0),
                        output_tokens=token_usage.get("output_tokens", 0),
                        thinking_tokens=token_usage.get("thinking_tokens", 0),
                    )
                    analysis_cost_inr = cost_data.get("cost_inr", 0)
                    if analysis_cost_inr > 0:
                        billing_enforcement_service.deduct_cost(
                            db=db, tenant_id=tenant_id, cost_inr=analysis_cost_inr,
                            description=f"Code analysis: {file_path or component_id}"
                        )
                        crud.usage_log.log_usage(
                            db=db, tenant_id=tenant_id, user_id=None,
                            feature_type="code_analysis",
                            operation="enhanced_analysis" if repo_name else "basic_analysis",
                            model_used="gemini-2.5-flash",
                            input_tokens=token_usage.get("input_tokens", 0),
                            output_tokens=token_usage.get("output_tokens", 0) + token_usage.get("thinking_tokens", 0),
                            cost_usd=cost_data.get("cost_usd", 0),
                            cost_inr=analysis_cost_inr,
                        )
                        logger.info(f"Billed ₹{analysis_cost_inr:.4f} for analysis of {file_path}")
                except Exception as cost_err:
                    logger.warning(f"Cost tracking failed for analysis (non-critical): {cost_err}")

        # Delta analysis: compare with previous analysis if it exists
        new_analysis = analysis_result.get("structured_analysis")
        new_hash = _hash_analysis(new_analysis)
        delta_result = None

        if previous_analysis and previous_hash and new_hash != previous_hash:
            logger.info(f"Analysis changed for component {component_id} — running delta analysis")
            try:
                delta_result = _run_async(
                    provider_router.analyze_delta(
                        file_path=file_path or component.name,
                        previous_analysis=previous_analysis,
                        current_analysis=new_analysis
                    )
                )
                logger.info(
                    f"Delta analysis complete: has_changes={delta_result.get('has_changes')}, "
                    f"risk={delta_result.get('risk_assessment', {}).get('overall_risk', 'unknown')}"
                )
                # Cost tracking for delta analysis
                delta_tokens = delta_result.get("_token_usage", {})
                if delta_tokens and delta_tokens.get("input_tokens", 0) > 0:
                    try:
                        from app.services.cost_service import cost_service
                        delta_cost_data = cost_service.calculate_cost_from_actual_tokens(
                            input_tokens=delta_tokens.get("input_tokens", 0),
                            output_tokens=delta_tokens.get("output_tokens", 0),
                            thinking_tokens=delta_tokens.get("thinking_tokens", 0),
                        )
                        delta_cost_inr = delta_cost_data.get("cost_inr", 0)
                        if delta_cost_inr > 0:
                            billing_enforcement_service.deduct_cost(
                                db=db, tenant_id=tenant_id, cost_inr=delta_cost_inr,
                                description=f"Delta analysis: {file_path or component_id}"
                            )
                            crud.usage_log.log_usage(
                                db=db, tenant_id=tenant_id, user_id=None,
                                feature_type="code_analysis",
                                operation="delta_analysis",
                                model_used="gemini-2.5-flash",
                                input_tokens=delta_tokens.get("input_tokens", 0),
                                output_tokens=delta_tokens.get("output_tokens", 0) + delta_tokens.get("thinking_tokens", 0),
                                cost_usd=delta_cost_data.get("cost_usd", 0),
                                cost_inr=delta_cost_inr,
                            )
                            logger.info(f"Billed ₹{delta_cost_inr:.4f} for delta analysis of {file_path}")
                    except Exception as cost_err:
                        logger.warning(f"Cost tracking failed for delta analysis (non-critical): {cost_err}")
            except Exception as delta_err:
                logger.warning(f"Delta analysis failed (non-critical): {delta_err}")

        # Persist results
        update_data = {
            "summary": analysis_result.get("summary"),
            "structured_analysis": new_analysis,
            "analysis_status": "completed",
            "previous_analysis_hash": previous_hash if previous_analysis else None,
        }
        if delta_result:
            update_data["analysis_delta"] = delta_result

        crud.code_component.update(db, db_obj=component, obj_in=update_data)

        logger.info(f"ANALYSIS_WORKER completed for component {component_id}")
        return {
            "status": "completed",
            "component_id": component_id,
            "has_delta": delta_result is not None and delta_result.get("has_changes", False),
        }

    except Exception as e:
        logger.error(f"ANALYSIS_WORKER failed for component {component_id}: {e}")
        try:
            comp = crud.code_component.get(db=db, id=component_id, tenant_id=tenant_id)
            if comp:
                crud.code_component.update(db, db_obj=comp, obj_in={
                    "analysis_status": "failed",
                    "summary": f"Analysis failed: {str(e)}"
                })
        except Exception:
            pass

        try:
            self.retry(countdown=30 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(f"ANALYSIS_WORKER permanently failed for component {component_id}")

        return {"status": "failed", "component_id": component_id, "error": str(e)}
    finally:
        if db.is_active:
            db.commit()
        db.close()


# ============================================================
# REPOSITORY ANALYSIS ORCHESTRATOR
# ============================================================

def _file_analysis_priority(file_info: dict) -> tuple:
    """
    Sort files so foundational files are analyzed first (models, schemas, config)
    and dependent files later (controllers, views, tests).
    This makes cross-file context more useful — controllers benefit from
    knowing about models that were analyzed earlier.
    """
    path = file_info.get("path", "").lower()
    if any(k in path for k in ["model", "schema", "entity", "base", "config", "settings", "types"]):
        return (0, path)
    if any(k in path for k in ["service", "util", "helper", "middleware", "lib", "core"]):
        return (1, path)
    if any(k in path for k in ["controller", "route", "endpoint", "api", "view", "handler", "page"]):
        return (2, path)
    if any(k in path for k in ["test", "spec", "fixture", "__test__"]):
        return (3, path)
    return (1, path)  # Default: same priority as services


@celery_app.task(name="repo_analysis_task", bind=True, max_retries=1)
def repo_analysis_task(
    self, repo_id: int, tenant_id: int, file_list: list
):
    """
    Orchestrator: Iterates through the file list for a repository,
    creates CodeComponent records, and dispatches enhanced analysis
    for each file.

    Args:
        repo_id: Repository ID
        tenant_id: Tenant ID for multi-tenancy
        file_list: List of dicts [{"path": "src/foo.py", "url": "https://raw.../foo.py", "language": "python"}]
    """
    logger.info(
        f"REPO_AGENT started for repo_id={repo_id}, "
        f"tenant_id={tenant_id}, files={len(file_list)}"
    )

    db = SessionLocal()
    try:
        repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
        if not repo:
            logger.error(f"Repo agent: Repository {repo_id} not found")
            return {"status": "error", "reason": "repo_not_found"}

        # Mark repo as analyzing
        crud.repository.update_analysis_progress(
            db=db, repo_id=repo_id, tenant_id=tenant_id,
            analyzed_files=0, total_files=len(file_list),
            status="analyzing"
        )

        # Sort files: foundational first (models/schemas), then services, then controllers, tests last
        file_list.sort(key=_file_analysis_priority)
        logger.info(
            f"Repo {repo_id}: files sorted by dependency priority "
            f"(models→services→controllers→tests)"
        )

        # Running context: accumulates summaries from previously-analyzed files
        repo_context = []  # list of {"path": ..., "summary": ..., "file_type": ...}

        completed = 0
        failed = 0

        for file_info in file_list:
            file_path = file_info.get("path", "unknown")
            file_url = file_info.get("url", "")
            file_language = file_info.get("language", "unknown")

            try:
                # Fetch file content
                code_content = _fetch_file_content(file_url)
                if not code_content:
                    logger.warning(f"Empty content for {file_path}, skipping")
                    failed += 1
                    continue

                # Check if component already exists for this file (re-analysis scenario)
                from app.models.code_component import CodeComponent
                existing_component = db.query(CodeComponent).filter(
                    CodeComponent.repository_id == repo_id,
                    CodeComponent.name == file_path.split("/")[-1],
                    CodeComponent.location == file_url,
                    CodeComponent.tenant_id == tenant_id,
                ).first()

                if existing_component:
                    # Re-analysis: reuse existing component (delta analysis will kick in)
                    component = existing_component
                    logger.info(f"Re-analyzing existing component {component.id} for {file_path}")
                else:
                    # New file: create CodeComponent record
                    from app.schemas.code_component import CodeComponentCreate
                    component_in = CodeComponentCreate(
                        name=file_path.split("/")[-1],  # filename
                        component_type="File",
                        location=file_url,
                        version=repo.last_analyzed_commit or "HEAD",
                    )
                    component = crud.code_component.create_with_owner(
                        db=db, obj_in=component_in,
                        owner_id=repo.owner_id, tenant_id=tenant_id
                    )

                    # Link to repository
                    crud.code_component.update(
                        db, db_obj=component,
                        obj_in={"repository_id": repo_id}
                    )

                # Build cross-file context from previously-analyzed files
                # Provides lightweight awareness of sibling files (last 10)
                context_prefix = ""
                if repo_context:
                    recent = repo_context[-10:]
                    context_lines = [
                        f"  - {rc['path']} ({rc['file_type']}): {rc['summary']}"
                        for rc in recent
                    ]
                    context_prefix = (
                        "REPOSITORY CONTEXT (previously analyzed files in this repo):\n"
                        + "\n".join(context_lines)
                        + "\n\nNOW ANALYZING:\n"
                    )

                # Run enhanced analysis with repo context + language
                import time
                analysis_content = context_prefix + code_content if context_prefix else code_content
                result = static_analysis_worker(
                    component.id, tenant_id, analysis_content,
                    repo_name=repo.name,
                    file_path=file_path,
                    language=file_language
                )

                if result.get("status") == "completed":
                    completed += 1
                    # Accumulate context for subsequent files
                    try:
                        comp_refreshed = crud.code_component.get(
                            db=db, id=component.id, tenant_id=tenant_id
                        )
                        if comp_refreshed and comp_refreshed.summary:
                            sa = comp_refreshed.structured_analysis or {}
                            repo_context.append({
                                "path": file_path,
                                "summary": (comp_refreshed.summary or "")[:200],
                                "file_type": sa.get("language_info", {}).get("file_type", "Unknown"),
                            })
                    except Exception:
                        pass
                else:
                    failed += 1

                # Update progress atomically
                crud.repository.update_analysis_progress(
                    db=db, repo_id=repo_id, tenant_id=tenant_id,
                    analyzed_files=completed + failed
                )

                # Rate limiting: 4s sleep between analyses (15 RPM Gemini limit)
                time.sleep(4)

            except Exception as file_err:
                logger.error(f"Failed to process file {file_path}: {file_err}")
                failed += 1

        # Mark repo as completed or failed
        final_status = "completed" if failed == 0 else ("completed" if completed > 0 else "failed")
        error_msg = f"{failed} files failed analysis" if failed > 0 else None

        crud.repository.update_analysis_progress(
            db=db, repo_id=repo_id, tenant_id=tenant_id,
            analyzed_files=completed + failed,
            status=final_status,
            error_message=error_msg
        )

        logger.info(
            f"REPO_AGENT completed for repo {repo_id}: "
            f"{completed} succeeded, {failed} failed out of {len(file_list)} files"
        )

        # Fire code ontology extraction to populate graph from code analysis
        if completed > 0 and tenant_id:
            try:
                from app.tasks.ontology_tasks import extract_code_ontology_entities
                extract_code_ontology_entities.delay(repo_id, tenant_id)
                logger.info(
                    f"Repo {repo_id} analysis complete — dispatched code ontology extraction. "
                    f"Concepts matching BRD entities will be cross-referenced (source_type='both')."
                )
            except Exception as ontology_err:
                logger.warning(f"Failed to dispatch code ontology task (non-critical): {ontology_err}")

            # Dispatch Reduce Phase: synthesize per-file analyses into System Architecture
            try:
                repo_synthesis_task.delay(repo_id, tenant_id)
                logger.info(f"Repo {repo_id}: dispatched synthesis task (Reduce Phase)")
            except Exception as synth_err:
                logger.warning(f"Failed to dispatch synthesis task (non-critical): {synth_err}")

        return {
            "status": final_status,
            "repo_id": repo_id,
            "completed": completed,
            "failed": failed,
            "total": len(file_list),
        }

    except Exception as e:
        logger.error(f"REPO_AGENT failed for repo {repo_id}: {e}")
        try:
            crud.repository.update_analysis_progress(
                db=db, repo_id=repo_id, tenant_id=tenant_id,
                analyzed_files=0, status="failed",
                error_message=str(e)
            )
        except Exception:
            pass
        return {"status": "failed", "repo_id": repo_id, "error": str(e)}
    finally:
        if db.is_active:
            db.commit()
        db.close()


# ============================================================
# REPOSITORY SYNTHESIS — "REDUCE PHASE" (SPRINT 4)
# Combines per-file analyses into a System Architecture document
# ============================================================

@celery_app.task(name="repo_synthesis_task", bind=True, max_retries=1)
def repo_synthesis_task(self, repo_id: int, tenant_id: int):
    """
    Reduce Phase: After all files in a repository have been individually analyzed,
    synthesize their analyses into a single System Architecture document.

    Groups files by architectural layer (Controller, Service, Model, etc.),
    builds per-layer compact summaries, then feeds them into a REPOSITORY_SYNTHESIS
    prompt for a holistic architecture view.
    """
    logger.info(f"REPO_SYNTHESIS started for repo_id={repo_id}, tenant_id={tenant_id}")

    db = SessionLocal()
    try:
        repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
        if not repo:
            logger.error(f"Repo synthesis: Repository {repo_id} not found")
            return {"status": "error", "reason": "repo_not_found"}

        # Mark synthesis as running
        crud.repository.update(db, db_obj=repo, obj_in={"synthesis_status": "running"})

        # Gather all completed components for this repo
        from app.models.code_component import CodeComponent
        components = db.query(CodeComponent).filter(
            CodeComponent.repository_id == repo_id,
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.analysis_status == "completed",
            CodeComponent.structured_analysis.isnot(None),
        ).all()

        if not components:
            logger.warning(f"Repo synthesis: No completed components for repo {repo_id}")
            crud.repository.update(db, db_obj=repo, obj_in={
                "synthesis_status": "failed",
                "synthesis_data": {"error": "No completed file analyses to synthesize"}
            })
            return {"status": "skipped", "reason": "no_completed_components"}

        # Group files by architectural layer using file_type from structured_analysis
        layers = {}
        for comp in components:
            sa_data = comp.structured_analysis or {}
            lang_info = sa_data.get("language_info", {})
            file_type = lang_info.get("file_type", "Other")
            if file_type not in layers:
                layers[file_type] = []
            layers[file_type].append({
                "name": comp.name,
                "summary": (comp.summary or "")[:300],
                "language": lang_info.get("primary_language", "Unknown"),
                "framework": lang_info.get("framework", ""),
                "business_rules_count": len(sa_data.get("business_rules", [])),
                "api_contracts_count": len(sa_data.get("api_contracts", [])),
                "components_count": len(sa_data.get("components", [])),
                "key_components": [
                    c.get("name", "") for c in sa_data.get("components", [])[:5]
                ],
                "dependencies": sa_data.get("dependencies", [])[:10],
                "patterns": sa_data.get("patterns_and_architecture", {}).get("design_patterns", []),
                "security_patterns_count": len(sa_data.get("security_patterns", [])),
            })

        # Build layer summaries text
        layer_summaries_parts = []
        for layer_name, files in sorted(layers.items()):
            part = f"\n### Layer: {layer_name} ({len(files)} files)\n"
            for f in files:
                part += f"- **{f['name']}** ({f['language']}"
                if f['framework']:
                    part += f"/{f['framework']}"
                part += f"): {f['summary']}\n"
                if f['key_components']:
                    part += f"  Components: {', '.join(f['key_components'])}\n"
                if f['business_rules_count'] > 0:
                    part += f"  Business rules: {f['business_rules_count']}\n"
                if f['api_contracts_count'] > 0:
                    part += f"  API endpoints: {f['api_contracts_count']}\n"
                if f['patterns']:
                    part += f"  Patterns: {', '.join(f['patterns'][:5])}\n"
            layer_summaries_parts.append(part)

        layer_summaries_text = "\n".join(layer_summaries_parts)

        # Call AI for synthesis
        from app.services.ai.prompt_manager import prompt_manager, PromptType
        from app.services.ai.provider_router import provider_router

        prompt = prompt_manager.get_prompt(
            PromptType.REPOSITORY_SYNTHESIS,
            repo_name=repo.name,
            total_files=len(components),
            layer_count=len(layers),
            layer_summaries=layer_summaries_text,
        )

        response = _run_async(provider_router.generate_content(prompt))
        response_text = response.text if hasattr(response, 'text') else str(response)

        # Extract token usage for cost tracking
        from app.services.ai.gemini import gemini_service
        tokens = gemini_service.extract_token_usage(response)

        # Parse JSON response
        try:
            synthesis_data = json.loads(response_text)
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
                synthesis_data = json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse synthesis JSON for repo {repo_id}: {e}")
                synthesis_data = {
                    "system_overview": f"Synthesis completed but JSON parsing failed for {repo.name}",
                    "architecture": {"style": "Unknown", "layers": [], "patterns": []},
                    "technology_stack": {"languages": [], "frameworks": [], "databases": []},
                    "_parse_error": str(e),
                }

        # Add metadata
        synthesis_data["_metadata"] = {
            "total_files_synthesized": len(components),
            "layers_detected": list(layers.keys()),
            "input_tokens": tokens.get("input_tokens", 0),
            "output_tokens": tokens.get("output_tokens", 0),
            "thinking_tokens": tokens.get("thinking_tokens", 0),
        }

        # Persist synthesis
        crud.repository.update(db, db_obj=repo, obj_in={
            "synthesis_data": synthesis_data,
            "synthesis_status": "completed",
        })

        # Cost tracking (using actual token counts, NOT text-based counting)
        from app.services.cost_service import cost_service
        cost_data = cost_service.calculate_cost_from_actual_tokens(
            input_tokens=tokens.get("input_tokens", 0),
            output_tokens=tokens.get("output_tokens", 0),
            thinking_tokens=tokens.get("thinking_tokens", 0),
        )
        cost_inr = cost_data.get("cost_inr", 0)

        if cost_inr > 0:
            try:
                from app.services.billing_enforcement_service import billing_enforcement_service
                billing_enforcement_service.deduct_cost(
                    db=db, tenant_id=tenant_id, cost_inr=cost_inr,
                    description=f"Repository synthesis: {repo.name}"
                )
            except Exception as billing_err:
                logger.warning(f"Synthesis billing deduction failed (non-critical): {billing_err}")

            try:
                crud.usage_log.log_usage(
                    db=db,
                    tenant_id=tenant_id,
                    user_id=None,
                    feature_type="code_analysis",
                    operation="repository_synthesis",
                    model_used="gemini-2.5-flash",
                    input_tokens=tokens.get("input_tokens", 0),
                    output_tokens=tokens.get("output_tokens", 0) + tokens.get("thinking_tokens", 0),
                    cost_usd=cost_data.get("cost_usd", 0),
                    cost_inr=cost_inr,
                )
            except Exception as log_err:
                logger.warning(f"Synthesis usage logging failed (non-critical): {log_err}")

        logger.info(
            f"REPO_SYNTHESIS completed for repo {repo_id}: "
            f"{len(components)} files across {len(layers)} layers synthesized. "
            f"Cost: INR {cost_inr:.2f}"
        )

        return {
            "status": "completed",
            "repo_id": repo_id,
            "files_synthesized": len(components),
            "layers": list(layers.keys()),
        }

    except Exception as e:
        logger.error(f"REPO_SYNTHESIS failed for repo {repo_id}: {e}")
        try:
            repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
            if repo:
                crud.repository.update(db, db_obj=repo, obj_in={
                    "synthesis_status": "failed",
                    "synthesis_data": {"error": str(e)},
                })
        except Exception:
            pass
        try:
            self.retry(countdown=60)
        except self.MaxRetriesExceededError:
            logger.error(f"REPO_SYNTHESIS permanently failed for repo {repo_id}")
        return {"status": "failed", "repo_id": repo_id, "error": str(e)}
    finally:
        if db.is_active:
            db.commit()
        db.close()


# ============================================================
# WEBHOOK-TRIGGERED INCREMENTAL ANALYSIS (ADHOC-09)
# ============================================================

@celery_app.task(name="webhook_triggered_analysis", bind=True, max_retries=1)
def webhook_triggered_analysis(
    self, repo_id: int, tenant_id: int, changed_files: list,
    branch: str = "", commit_hash: str = ""
):
    """
    Incremental analysis triggered by a git webhook push event.
    Only re-analyzes files that changed, not the entire repo.
    """
    logger.info(
        f"WEBHOOK_ANALYSIS started for repo {repo_id}: "
        f"{len(changed_files)} files changed (branch={branch}, commit={commit_hash})"
    )

    db = SessionLocal()
    try:
        repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
        if not repo:
            logger.error(f"Webhook analysis: repo {repo_id} not found")
            return {"status": "error", "reason": "repo_not_found"}

        from app.models.code_component import CodeComponent

        completed = 0
        for file_path in changed_files:
            filename = file_path.split("/")[-1]

            # Find existing component for this file
            component = db.query(CodeComponent).filter(
                CodeComponent.repository_id == repo_id,
                CodeComponent.tenant_id == tenant_id,
                CodeComponent.name == filename,
            ).first()

            if not component:
                logger.info(f"Webhook: {file_path} not tracked, skipping")
                continue

            # Fetch updated content
            raw_url = component.location
            if not raw_url:
                continue

            code_content = _fetch_file_content(raw_url)
            if not code_content:
                continue

            # Detect language from file extension
            ext = file_path.rsplit(".", 1)[-1] if "." in file_path else ""
            lang_map = {"py": "python", "js": "javascript", "ts": "typescript", "java": "java", "go": "go"}
            language = lang_map.get(ext, "")

            import time
            result = static_analysis_worker(
                component.id, tenant_id, code_content,
                repo_name=repo.name, file_path=file_path, language=language,
            )

            if result.get("status") == "completed":
                completed += 1

            time.sleep(4)  # Rate limiting

        # Update repo last_analyzed_commit
        if commit_hash:
            crud.repository.update(
                db, db_obj=repo, obj_in={"last_analyzed_commit": commit_hash}
            )

        # Trigger incremental cross-graph mapping for changed concepts
        if completed > 0:
            try:
                from app.tasks.ontology_tasks import extract_code_ontology_entities
                extract_code_ontology_entities.delay(repo_id, tenant_id)
            except Exception as e:
                logger.warning(f"Webhook: ontology task dispatch failed: {e}")

        logger.info(f"WEBHOOK_ANALYSIS completed: {completed}/{len(changed_files)} files re-analyzed")
        return {"status": "completed", "re_analyzed": completed, "total_changed": len(changed_files)}

    except Exception as e:
        logger.error(f"WEBHOOK_ANALYSIS failed for repo {repo_id}: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        if db.is_active:
            db.commit()
        db.close()


def _fetch_file_content(url: str) -> Optional[str]:
    """Fetch raw file content from a URL (e.g., GitHub raw URL)."""
    if not url:
        return None
    try:
        import httpx
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None
