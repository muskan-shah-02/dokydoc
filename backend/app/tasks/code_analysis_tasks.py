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

            # Call Gemini — use enhanced analysis when we have repo context
            from app.services.ai.gemini import gemini_service
            if not gemini_service:
                raise RuntimeError("GeminiService not available")

            if repo_name:
                # Enhanced analysis with business rules, API contracts, etc.
                analysis_result = asyncio.run(
                    gemini_service.call_gemini_for_enhanced_analysis(
                        code_content,
                        repo_name=repo_name,
                        file_path=file_path,
                        language=language
                    )
                )
            else:
                # Fallback to basic analysis for standalone components
                analysis_result = asyncio.run(
                    gemini_service.call_gemini_for_code_analysis(code_content)
                )

            # Cache the result
            cache_service.set_cached_analysis(
                content=code_content,
                analysis_type=cache_type,
                result=analysis_result,
                ttl_seconds=2592000  # 30 days
            )

        # Delta analysis: compare with previous analysis if it exists
        new_analysis = analysis_result.get("structured_analysis")
        new_hash = _hash_analysis(new_analysis)
        delta_result = None

        if previous_analysis and previous_hash and new_hash != previous_hash:
            logger.info(f"Analysis changed for component {component_id} — running delta analysis")
            try:
                delta_result = asyncio.run(
                    gemini_service.call_gemini_for_delta_analysis(
                        file_path=file_path or component.name,
                        previous_analysis=previous_analysis,
                        current_analysis=new_analysis
                    )
                )
                logger.info(
                    f"Delta analysis complete: has_changes={delta_result.get('has_changes')}, "
                    f"risk={delta_result.get('risk_assessment', {}).get('overall_risk', 'unknown')}"
                )
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

                # Run enhanced analysis with repo context + language
                import time
                result = static_analysis_worker(
                    component.id, tenant_id, code_content,
                    repo_name=repo.name,
                    file_path=file_path,
                    language=file_language
                )

                if result.get("status") == "completed":
                    completed += 1
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
