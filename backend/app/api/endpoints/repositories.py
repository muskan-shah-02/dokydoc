"""
SPRINT 3: Repository Onboarding API Endpoints (API-02)

Provides endpoints for repository lifecycle:
  POST   /                   — Onboard a new repository
  GET    /                   — List all repositories
  GET    /{id}               — Get repository details + progress
  POST   /{id}/analyze       — Trigger analysis for a repository
  DELETE /{id}               — Delete repository and its components
  GET    /{id}/components    — List code components in a repository
"""

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.db.session import get_db
from app.schemas.repository import (
    RepositoryCreate, RepositoryUpdate, RepositoryResponse, RepositoryWithProgress
)
from app.core.logging import get_logger

logger = get_logger("api.repositories")

router = APIRouter()


# ============================================================
# REPOSITORY CRUD
# ============================================================

@router.get("/", response_model=List[RepositoryResponse])
def list_repositories(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    analysis_status: Optional[str] = Query(None, description="Filter by status"),
    initiative_id: Optional[int] = Query(None, description="Filter by initiative (project) ID"),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all repositories for the current tenant, optionally filtered by initiative."""
    if initiative_id:
        repos = crud.repository.get_by_initiative(
            db=db, initiative_id=initiative_id, tenant_id=tenant_id,
            skip=skip, limit=limit
        )
    elif analysis_status:
        repos = crud.repository.get_by_status(
            db=db, analysis_status=analysis_status, tenant_id=tenant_id,
            skip=skip, limit=limit
        )
    else:
        repos = crud.repository.get_multi(
            db=db, tenant_id=tenant_id, skip=skip, limit=limit
        )

    # Dynamically compute file counts from actual CodeComponent records
    # This prevents stale 54/282 counters — always reflects real DB state
    from app.models.code_component import CodeComponent
    from sqlalchemy import func
    for repo in repos:
        stats = db.query(
            func.count(CodeComponent.id).label("total"),
            func.count(CodeComponent.id).filter(
                CodeComponent.analysis_status.in_(["completed", "failed"])
            ).label("analyzed"),
        ).filter(
            CodeComponent.repository_id == repo.id,
            CodeComponent.tenant_id == tenant_id,
        ).first()

        if stats and stats.total > 0:
            repo.total_files = stats.total
            repo.analyzed_files = stats.analyzed
            # Also compute total AI cost from components
            cost_sum = db.query(func.sum(CodeComponent.ai_cost_inr)).filter(
                CodeComponent.repository_id == repo.id,
                CodeComponent.tenant_id == tenant_id,
                CodeComponent.ai_cost_inr.isnot(None),
            ).scalar()
            repo.total_ai_cost_inr = float(cost_sum) if cost_sum else 0

    return repos


@router.post("/", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
def onboard_repository(
    *,
    obj_in: RepositoryCreate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    initiative_id: Optional[int] = Query(None, description="Auto-link repo to initiative (project)"),
) -> Any:
    """
    Onboard a new repository. Checks for duplicate URLs within the tenant.
    Does NOT trigger analysis — use POST /{id}/analyze for that.
    SPRINT 4: Optional initiative_id to auto-link repo to a project.
    """
    # Dedup: if repo with same URL exists, update its branch & return it (upsert)
    existing = crud.repository.get_by_url(db=db, url=obj_in.url, tenant_id=tenant_id)
    if existing:
        update_fields = {}
        if obj_in.default_branch and obj_in.default_branch != existing.default_branch:
            update_fields["default_branch"] = obj_in.default_branch
            logger.info(
                f"Repository '{existing.name}' branch updated: "
                f"{existing.default_branch} → {obj_in.default_branch}"
            )
        if obj_in.name and obj_in.name != existing.name:
            update_fields["name"] = obj_in.name
        if obj_in.description and obj_in.description != existing.description:
            update_fields["description"] = obj_in.description
        if update_fields:
            crud.repository.update(db=db, db_obj=existing, obj_in=update_fields)
        return existing

    repo = crud.repository.create_with_owner(
        db=db, obj_in=obj_in, owner_id=current_user.id, tenant_id=tenant_id
    )
    logger.info(f"Repository '{repo.name}' onboarded by user {current_user.id} in tenant {tenant_id}")

    # Auto-link to initiative if specified
    if initiative_id:
        try:
            from app.schemas.initiative import InitiativeAssetCreate
            crud.initiative_asset.create_asset(
                db=db,
                obj_in=InitiativeAssetCreate(
                    initiative_id=initiative_id,
                    asset_type="REPOSITORY",
                    asset_id=repo.id,
                ),
                tenant_id=tenant_id
            )
            logger.info(f"Repository {repo.id} auto-linked to initiative {initiative_id}")
        except Exception as e:
            logger.warning(f"Failed to auto-link repository {repo.id} to initiative {initiative_id}: {e}")

    return repo


@router.get("/{repo_id}", response_model=RepositoryWithProgress)
def get_repository(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get repository details with analysis progress percentage."""
    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return RepositoryWithProgress.from_repo(repo)


@router.put("/{repo_id}", response_model=RepositoryResponse)
def update_repository(
    repo_id: int,
    *,
    obj_in: RepositoryUpdate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Update repository metadata (name, description, default_branch)."""
    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return crud.repository.update(db=db, db_obj=repo, obj_in=obj_in)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> None:
    """Delete a repository and cascade-delete its code components."""
    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Cascade: delete all code components linked to this repository
    from app.models.code_component import CodeComponent
    from app.models.ontology_concept import OntologyConcept

    # Get the component IDs before deleting so we can clean up ontology
    component_ids = [
        row.id for row in db.query(CodeComponent.id).filter(
            CodeComponent.repository_id == repo_id,
            CodeComponent.tenant_id == tenant_id,
        ).all()
    ]

    # Delete ontology concepts sourced from this repository's code components
    if component_ids:
        db.query(OntologyConcept).filter(
            OntologyConcept.tenant_id == tenant_id,
            OntologyConcept.source_component_id.in_(component_ids),
        ).delete(synchronize_session=False)

    db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
    ).delete()

    crud.repository.remove(db=db, id=repo_id, tenant_id=tenant_id)


# ============================================================
# SCAN PREVIEW (classify files without running LLM analysis)
# ============================================================

@router.post("/scan-preview", status_code=status.HTTP_200_OK)
def scan_repo_preview(
    *,
    body: dict,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Phase 1 of two-phase repo onboarding: scan a GitHub repo URL and classify
    files into to_analyze / skipped WITHOUT starting any LLM analysis.
    Returns a breakdown so the user can review before committing to analysis.

    Body: {"url": "https://github.com/owner/repo", "branch": "main"}
    Response: {
      "to_analyze": [{"path": ..., "language": ...}],
      "skipped": [{"path": ..., "category": ..., "ext": ...}],
      "summary": {"total": N, "analyze_count": N, "skipped_count": N,
                  "by_language": {...}, "skipped_by_category": {...}}
    }
    """
    import asyncio
    from app.services.code_analysis_service import code_analysis_service

    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    # Look up tenant's GitHub integration token (enables private repo access)
    from app.crud.crud_integration_config import crud_integration_config
    gh_config = crud_integration_config.get_by_provider(db, tenant_id=tenant_id, provider="github")
    github_token = gh_config.access_token if (gh_config and gh_config.is_active) else None

    try:
        # Run the async scan synchronously
        scan_result = asyncio.run(
            code_analysis_service._get_repo_file_list(
                *code_analysis_service._detect_github_url_type(url)[1:3],  # owner, repo
                body.get("branch"),  # branch (optional, None = auto-detect)
                github_token=github_token,
            )
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not scan repository: {e}")

    to_analyze = scan_result.get("to_analyze", [])
    skipped = scan_result.get("skipped", [])

    # Build summary
    by_language: dict = {}
    for f in to_analyze:
        lang = f.get("language") or "unknown"
        by_language[lang] = by_language.get(lang, 0) + 1

    skipped_by_category: dict = {}
    for s in skipped:
        cat = s.get("category", "Other")
        skipped_by_category[cat] = skipped_by_category.get(cat, 0) + 1

    return {
        "to_analyze": [{"path": f["path"], "language": f.get("language", "")} for f in to_analyze],
        "skipped": skipped,
        "summary": {
            "total": len(to_analyze) + len(skipped),
            "analyze_count": len(to_analyze),
            "skipped_count": len(skipped),
            "by_language": by_language,
            "skipped_by_category": skipped_by_category,
        },
    }


# ============================================================
# ANALYSIS TRIGGER
# ============================================================

@router.post("/{repo_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
def trigger_analysis(
    repo_id: int,
    *,
    file_list: List[dict],
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Trigger analysis for a repository. Accepts a list of files to analyze.

    Request body:
    ```json
    [
        {"path": "src/main.py", "url": "https://raw.githubusercontent.com/.../main.py", "language": "python"},
        {"path": "src/utils.py", "url": "https://raw.githubusercontent.com/.../utils.py", "language": "python"}
    ]
    ```

    The analysis runs asynchronously via Celery. Poll GET /{repo_id} for progress.
    """
    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repo.analysis_status == "analyzing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository is already being analyzed. Wait for completion."
        )

    if not file_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_list cannot be empty"
        )

    # Validate file_list structure
    for f in file_list:
        if "path" not in f or "url" not in f:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Each file must have 'path' and 'url' fields"
            )

    # Build language breakdown from file_list and persist for immediate UI display
    language_breakdown: dict = {}
    for f in file_list:
        lang = f.get("language") or "unknown"
        language_breakdown[lang] = language_breakdown.get(lang, 0) + 1
    repo_obj = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if repo_obj:
        crud.repository.update(db=db, db_obj=repo_obj, obj_in={"analyze_language_breakdown": language_breakdown})
        db.commit()

    # Set total_files upfront so the UI can display the full expected count immediately,
    # before the Celery worker starts processing files.
    crud.repository.update_analysis_progress(
        db=db, repo_id=repo_id, tenant_id=tenant_id,
        analyzed_files=0, total_files=len(file_list),
        status="analyzing"
    )

    # Look up tenant's GitHub integration token (enables private repo analysis)
    from app.crud.crud_integration_config import crud_integration_config
    gh_config = crud_integration_config.get_by_provider(db, tenant_id=tenant_id, provider="github")
    github_token = gh_config.access_token if (gh_config and gh_config.is_active) else None

    # Dispatch Celery task
    from app.tasks.code_analysis_tasks import repo_analysis_task
    task = repo_analysis_task.delay(repo_id, tenant_id, file_list, github_token)

    logger.info(
        f"Repo analysis triggered for repo {repo_id} ({len(file_list)} files) "
        f"by user {current_user.id}, celery_task_id={task.id}"
    )

    return {
        "message": f"Analysis started for {len(file_list)} files",
        "repo_id": repo_id,
        "task_id": task.id,
        "total_files": len(file_list),
    }


# ============================================================
# RESUME ANALYSIS (pick up where it left off)
# ============================================================

@router.post("/{repo_id}/resume", status_code=status.HTTP_202_ACCEPTED)
def resume_analysis(
    repo_id: int,
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Resume analysis for a repository by re-queuing only the files that
    are not yet completed (pending, failed, processing). Already-completed
    files are automatically skipped by the worker.
    """
    from app.models.code_component import CodeComponent

    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repo.analysis_status == "analyzing":
        # Allow resume even if status is "analyzing" — the worker may have died.
        # Resume will reset the status and re-queue pending files.
        pass

    # Find all non-completed file components
    pending_components = db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
        CodeComponent.component_type == "File",
        CodeComponent.analysis_status != "completed",
    ).all()

    if not pending_components:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending files to resume — all files are already completed."
        )

    # Count already-completed so progress bar starts correctly
    completed_count = db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
        CodeComponent.component_type == "File",
        CodeComponent.analysis_status == "completed",
    ).count()

    # Build file_list from pending components' raw URLs
    _ext_to_lang = {
        ".py": "python", ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript", ".md": "markdown",
        ".go": "go", ".java": "java", ".rs": "rust", ".css": "css",
        ".json": "json", ".yaml": "yaml", ".yml": "yaml",
        ".sh": "shell", ".dockerfile": "dockerfile", ".rb": "ruby",
        ".php": "php", ".cs": "csharp", ".cpp": "cpp", ".c": "c",
    }
    file_list = []
    for comp in pending_components:
        location = comp.location or ""
        path = comp.name  # fallback
        if "raw.githubusercontent.com/" in location:
            # URL: https://raw.githubusercontent.com/owner/repo/branch/path/to/file
            after = location.split("raw.githubusercontent.com/", 1)[1]
            segments = after.split("/", 3)
            if len(segments) >= 4:
                path = segments[3]
        dot_idx = path.rfind(".")
        ext = path[dot_idx:].lower() if dot_idx != -1 else ""
        language = _ext_to_lang.get(ext, "unknown")
        file_list.append({"path": path, "url": location, "language": language})

    # Reset failed/pending status on those components so they're picked up fresh
    for comp in pending_components:
        if comp.analysis_status in ("failed", "processing"):
            crud.code_component.update(db, db_obj=comp, obj_in={"analysis_status": "pending"})
    db.commit()

    # Update repo progress: start from already-completed offset
    crud.repository.update_analysis_progress(
        db=db, repo_id=repo_id, tenant_id=tenant_id,
        analyzed_files=completed_count,
        total_files=completed_count + len(file_list),
        status="analyzing",
    )

    # Look up GitHub token
    from app.crud.crud_integration_config import crud_integration_config
    gh_config = crud_integration_config.get_by_provider(db, tenant_id=tenant_id, provider="github")
    github_token = gh_config.access_token if (gh_config and gh_config.is_active) else None

    # Dispatch with offset so progress tracking is correct
    from app.tasks.code_analysis_tasks import repo_analysis_task
    task = repo_analysis_task.delay(repo_id, tenant_id, file_list, github_token, completed_count)

    logger.info(
        f"Resumed analysis for repo {repo_id}: {len(file_list)} pending files "
        f"(offset={completed_count}), task={task.id}"
    )

    return {
        "message": f"Resuming analysis for {len(file_list)} pending files",
        "repo_id": repo_id,
        "task_id": task.id,
        "pending_files": len(file_list),
        "already_completed": completed_count,
    }


# ============================================================
# REPOSITORY COMPONENTS
# ============================================================

@router.get("/{repo_id}/components", response_model=List[schemas.CodeComponent])
def list_repo_components(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    skip: int = 0,
    limit: int = 500,
) -> Any:
    """List all code components belonging to a repository (default limit 500 to support large repos)."""
    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    from app.models.code_component import CodeComponent
    from datetime import datetime, timedelta

    # Auto-fix stuck "processing" files: if stuck for >10 minutes, mark as failed
    # Also detect potential loops (files re-stuck after retry)
    stale_cutoff = datetime.utcnow() - timedelta(minutes=10)
    stuck_components = db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
        CodeComponent.analysis_status == "processing",
        CodeComponent.analysis_started_at < stale_cutoff,
    ).all()

    if stuck_components:
        for comp in stuck_components:
            # Detect retry loops: if this file was already stuck before (has a prior failure summary)
            prev_summary = comp.summary or ""
            is_loop = "timed out" in prev_summary.lower() or "stuck" in prev_summary.lower()

            if is_loop:
                solution = (
                    "Analysis stuck in loop (timed out repeatedly).\n"
                    "Solution: This file may be too complex for automatic analysis. "
                    "Try re-uploading the repository or contact support if this persists."
                )
            else:
                solution = (
                    "Analysis timed out (processing exceeded 10 minutes).\n"
                    "Solution: Click 'Retry' to re-analyze. If it keeps timing out, "
                    "the file may be too large or the AI service may be experiencing delays."
                )

            crud.code_component.update(
                db, db_obj=comp,
                obj_in={
                    "analysis_status": "failed",
                    "summary": solution,
                }
            )
        logger.info(
            f"Auto-marked {len(stuck_components)} stuck components as failed in repo {repo_id}"
        )

    # Also fix "pending" files that belong to repos marked as "completed"
    # This catches orphaned files from interrupted analysis runs
    if repo.analysis_status == "completed":
        orphaned = db.query(CodeComponent).filter(
            CodeComponent.repository_id == repo_id,
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.analysis_status == "pending",
        ).count()
        if orphaned > 0:
            logger.info(f"Found {orphaned} orphaned pending files in completed repo {repo_id}")

    components = db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
    ).order_by(CodeComponent.id.asc()).offset(skip).limit(limit).all()

    return components


