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
from datetime import datetime
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


def _build_error_with_solution(error_str: str, file_path: str) -> str:
    """
    Build a user-friendly error message with actionable solution steps.
    Classifies errors and provides resolution guidance.
    """
    err_lower = error_str.lower()

    # Rate limiting / quota errors
    if any(k in err_lower for k in ["429", "rate limit", "quota", "resource exhausted", "too many requests"]):
        return (
            f"Analysis failed: AI rate limit exceeded.\n"
            f"Solution: Click 'Retry' — the system will automatically space out requests. "
            f"If this persists, wait 1-2 minutes before retrying."
        )

    # Timeout errors
    if any(k in err_lower for k in ["timeout", "timed out", "deadline exceeded"]):
        return (
            f"Analysis failed: Request timed out.\n"
            f"Solution: This file may be too large for single-pass analysis. "
            f"Click 'Retry' to try again. If it persists, the file may need to be split."
        )

    # Content too large
    if any(k in err_lower for k in ["too large", "max_tokens", "content_length", "payload too large"]):
        return (
            f"Analysis failed: File content exceeds AI model limits.\n"
            f"Solution: This file ({file_path}) is very large. Consider splitting it into "
            f"smaller modules. Click 'Retry' to attempt with truncated content."
        )

    # Network / connection errors
    if any(k in err_lower for k in ["connection", "network", "dns", "ssl", "refused", "unreachable"]):
        return (
            f"Analysis failed: Network connection error.\n"
            f"Solution: Check your internet connection and API key configuration. "
            f"Click 'Retry' to try again."
        )

    # Authentication / API key errors
    if any(k in err_lower for k in ["401", "403", "unauthorized", "forbidden", "api key", "invalid key"]):
        return (
            f"Analysis failed: Authentication error with AI provider.\n"
            f"Solution: Check that your Gemini API key is valid and has sufficient permissions. "
            f"Contact admin if the issue persists."
        )

    # JSON parsing errors (AI returned invalid response)
    if any(k in err_lower for k in ["json", "parse", "decode", "unexpected token", "invalid json"]):
        return (
            f"Analysis failed: AI returned an invalid response format.\n"
            f"Solution: Click 'Retry' — this is usually a transient issue. The AI occasionally "
            f"returns malformed output that resolves on retry."
        )

    # Billing / balance errors
    if any(k in err_lower for k in ["billing", "balance", "insufficient", "afford"]):
        return (
            f"Analysis failed: Insufficient billing balance.\n"
            f"Solution: Add credits to your account in Settings > Billing, then retry."
        )

    # File fetch errors
    if any(k in err_lower for k in ["404", "not found", "fetch", "download"]):
        return (
            f"Analysis failed: Could not fetch file content from repository.\n"
            f"Solution: Verify the file still exists in the repository and the URL is accessible. "
            f"Re-upload the repository if files have been moved."
        )

    # Server errors
    if any(k in err_lower for k in ["500", "502", "503", "504", "internal server", "bad gateway", "service unavailable"]):
        return (
            f"Analysis failed: AI service temporarily unavailable.\n"
            f"Solution: Click 'Retry' — this is a temporary server issue that usually resolves quickly."
        )

    # Generic fallback
    return (
        f"Analysis failed: {error_str[:300]}\n"
        f"Solution: Click 'Retry' to re-analyze this file. If the error persists, "
        f"check the file content for unusual formatting or encoding issues."
    )


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

        # Update status + start timestamp
        from datetime import datetime as dt
        analysis_start = dt.utcnow()
        crud.code_component.update(
            db, db_obj=component, obj_in={
                "analysis_status": "processing",
                "analysis_started_at": analysis_start,
            }
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
                        language=language,
                        tenant_id=tenant_id,
                    )
                )
            else:
                # Fallback to basic analysis for standalone components
                analysis_result = _run_async(
                    provider_router.analyze_code(code_content, tenant_id=tenant_id)
                )

            # Cache the result
            cache_service.set_cached_analysis(
                content=code_content,
                analysis_type=cache_type,
                result=analysis_result,
                ttl_seconds=2592000  # 30 days
            )

            # Cost tracking: NOW HANDLED CENTRALLY by generate_content() in gemini.py
            # The auto-billing in generate_content() deducts cost + logs to usage_logs
            # automatically when tenant_id is passed through provider_router.
            # We only need to calculate cost here for the component's own ai_cost_inr field.

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
                        current_analysis=new_analysis,
                        tenant_id=tenant_id,
                    )
                )
                logger.info(
                    f"Delta analysis complete: has_changes={delta_result.get('has_changes')}, "
                    f"risk={delta_result.get('risk_assessment', {}).get('overall_risk', 'unknown')}"
                )
                # Delta cost tracking: NOW HANDLED CENTRALLY by generate_content() auto-billing
            except Exception as delta_err:
                logger.warning(f"Delta analysis failed (non-critical): {delta_err}")

        # Persist results + cost/timing data
        analysis_end = dt.utcnow()
        token_usage_final = analysis_result.get("_token_usage", {})
        total_cost_inr = 0
        try:
            if token_usage_final and token_usage_final.get("input_tokens", 0) > 0:
                from app.services.cost_service import cost_service as _cs
                _cost = _cs.calculate_cost_from_actual_tokens(
                    input_tokens=token_usage_final.get("input_tokens", 0),
                    output_tokens=token_usage_final.get("output_tokens", 0),
                    thinking_tokens=token_usage_final.get("thinking_tokens", 0),
                )
                total_cost_inr = _cost.get("cost_inr", 0)
        except Exception:
            pass

        update_data = {
            "summary": analysis_result.get("summary"),
            "structured_analysis": new_analysis,
            "analysis_status": "completed",
            "previous_analysis_hash": previous_hash if previous_analysis else None,
            "analysis_completed_at": analysis_end,
            "ai_cost_inr": total_cost_inr,  # Always save (0 for cached, >0 for API calls)
            "token_count_input": token_usage_final.get("input_tokens", 0) if token_usage_final else 0,
            "token_count_output": token_usage_final.get("output_tokens", 0) if token_usage_final else 0,
        }
        if delta_result:
            update_data["analysis_delta"] = delta_result

        crud.code_component.update(db, db_obj=component, obj_in=update_data)

        # Extract ontology concepts inline (source_type="code") so Code tab
        # populates immediately — no need to wait for full repo completion
        if new_analysis and tenant_id:
            try:
                from app.services.code_analysis_service import code_analysis_service
                code_analysis_service._extract_ontology_from_analysis(
                    db, structured_analysis=new_analysis,
                    component_name=file_path or component.name,
                    tenant_id=tenant_id,
                    source_component_id=component.id,
                )
            except Exception as onto_err:
                logger.warning(f"Inline ontology extraction failed (non-critical): {onto_err}")

        logger.info(f"ANALYSIS_WORKER completed for component {component_id}")
        return {
            "status": "completed",
            "component_id": component_id,
            "has_delta": delta_result is not None and delta_result.get("has_changes", False),
        }

    except Exception as e:
        logger.error(f"ANALYSIS_WORKER failed for component {component_id}: {e}")
        error_str = str(e)
        error_summary = _build_error_with_solution(error_str, file_path or "unknown")
        try:
            comp = crud.code_component.get(db=db, id=component_id, tenant_id=tenant_id)
            if comp:
                crud.code_component.update(db, db_obj=comp, obj_in={
                    "analysis_status": "failed",
                    "summary": error_summary
                })
        except Exception:
            pass

        try:
            self.retry(countdown=30 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(f"ANALYSIS_WORKER permanently failed for component {component_id}")

        return {"status": "failed", "component_id": component_id, "error": error_str}
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
                    # Re-analysis: check if content actually changed before re-analyzing
                    component = existing_component
                    content_hash = hashlib.sha256(code_content.encode()).hexdigest()
                    prev_hash = component.previous_analysis_hash or ""

                    # Also check cache: if content is identical to last analysis, skip AI call
                    from app.services.cache_service import cache_service as _cache
                    cache_type = "enhanced_analysis" if repo.name else "code_analysis"
                    cached_result = _cache.get_cached_analysis(content=code_content, analysis_type=cache_type)

                    if cached_result and component.analysis_status == "completed" and component.structured_analysis:
                        # Content unchanged and previous analysis exists — skip entirely
                        logger.info(
                            f"SKIP re-analysis for {file_path} (component {component.id}) "
                            f"— content unchanged (cache hit), reusing existing analysis"
                        )
                        completed += 1
                        # Still contribute to cross-file context
                        if component.summary:
                            sa = component.structured_analysis or {}
                            repo_context.append({
                                "path": file_path,
                                "summary": (component.summary or "")[:200],
                                "file_type": sa.get("language_info", {}).get("file_type", "Unknown"),
                            })
                        crud.repository.update_analysis_progress(
                            db=db, repo_id=repo_id, tenant_id=tenant_id,
                            analyzed_files=completed + failed
                        )
                        continue

                    logger.info(f"Re-analyzing existing component {component.id} for {file_path} (content changed or no cache)")
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
# BATCH RETRY FAILED COMPONENTS (RATE-LIMITED)
# ============================================================

@celery_app.task(name="batch_retry_failed_components", bind=True, max_retries=0)
def batch_retry_failed_components(self, repo_id: int, tenant_id: int, component_ids: list):
    """
    Sequential retry of failed components with 4s rate-limiting between calls.
    This prevents flooding Gemini's 15 RPM limit when retrying many files at once.
    """
    import time
    logger.info(
        f"BATCH_RETRY started for repo {repo_id}: {len(component_ids)} components"
    )

    db = SessionLocal()
    try:
        repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
        repo_name = repo.name if repo else ""
        completed = 0
        failed = 0

        for comp_id in component_ids:
            try:
                component = crud.code_component.get(db=db, id=comp_id, tenant_id=tenant_id)
                if not component:
                    failed += 1
                    continue

                # Fetch file content
                code_content = ""
                try:
                    import httpx
                    resp = httpx.get(component.location, timeout=30, follow_redirects=True)
                    code_content = resp.text if resp.status_code == 200 else ""
                except Exception:
                    pass

                if not code_content:
                    crud.code_component.update(
                        db, db_obj=component,
                        obj_in={
                            "analysis_status": "failed",
                            "summary": "Could not fetch file content from URL.",
                        }
                    )
                    failed += 1
                    continue

                # Detect language
                ext = component.name.rsplit(".", 1)[-1].lower() if "." in component.name else ""
                lang_map = {
                    "py": "python", "js": "javascript", "ts": "typescript",
                    "tsx": "typescript", "jsx": "javascript", "java": "java",
                    "go": "go", "rs": "rust", "rb": "ruby",
                }
                language = lang_map.get(ext, ext)

                # Run analysis synchronously (same as repo_analysis_task does)
                result = static_analysis_worker(
                    comp_id, tenant_id, code_content,
                    repo_name=repo_name,
                    file_path=component.name,
                    language=language,
                )

                if result.get("status") == "completed":
                    completed += 1
                else:
                    failed += 1

                # Update repo progress in real-time so the UI reflects progress
                try:
                    from app.models.code_component import CodeComponent as CC
                    all_comps = (
                        db.query(CC)
                        .filter(CC.repository_id == repo_id, CC.tenant_id == tenant_id)
                        .all()
                    )
                    done = sum(1 for c in all_comps if c.analysis_status in ("completed", "failed"))
                    crud.repository.update_analysis_progress(
                        db, repo_id=repo_id, tenant_id=tenant_id,
                        analyzed_files=done, status="analyzing",
                    )
                except Exception:
                    pass

                # Rate limit: 4s between analyses
                time.sleep(4)

            except Exception as e:
                logger.error(f"Batch retry failed for component {comp_id}: {e}")
                failed += 1

        # UPDATE REPO PROGRESS COUNTER — fixes the stale 28/248 issue
        # After batch retry, recount ALL components (not just retried ones)
        if repo:
            try:
                from app.models.code_component import CodeComponent as CC
                all_components = (
                    db.query(CC)
                    .filter(CC.repository_id == repo_id, CC.tenant_id == tenant_id)
                    .all()
                )
                total_count = len(all_components)
                completed_count = sum(
                    1 for c in all_components if c.analysis_status == "completed"
                )
                failed_count = sum(
                    1 for c in all_components if c.analysis_status == "failed"
                )
                analyzed_count = completed_count + failed_count

                new_status = "completed" if analyzed_count >= total_count else "analyzing"
                crud.repository.update_analysis_progress(
                    db,
                    repo_id=repo_id,
                    tenant_id=tenant_id,
                    analyzed_files=analyzed_count,
                    total_files=total_count,
                    status=new_status,
                )
                logger.info(
                    f"BATCH_RETRY progress update: {analyzed_count}/{total_count} "
                    f"(completed={completed_count}, failed={failed_count})"
                )
            except Exception as progress_err:
                logger.warning(f"Failed to update repo progress after batch retry: {progress_err}")

        logger.info(
            f"BATCH_RETRY completed for repo {repo_id}: "
            f"{completed} succeeded, {failed} failed out of {len(component_ids)}"
        )
        return {
            "status": "completed",
            "repo_id": repo_id,
            "completed": completed,
            "failed": failed,
            "total": len(component_ids),
        }
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

        response = _run_async(provider_router.generate_content(
            prompt, tenant_id=tenant_id, operation="repository_synthesis",
        ))
        response_text = response.text if hasattr(response, 'text') else str(response)

        # Extract token usage for metadata (billing auto-handled by generate_content)
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

        # Cost tracking: NOW HANDLED CENTRALLY by generate_content() auto-billing.
        # No manual deduction/logging needed — generate_content() already deducted
        # and logged to usage_logs when tenant_id was passed through provider_router.

        logger.info(
            f"REPO_SYNTHESIS completed for repo {repo_id}: "
            f"{len(components)} files across {len(layers)} layers synthesized. "
            f"Tokens: {tokens.get('input_tokens', 0)} in / {tokens.get('output_tokens', 0)} out"
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

    Sprint 4 Phase 4: Routes based on branch type:
    - Main branches (main/master/develop) → permanent PostgreSQL write (existing flow)
    - Feature branches → ephemeral Redis preview (branch_preview_extraction)
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

        # Determine if this is a main branch or feature branch
        default_branch = getattr(repo, "default_branch", None) or "main"
        main_branches = {"main", "master", "develop", default_branch}
        is_main = branch in main_branches

        if not is_main and branch:
            # Feature branch → dispatch ephemeral preview extraction
            logger.info(
                f"Webhook: feature branch '{branch}' detected — routing to preview extraction"
            )
            branch_preview_extraction.delay(
                repo_id=repo_id,
                tenant_id=tenant_id,
                branch=branch,
                commit_hash=commit_hash,
                changed_files=changed_files,
            )
            return {
                "status": "dispatched_preview",
                "branch": branch,
                "files": len(changed_files),
            }

        # Main branch → permanent write to PostgreSQL (existing flow)
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


def _detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    lang_map = {
        "py": "python", "js": "javascript", "ts": "typescript",
        "tsx": "typescript", "jsx": "javascript",
        "java": "java", "go": "go", "rs": "rust",
        "rb": "ruby", "cs": "csharp", "php": "php",
    }
    return lang_map.get(ext, "")


def _extract_owner_repo(repo_url: str) -> str:
    """Extract 'owner/repo' from a GitHub URL."""
    url = repo_url.rstrip("/").rstrip(".git")
    parts = url.split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return ""


def _extract_entities_from_structured(structured: dict, file_path: str) -> tuple:
    """
    Extract ontology entities and relationships from a structured_analysis result.
    Returns (entities_list, relationships_list) for branch preview storage.
    """
    entities = []
    relationships = []

    # Extract from components
    for comp in structured.get("components", []):
        name = comp.get("name", "")
        if name:
            entities.append({
                "name": name,
                "type": comp.get("type", "Entity"),
                "confidence": 0.85,
                "context": file_path,
            })

    # Extract from business_rules
    for rule in structured.get("business_rules", []):
        name = rule.get("name", "") or rule.get("rule_name", "")
        if name:
            entities.append({
                "name": name,
                "type": "Process",
                "confidence": 0.8,
                "context": file_path,
            })

    # Extract from api_contracts
    for api in structured.get("api_contracts", []):
        endpoint = api.get("endpoint", "") or api.get("path", "")
        if endpoint:
            entities.append({
                "name": endpoint,
                "type": "Service",
                "confidence": 0.9,
                "context": file_path,
            })

    # Extract from data_models
    for model in structured.get("data_models", []):
        name = model.get("name", "") or model.get("model_name", "")
        if name:
            entities.append({
                "name": name,
                "type": "Entity",
                "confidence": 0.9,
                "context": file_path,
            })
            # Relationships from model fields referencing other models
            for field in model.get("fields", []):
                ref = field.get("references", "") or field.get("foreign_key", "")
                if ref:
                    relationships.append({
                        "source": name,
                        "target": ref,
                        "type": "references",
                        "confidence": 0.85,
                    })

    # Extract from dependencies
    for dep in structured.get("dependencies", []):
        if isinstance(dep, dict):
            source = dep.get("from", "") or dep.get("source", "")
            target = dep.get("to", "") or dep.get("target", "") or dep.get("name", "")
            if source and target:
                relationships.append({
                    "source": source,
                    "target": target,
                    "type": dep.get("type", "depends_on"),
                    "confidence": 0.75,
                })

    return entities, relationships


# ============================================================
# BRANCH PREVIEW EXTRACTION (Sprint 4 Phase 4)
# Ephemeral analysis for feature branches → Redis, NOT PostgreSQL
# ============================================================

@celery_app.task(name="branch_preview_extraction", bind=True, max_retries=2)
def branch_preview_extraction(
    self, repo_id: int, tenant_id: int, branch: str,
    commit_hash: str = "", changed_files: list = None
):
    """
    Analyze changed files on a feature branch and store extracted
    concepts/relationships in Redis as an ephemeral preview.
    Does NOT write to PostgreSQL — preview auto-expires after 7 days.
    """
    changed_files = changed_files or []
    logger.info(
        f"BRANCH_PREVIEW started for repo {repo_id}, branch={branch}: "
        f"{len(changed_files)} files"
    )

    db = SessionLocal()
    try:
        repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
        if not repo:
            logger.error(f"Branch preview: repo {repo_id} not found")
            return {"status": "error", "reason": "repo_not_found"}

        entities = []
        relationships = []

        for file_path in changed_files:
            try:
                # Build raw URL for the branch file
                owner_repo = _extract_owner_repo(repo.url)
                if owner_repo:
                    raw_url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/{file_path}"
                else:
                    # Fallback: try to adapt existing component URL
                    from app.models.code_component import CodeComponent
                    comp = db.query(CodeComponent).filter(
                        CodeComponent.repository_id == repo_id,
                        CodeComponent.tenant_id == tenant_id,
                        CodeComponent.name == file_path.split("/")[-1],
                    ).first()
                    raw_url = comp.location if comp else None

                if not raw_url:
                    logger.warning(f"Branch preview: cannot build URL for {file_path}")
                    continue

                code_content = _fetch_file_content(raw_url)
                if not code_content:
                    continue

                # Run AI analysis (same as enhanced analysis)
                from app.services.ai.provider_router import provider_router
                language = _detect_language(file_path)

                analysis_result = _run_async(
                    provider_router.analyze_code_enhanced(
                        code_content,
                        repo_name=repo.name,
                        file_path=file_path,
                        language=language,
                    )
                )

                # Extract inline ontology concepts from structured_analysis
                structured = analysis_result.get("structured_analysis", {})
                if structured:
                    file_entities, file_rels = _extract_entities_from_structured(
                        structured, file_path
                    )
                    entities.extend(file_entities)
                    relationships.extend(file_rels)

                import time
                time.sleep(4)  # Rate limiting

            except Exception as file_err:
                logger.warning(f"Branch preview: failed to process {file_path}: {file_err}")

        # Store in Redis (NOT PostgreSQL)
        from app.services.cache_service import cache_service
        cache_service.set_branch_preview(
            tenant_id=tenant_id,
            repo_id=repo_id,
            branch=branch,
            preview_data={
                "branch": branch,
                "commit_hash": commit_hash,
                "extracted_at": datetime.utcnow().isoformat(),
                "entities": entities,
                "relationships": relationships,
                "changed_files": changed_files,
            },
        )

        logger.info(
            f"BRANCH_PREVIEW completed: {repo.name}/{branch} — "
            f"{len(entities)} entities, {len(relationships)} relationships"
        )
        return {
            "status": "completed",
            "branch": branch,
            "entities": len(entities),
            "relationships": len(relationships),
        }

    except Exception as e:
        logger.error(f"BRANCH_PREVIEW failed for repo {repo_id}/{branch}: {e}")
        try:
            self.retry(countdown=30 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(f"BRANCH_PREVIEW permanently failed for {repo_id}/{branch}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


# ============================================================
# PROMOTE BRANCH PREVIEW (Sprint 4 Phase 4)
# When a PR is merged, write ephemeral Redis preview → PostgreSQL
# ============================================================

@celery_app.task(name="promote_branch_preview", bind=True, max_retries=1)
def promote_branch_preview(
    self, repo_id: int, tenant_id: int, branch: str
):
    """
    When a PR is merged, take the ephemeral Redis preview and write
    its concepts/relationships permanently to PostgreSQL.
    Then clean up the Redis key.
    """
    logger.info(f"PROMOTE_PREVIEW started: repo {repo_id}, branch={branch}")

    from app.services.cache_service import cache_service
    preview = cache_service.get_branch_preview(
        tenant_id=tenant_id, repo_id=repo_id, branch=branch
    )

    if not preview:
        logger.info(f"No preview to promote for {branch}")
        return {"status": "skipped", "reason": "no_preview"}

    db = SessionLocal()
    try:
        from app.services.business_ontology_service import business_ontology_service

        # Resolve initiative_id for this repository
        initiative_id = business_ontology_service._resolve_initiative_for_repository(
            db=db, repo_id=repo_id, tenant_id=tenant_id
        )

        # Ingest entities into PostgreSQL as permanent concepts
        for entity in preview.get("entities", []):
            try:
                business_ontology_service.get_or_create_concept(
                    db=db,
                    name=entity.get("name", ""),
                    concept_type=entity.get("type", "Entity"),
                    tenant_id=tenant_id,
                    description=f"From branch merge: {branch}",
                    confidence_score=entity.get("confidence", 0.8),
                    source_type="code",
                    initiative_id=initiative_id,
                )
            except Exception as e:
                logger.warning(f"Promote preview: failed to create concept {entity.get('name')}: {e}")

        # Ingest relationships
        for rel in preview.get("relationships", []):
            try:
                source_name = rel.get("source", "")
                target_name = rel.get("target", "")
                if source_name and target_name:
                    source_concept = crud.ontology_concept.get_by_name(
                        db=db, name=source_name, tenant_id=tenant_id
                    )
                    target_concept = crud.ontology_concept.get_by_name(
                        db=db, name=target_name, tenant_id=tenant_id
                    )
                    if source_concept and target_concept:
                        crud.ontology_relationship.create_if_not_exists(
                            db=db,
                            source_concept_id=source_concept.id,
                            target_concept_id=target_concept.id,
                            relationship_type=rel.get("type", "relates_to"),
                            tenant_id=tenant_id,
                            confidence_score=rel.get("confidence", 0.75),
                        )
            except Exception as e:
                logger.warning(f"Promote preview: failed to create relationship: {e}")

        db.commit()

        # Clean up Redis
        cache_service.delete_branch_preview(
            tenant_id=tenant_id, repo_id=repo_id, branch=branch
        )

        logger.info(
            f"PROMOTE_PREVIEW completed: {branch} → "
            f"{len(preview.get('entities', []))} entities promoted to PostgreSQL"
        )

        # Trigger cross-graph mapping after promotion
        try:
            from app.tasks.ontology_tasks import extract_code_ontology_entities
            extract_code_ontology_entities.delay(repo_id, tenant_id)
        except Exception as e:
            logger.warning(f"Promote preview: ontology task dispatch failed: {e}")

        return {
            "status": "completed",
            "branch": branch,
            "entities_promoted": len(preview.get("entities", [])),
            "relationships_promoted": len(preview.get("relationships", [])),
        }

    except Exception as e:
        logger.error(f"PROMOTE_PREVIEW failed for {branch}: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        if db.is_active:
            db.commit()
        db.close()
