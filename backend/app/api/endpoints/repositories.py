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
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all repositories for the current tenant."""
    if analysis_status:
        return crud.repository.get_by_status(
            db=db, analysis_status=analysis_status, tenant_id=tenant_id,
            skip=skip, limit=limit
        )
    return crud.repository.get_multi(
        db=db, tenant_id=tenant_id, skip=skip, limit=limit
    )


@router.post("/", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
def onboard_repository(
    *,
    obj_in: RepositoryCreate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Onboard a new repository. Checks for duplicate URLs within the tenant.
    Does NOT trigger analysis — use POST /{id}/analyze for that.
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
    limit: int = 100,
) -> Any:
    """List all code components belonging to a repository."""
    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    from app.models.code_component import CodeComponent
    components = db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
    ).offset(skip).limit(limit).all()

    return components


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
