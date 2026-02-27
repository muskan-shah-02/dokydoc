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
    # Dedup: prevent duplicate repos by URL
    existing = crud.repository.get_by_url(db=db, url=obj_in.url, tenant_id=tenant_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repository with URL '{obj_in.url}' already exists (id={existing.id})"
        )

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
    db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
    ).delete()

    crud.repository.remove(db=db, id=repo_id, tenant_id=tenant_id)


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

    # Dispatch Celery task
    from app.tasks.code_analysis_tasks import repo_analysis_task
    task = repo_analysis_task.delay(repo_id, tenant_id, file_list)

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

    return {
        "repo_id": repo_id,
        "repo_name": repo.name,
        "total_files": len(components),
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