@router.post("/{repo_id}/retry-failed", status_code=status.HTTP_202_ACCEPTED)
def retry_all_failed_components(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retry ALL failed components in a repository via a single Celery task
    that processes them sequentially with rate-limiting (4s between calls)
    to respect Gemini's 15 RPM limit.
    """
    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    from app.models.code_component import CodeComponent
    failed_components = db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
        CodeComponent.analysis_status == "failed",
    ).all()

    if not failed_components:
        raise HTTPException(status_code=400, detail="No failed components to retry")

    # Reset all failed components to pending
    failed_ids = []
    for comp in failed_components:
        crud.code_component.update(
            db, db_obj=comp,
            obj_in={
                "analysis_status": "pending",
                "summary": None,
                "analysis_started_at": None,
                "analysis_completed_at": None,
                "ai_cost_inr": 0,
            }
        )
        failed_ids.append(comp.id)

    # Dispatch a single Celery task that processes them sequentially
    from app.tasks.code_analysis_tasks import batch_retry_failed_components
    task = batch_retry_failed_components.delay(repo_id, tenant_id, failed_ids)

    logger.info(
        f"Batch retry dispatched for {len(failed_ids)} failed components in repo {repo_id}, "
        f"celery_task_id={task.id}"
    )

    return {
        "message": f"Retrying {len(failed_ids)} failed files sequentially (rate-limited)",
        "repo_id": repo_id,
        "task_id": task.id,
        "failed_count": len(failed_ids),
    }


# ============================================================
# SYNTHESIS (Reduce Phase — System Architecture)
# ============================================================

@router.get("/{repo_id}/synthesis")
def get_repo_synthesis(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get the synthesized System Architecture document for a repository."""
    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not repo.synthesis_data:
        raise HTTPException(
            status_code=404,
            detail=f"Synthesis not yet available (status: {repo.synthesis_status or 'not started'})"
        )
    return {
        "repo_id": repo_id,
        "repo_name": repo.name,
        "synthesis_status": repo.synthesis_status,
        "synthesis": repo.synthesis_data,
    }


@router.post("/{repo_id}/synthesize", status_code=status.HTTP_202_ACCEPTED)
def trigger_synthesis(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Manually trigger (or re-trigger) synthesis for a repository.
    Requires the repository to have completed analysis.
    """
    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repo.analysis_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository analysis must be completed first (current: {repo.analysis_status})"
        )

    if repo.synthesis_status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Synthesis is already running"
        )

    from app.tasks.code_analysis_tasks import repo_synthesis_task
    task = repo_synthesis_task.delay(repo_id, tenant_id)

    logger.info(
        f"Synthesis manually triggered for repo {repo_id} by user {current_user.id}, "
        f"celery_task_id={task.id}"
    )

    return {
        "message": "Synthesis started",
        "repo_id": repo_id,
        "task_id": task.id,
    }


# ============================================================
# STATS
# ============================================================

@router.get("/stats/summary")
def get_repo_stats(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get repository statistics for the tenant."""
    total = crud.repository.count_by_tenant(db=db, tenant_id=tenant_id)
    completed = len(crud.repository.get_by_status(
        db=db, analysis_status="completed", tenant_id=tenant_id
    ))
    analyzing = len(crud.repository.get_by_status(
        db=db, analysis_status="analyzing", tenant_id=tenant_id
    ))
    failed = len(crud.repository.get_by_status(
        db=db, analysis_status="failed", tenant_id=tenant_id
    ))

    return {
        "total_repositories": total,
        "completed": completed,
        "analyzing": analyzing,
        "failed": failed,
        "pending": total - completed - analyzing - failed,
    }


@router.get("/{repo_id}/stats")
def get_single_repo_stats(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Detailed stats for a single repository:
    - File extension breakdown (.py: 45, .ts: 120, ...)
    - Component type counts (Class: 30, Service: 12, Function: 200, ...)
    - Analysis status breakdown (completed, failed, pending, processing)
    - Extracted entities: services, endpoints, models from structured_analysis
    - Total AI cost for this repo
    """
    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    from app.models.code_component import CodeComponent
    from sqlalchemy import func
    import os

    components = db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
    ).all()

    # Extension breakdown
    ext_counts = {}
    for comp in components:
        name = comp.name or ""
        _, ext = os.path.splitext(name)
        ext = ext.lower() if ext else "(no ext)"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
    ext_breakdown = sorted(ext_counts.items(), key=lambda x: -x[1])

    # Analysis status breakdown
    status_counts = {"completed": 0, "failed": 0, "pending": 0, "processing": 0}
    for comp in components:
        s = comp.analysis_status or "pending"
        status_counts[s] = status_counts.get(s, 0) + 1

    # Component type counts + key entities from structured_analysis
    type_counts = {}
    services_found = []
    endpoints_found = []
    models_found = []
    for comp in components:
        sa = comp.structured_analysis
        if not sa:
            continue
        for c in sa.get("components", []):
            ctype = c.get("type", "Other")
            type_counts[ctype] = type_counts.get(ctype, 0) + 1
            cname = c.get("name", "")
            if ctype in ("Service", "Class") and ("service" in cname.lower() or "controller" in cname.lower()):
                services_found.append(cname)
            if ctype == "Model" or (ctype == "Class" and "model" in cname.lower()):
                models_found.append(cname)
        for api in sa.get("api_contracts", []):
            method = api.get("method", "")
            path = api.get("path", "")
            if path:
                endpoints_found.append(f"{method} {path}" if method else path)

    type_breakdown = sorted(type_counts.items(), key=lambda x: -x[1])

    # Total AI cost
    cost_sum = db.query(func.sum(CodeComponent.ai_cost_inr)).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
        CodeComponent.ai_cost_inr.isnot(None),
    ).scalar()

    # Skipped files (stored from initial GitHub scan)
    skipped_files = repo.skipped_files or []
    skipped_count = len(skipped_files)
    total_repo_files = len(components) + skipped_count

    # Skipped files breakdown by category
    skipped_cat_counts: dict = {}
    skipped_ext_counts: dict = {}
    for sf in skipped_files:
        cat = sf.get("category", "Other")
        skipped_cat_counts[cat] = skipped_cat_counts.get(cat, 0) + 1
        ext = sf.get("ext", "(no ext)")
        skipped_ext_counts[ext] = skipped_ext_counts.get(ext, 0) + 1
    skipped_category_breakdown = sorted(skipped_cat_counts.items(), key=lambda x: -x[1])
    skipped_extension_breakdown = sorted(skipped_ext_counts.items(), key=lambda x: -x[1])

    # Language breakdown from pre-analysis scan (populated before LLM runs)
    analyze_language_breakdown = repo.analyze_language_breakdown or {}
    scan_analyze_count = sum(analyze_language_breakdown.values()) if analyze_language_breakdown else len(components)

    return {
        "repo_id": repo_id,
        "repo_name": repo.name,
        "total_files": len(components),
        "total_repo_files": total_repo_files,
        "scan_analyze_count": scan_analyze_count,
        "skipped_files_count": skipped_count,
        "skipped_files": skipped_files[:500],
        "skipped_category_breakdown": [{"category": c, "count": n} for c, n in skipped_category_breakdown],
        "skipped_extension_breakdown": [{"ext": e, "count": n} for e, n in skipped_extension_breakdown],
        "analyze_language_breakdown": analyze_language_breakdown,
        "analysis_status_breakdown": status_counts,
        "extension_breakdown": [{"ext": e, "count": c} for e, c in ext_breakdown],
        "component_type_breakdown": [{"type": t, "count": c} for t, c in type_breakdown],
        "services": list(set(services_found))[:50],
        "endpoints": list(set(endpoints_found))[:100],
        "models": list(set(models_found))[:50],
        "services_count": len(set(services_found)),
        "endpoints_count": len(set(endpoints_found)),
        "models_count": len(set(models_found)),
        "total_ai_cost_inr": float(cost_sum) if cost_sum else 0,
    }


# =========================================================================
# Phase 3 (P3.7): Data Flow backfill endpoint for a repository
# =========================================================================

@router.post("/{repo_id}/data-flow/backfill", status_code=status.HTTP_202_ACCEPTED)
def trigger_data_flow_backfill(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_admin_user),
) -> Any:
    """Kick off an async backfill of data-flow edges for every analyzed
    component in a repository. Admin/CXO only. Returns Celery task_id."""
    repo = crud.repository.get(db, id=repo_id)
    if not repo or repo.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Repository not found")

    from app.tasks.data_flow_tasks import backfill_data_flow_edges
    task = backfill_data_flow_edges.delay(repo_id, tenant_id)
    return {
        "task_id": task.id,
        "repository_id": repo_id,
        "message": "Data flow backfill queued. Poll /tasks/{task_id}/status for progress.",
    }


@router.get("/{repo_id}/data-flow/stats")
def get_repo_data_flow_stats(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Return edge count and a readiness indicator for the repository."""
    from app.crud.crud_code_data_flow_edge import code_data_flow_edge as crud_edge
    from app.models.code_component import CodeComponent

    repo = crud.repository.get(db, id=repo_id)
    if not repo or repo.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Repository not found")

    edge_count = crud_edge.count_by_repository(
        db, repository_id=repo_id, tenant_id=tenant_id,
    )
    analyzed_count = (
        db.query(CodeComponent)
        .filter(
            CodeComponent.repository_id == repo_id,
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.analysis_status.in_(("completed", "complete")),
        )
        .count()
    )
    return {
        "repository_id": repo_id,
        "analyzed_components": analyzed_count,
        "edge_count": edge_count,
        "ready": edge_count > 0,
    }
