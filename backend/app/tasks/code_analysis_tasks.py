"""
SPRINT 3: Code Analysis Engine — Celery Workers (TASK-01)

Architecture:
  repo_analysis_task (orchestrator)
    └── for each file in repo:
           ├── static_analysis_worker  (structure, dependencies, patterns)
           └── semantic_analysis_worker (purpose, quality, domain concepts)

The Repo Agent scans a repository's files and creates CodeComponent records
for each, linking them back to the parent Repository via repository_id.
"""

import asyncio
import json
import httpx
from typing import Optional

from app.worker import celery_app
from app.db.session import SessionLocal
from app import crud
from app.core.logging import logger


# ============================================================
# STATIC ANALYSIS WORKER
# ============================================================

@celery_app.task(name="static_analysis_worker", bind=True, max_retries=2)
def static_analysis_worker(
    self, component_id: int, tenant_id: int, code_content: str
):
    """
    Worker: Runs structural / static analysis on a single file.
    Uses the existing Gemini CODE_ANALYSIS prompt to extract components,
    dependencies, patterns, etc.

    This is the same analysis that already existed for standalone code components,
    but now callable as a Celery sub-task within the repository pipeline.
    """
    logger.info(f"STATIC_WORKER started for component_id={component_id}")

    db = SessionLocal()
    try:
        component = crud.code_component.get(db=db, id=component_id, tenant_id=tenant_id)
        if not component:
            logger.error(f"Static worker: Component {component_id} not found")
            return {"status": "error", "reason": "component_not_found"}

        # Update status
        crud.code_component.update(
            db, db_obj=component, obj_in={"analysis_status": "processing"}
        )

        # Check cache first
        from app.services.cache_service import cache_service
        cached = cache_service.get_cached_analysis(
            content=code_content, analysis_type="code_analysis"
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

            # Call Gemini
            from app.services.ai.gemini import gemini_service
            if not gemini_service:
                raise RuntimeError("GeminiService not available")

            analysis_result = asyncio.run(
                gemini_service.call_gemini_for_code_analysis(code_content)
            )

            # Cache the result
            cache_service.set_cached_analysis(
                content=code_content,
                analysis_type="code_analysis",
                result=analysis_result,
                ttl_seconds=2592000  # 30 days
            )

        # Persist results
        crud.code_component.update(db, db_obj=component, obj_in={
            "summary": analysis_result.get("summary"),
            "structured_analysis": analysis_result.get("structured_analysis"),
            "analysis_status": "completed",
        })

        logger.info(f"STATIC_WORKER completed for component {component_id}")
        return {"status": "completed", "component_id": component_id}

    except Exception as e:
        logger.error(f"STATIC_WORKER failed for component {component_id}: {e}")
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
            logger.error(f"STATIC_WORKER permanently failed for component {component_id}")

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
    creates CodeComponent records, and dispatches static_analysis_worker
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

                # Create CodeComponent record linked to repository
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

                # Dispatch static analysis (synchronous call for rate limiting)
                # We call the worker function directly instead of .delay()
                # to respect the 15 RPM Gemini rate limit with sequential processing
                import time
                result = static_analysis_worker(component.id, tenant_id, code_content)

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

        # Fire ontology extraction for newly analyzed code if concepts are relevant
        if completed > 0 and tenant_id:
            try:
                from app.tasks.ontology_tasks import extract_ontology_entities
                # Ontology extraction runs per-document, not per-repo
                # This is handled at the component level in future iterations
                logger.info(f"Repo {repo_id} analysis complete — ontology will enrich on next document link")
            except Exception:
                pass

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
