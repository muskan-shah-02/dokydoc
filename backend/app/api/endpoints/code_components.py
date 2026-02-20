# This is the final, updated content for your file at:
# backend/app/api/endpoints/code_components.py

from datetime import datetime, timedelta, timezone
from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.services.code_analysis_service import code_analysis_service
from app.core.logging import LoggerMixin
from app.core.exceptions import NotFoundException, ValidationException

# How long before we consider a "processing" analysis to be stuck
STALE_ANALYSIS_THRESHOLD_MINUTES = 30

class CodeComponentEndpoints(LoggerMixin):
    """Code component endpoints with enhanced logging and error handling."""
    
    def __init__(self):
        super().__init__()

# Create instance for use in endpoints
code_component_endpoints = CodeComponentEndpoints()

router = APIRouter()


@router.get("/", response_model=List[schemas.CodeComponentWithProgress])
def read_code_components(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all code components for the current user, enriched with
    repository analysis progress (analyzed_files / total_files) for
    components linked to a repository.
    """
    logger = code_component_endpoints.logger
    logger.info(f"Fetching code components for user {current_user.id} (tenant_id={tenant_id}), skip={skip}, limit={limit}")

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

        # Add the new analysis service to the background queue
        # This triggers our new pipeline without making the user wait
        # SPRINT 2 Phase 6: Pass tenant_id to background task for isolation
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
