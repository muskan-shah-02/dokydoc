# This is the final, updated content for your file at:
# backend/app/api/endpoints/code_components.py

from datetime import datetime, timedelta, timezone
from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.services.code_analysis_service import code_analysis_service
from app.core.logging import LoggerMixin
from app.core.exceptions import NotFoundException, ValidationException

# How long before we consider a "processing" analysis to be stuck
STALE_ANALYSIS_THRESHOLD_MINUTES = 10

class CodeComponentEndpoints(LoggerMixin):
    """Code component endpoints with enhanced logging and error handling."""
    
    def __init__(self):
        super().__init__()

# Create instance for use in endpoints
code_component_endpoints = CodeComponentEndpoints()

router = APIRouter()


@router.get("/check-name")
def check_component_name(
    name: str = Query(..., description="Component name (or filename) to check"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Check whether a component with the given name already exists in any repository
    for this tenant. Used by the frontend to surface an override confirmation dialog
    before the user registers a standalone component.

    Returns a list of matching components (only those linked to a repository).
    """
    from app.models.code_component import CodeComponent
    from app.models.repository import Repository

    basename = name.strip().rstrip("/").rsplit("/", 1)[-1]  # extract filename from path
    matches = (
        db.query(CodeComponent, Repository.name.label("repo_name"))
        .join(Repository, CodeComponent.repository_id == Repository.id)
        .filter(
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.repository_id.isnot(None),
            CodeComponent.name == basename,
        )
        .limit(5)
        .all()
    )

    return [
        {
            "id": comp.id,
            "name": comp.name,
            "location": comp.location,
            "repository_id": comp.repository_id,
            "repo_name": repo_name,
        }
        for comp, repo_name in matches
    ]


@router.get("/", response_model=List[schemas.CodeComponentWithProgress])
def read_code_components(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    standalone: bool = Query(False, description="When true, return only components with no repository (standalone)"),
    initiative_id: int = Query(None, description="Filter by initiative (project) ID"),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all code components for the current user, enriched with
    repository analysis progress (analyzed_files / total_files) for
    components linked to a repository.

    - standalone=true: only components with repository_id IS NULL
    - initiative_id: filter via repository → InitiativeAsset join
    """
    logger = code_component_endpoints.logger
    logger.info(f"Fetching code components for user {current_user.id} (tenant_id={tenant_id}), skip={skip}, limit={limit}, standalone={standalone}")

    if initiative_id:
        # Filter code components via their repository's initiative asset link
        from app.models.initiative_asset import InitiativeAsset
        from app.models.code_component import CodeComponent
        repo_ids_sub = db.query(InitiativeAsset.asset_id).filter(
            InitiativeAsset.initiative_id == initiative_id,
            InitiativeAsset.asset_type == "REPOSITORY",
            InitiativeAsset.tenant_id == tenant_id,
            InitiativeAsset.is_active == True,
        ).subquery()
        code_components = db.query(CodeComponent).filter(
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.repository_id.in_(repo_ids_sub),
        ).offset(skip).limit(limit).all()
    elif standalone:
        from app.models.code_component import CodeComponent
        code_components = db.query(CodeComponent).filter(
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.repository_id.is_(None),
        ).offset(skip).limit(limit).all()
    else:
        code_components = crud.code_component.get_multi_by_owner(
            db=db, owner_id=current_user.id, tenant_id=tenant_id, skip=skip, limit=limit
        )

    # Auto-recover stale analyses: if a component has been "processing" for too long,
    # mark it as failed so the user gets clear feedback instead of infinite spinner.
    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_ANALYSIS_THRESHOLD_MINUTES)
    for comp in code_components:
        if comp.analysis_status == "processing" and comp.analysis_started_at:
            started = comp.analysis_started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if started < stale_cutoff:
                logger.warning(
                    f"Component {comp.id} stuck in 'processing' since {comp.analysis_started_at} "
                    f"(>{STALE_ANALYSIS_THRESHOLD_MINUTES}min) — marking as failed"
                )
                crud.code_component.update(
                    db, db_obj=comp,
                    obj_in={
                        "analysis_status": "failed",
                        "summary": f"Analysis timed out after {STALE_ANALYSIS_THRESHOLD_MINUTES} minutes. "
                                   "The worker may have crashed. Please try again.",
                    }
                )

    # Batch-fetch linked repositories in ONE query to get progress data
    repo_ids = {c.repository_id for c in code_components if c.repository_id}
    repo_map = {}
    if repo_ids:
        from app.models.repository import Repository
        repos = db.query(Repository).filter(
            Repository.id.in_(repo_ids),
            Repository.tenant_id == tenant_id,
        ).all()
        repo_map = {r.id: r for r in repos}

    # Build enriched response with repo progress
    result = []
    for comp in code_components:
        comp_data = schemas.CodeComponentWithProgress.model_validate(comp)
        if comp.repository_id and comp.repository_id in repo_map:
            repo = repo_map[comp.repository_id]
            comp_data.repo_analyzed_files = repo.analyzed_files
            comp_data.repo_total_files = repo.total_files
            comp_data.repo_analysis_status = repo.analysis_status
        result.append(comp_data)

    logger.info(f"Retrieved {len(result)} code components for user {current_user.id} (tenant_id={tenant_id})")
    return result


@router.post("/", response_model=schemas.CodeComponent)
def create_code_component(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    code_component_in: schemas.CodeComponentCreate,
    current_user: models.User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks
) -> Any:
    """
    Create new code component.

    SPRINT 2: Now creates component in current tenant for multi-tenancy isolation.
    """
    logger = code_component_endpoints.logger
    logger.info(f"Creating code component '{code_component_in.name}' for user {current_user.id} (tenant_id={tenant_id})")

    try:
        code_component = crud.code_component.create_with_owner(
            db=db, obj_in=code_component_in, owner_id=current_user.id, tenant_id=tenant_id
        )

        # Dispatch analysis via Celery for reliability (no daemon threads that can die silently).
        # The code_analysis_service handles URL detection: repo URLs → redirect to repo pipeline,
        # single file URLs → static_analysis_worker, non-GitHub → fetch then static_analysis_worker.
        background_tasks.add_task(
            code_analysis_service.analyze_component_in_background,
            component_id=code_component.id,
            tenant_id=tenant_id
        )

        logger.info(f"Code component {code_component.id} created successfully in tenant {tenant_id} and analysis scheduled")
        return code_component

    except Exception as e:
        logger.error(f"Failed to create code component: {e}")
        raise ValidationException(f"Failed to create code component: {str(e)}")


@router.get("/{id}", response_model=schemas.CodeComponent)
def read_code_component(
    *,
    id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get code component by ID.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when component not in tenant to avoid leaking existence.
    """
    logger = code_component_endpoints.logger
    logger.info(f"Fetching CodeComponent {id} for user {current_user.email} (tenant_id={tenant_id})")

    component = crud.code_component.get(db=db, id=id, tenant_id=tenant_id)

    if not component:
        logger.warning(f"CodeComponent {id} not found in tenant {tenant_id}")
        raise HTTPException(status_code=404, detail="CodeComponent not found")

    logger.info(f"Successfully retrieved component {id} ('{component.name}') for user {current_user.email}")
    return component


@router.put("/{id}", response_model=schemas.CodeComponent)
def update_code_component(
    *,
    id: int,
    obj_in: schemas.CodeComponentUpdate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Update a code component's metadata (e.g. location when overriding a repo file)."""
    component = crud.code_component.get(db=db, id=id, tenant_id=tenant_id)
    if not component:
        raise HTTPException(status_code=404, detail="CodeComponent not found")
    return crud.code_component.update(db=db, db_obj=component, obj_in=obj_in)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_code_component(
    *,
    id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Delete a code component and its associated links.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when component not in tenant to avoid leaking existence.
    """
    logger = code_component_endpoints.logger
    logger.info(f"User {current_user.email} attempting to delete component {id} (tenant_id={tenant_id})")

    component = crud.code_component.get(db=db, id=id, tenant_id=tenant_id)
    if not component:
        logger.warning(f"Component {id} not found in tenant {tenant_id} for deletion")
        raise HTTPException(status_code=404, detail="CodeComponent not found")

    # Use our new safe deletion method from the CRUD layer
    crud.code_component.remove_with_links(db=db, id=id, tenant_id=tenant_id)
    logger.info(f"Successfully deleted component {id} from tenant {tenant_id}")
    # No return value is needed, as the 204 status code implies success with no content.


@router.post("/{id}/retry", response_model=schemas.CodeComponent)
def retry_failed_component(
    *,
    id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retry analysis for a failed component. Resets status to 'pending'
    and dispatches the analysis worker.
    Only works on components with status 'failed'.
    """
    logger = code_component_endpoints.logger
    component = crud.code_component.get(db=db, id=id, tenant_id=tenant_id)
    if not component:
        raise HTTPException(status_code=404, detail="CodeComponent not found")

    if component.analysis_status not in ("failed", "pending"):
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry failed or pending components (current: {component.analysis_status})"
        )

    # Reset the component for re-analysis
    crud.code_component.update(
        db, db_obj=component,
        obj_in={
            "analysis_status": "pending",
            "summary": None,
            "analysis_started_at": None,
            "analysis_completed_at": None,
            "ai_cost_inr": 0,
        }
    )

    # Dispatch analysis
    if component.repository_id:
        # Repository component: use static_analysis_worker
        from app.tasks.code_analysis_tasks import static_analysis_worker
        import httpx

        # Fetch file content from the stored URL
        try:
            resp = httpx.get(component.location, timeout=30, follow_redirects=True)
            code_content = resp.text if resp.status_code == 200 else ""
        except Exception:
            code_content = ""

        if not code_content:
            crud.code_component.update(
                db, db_obj=component,
                obj_in={"analysis_status": "failed", "summary": "Could not fetch file content from URL. Check if the repository is accessible."}
            )
            raise HTTPException(status_code=400, detail="Could not fetch file content from URL")

        repo = crud.repository.get(db=db, id=component.repository_id, tenant_id=tenant_id)
        repo_name = repo.name if repo else ""
        file_path = component.name

        # Detect language from file extension
        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
        lang_map = {"py": "python", "js": "javascript", "ts": "typescript", "tsx": "typescript",
                     "jsx": "javascript", "java": "java", "go": "go", "rs": "rust", "rb": "ruby"}
        language = lang_map.get(ext, ext)

        static_analysis_worker.delay(
            component.id, tenant_id, code_content,
            repo_name=repo_name, file_path=file_path, language=language
        )
        logger.info(f"Retrying repo component {id} via static_analysis_worker")
    else:
        # Standalone component: use static_analysis_worker via Celery for reliability
        import httpx as _httpx
        try:
            _resp = _httpx.get(component.location, timeout=30, follow_redirects=True)
            _code_content = _resp.text if _resp.status_code == 200 else ""
        except Exception:
            _code_content = ""

        if not _code_content:
            crud.code_component.update(
                db, db_obj=component,
                obj_in={"analysis_status": "failed", "summary": "Could not fetch file content from URL."}
            )
            raise HTTPException(status_code=400, detail="Could not fetch file content from URL")

        _ext = component.name.rsplit(".", 1)[-1].lower() if "." in component.name else ""
        _lang_map = {"py": "python", "js": "javascript", "ts": "typescript", "tsx": "typescript",
                     "jsx": "javascript", "java": "java", "go": "go", "rs": "rust", "rb": "ruby"}
        _language = _lang_map.get(_ext, _ext)

        from app.tasks.code_analysis_tasks import static_analysis_worker
        static_analysis_worker.delay(
            component.id, tenant_id, _code_content,
            repo_name="", file_path=component.name, language=_language
        )
        logger.info(f"Retrying standalone component {id} via static_analysis_worker (Celery)")

    # Return the updated component
    db.refresh(component)
    return component
