# This is the updated content for your file at:
# backend/app/api/endpoints/code_components.py

from typing import List, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.services.code_analysis_service import code_analysis_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[schemas.CodeComponent])
def read_code_components(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    # --- FIX: Corrected function name ---
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all code components for the current user.
    """
    code_components = crud.code_component.get_multi_by_owner(
        db=db, owner_id=current_user.id, skip=skip, limit=limit
    )
    return code_components


@router.post("/", response_model=schemas.CodeComponent)
def create_code_component(
    *,
    db: Session = Depends(deps.get_db),
    code_component_in: schemas.CodeComponentCreate,
    current_user: models.User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks # 1. Add this dependency
) -> Any:
    """
    Create new code component.
    """
    code_component = crud.code_component.create_with_owner(
        db=db, obj_in=code_component_in, owner_id=current_user.id
    )

    # 2. Add the new analysis service to the background queue
    # This triggers our new pipeline without making the user wait
    background_tasks.add_task(
        code_analysis_service.analyze_component_in_background,
        component_id=code_component.id
    )
    
    return code_component


@router.get("/{id}", response_model=schemas.CodeComponent)
def read_code_component(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    # --- FIX: Corrected function name ---
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get code component by ID.
    """
    logger.info(f"Attempting to fetch CodeComponent with id: {id} for user: {current_user.email}")
    
    component = crud.code_component.get(db=db, id=id)
    
    if not component:
        logger.warning(f"DATABASE MISS: CodeComponent with id {id} not found in the database.")
        raise HTTPException(status_code=404, detail="CodeComponent not found")
    
    logger.info(f"DATABASE HIT: Found component '{component.name}' with owner_id: {component.owner_id}")

    if component.owner_id != current_user.id:
        logger.error(f"PERMISSION DENIED: User {current_user.email} tried to access component owned by user {component.owner_id}.")
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    logger.info(f"Successfully retrieved component {id} for user {current_user.email}")
    return component
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_code_component(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Delete a code component and its associated links.
    """
    logger.info(f"User {current_user.email} attempting to delete component {id}")
    component = crud.code_component.get(db=db, id=id)
    if not component:
        raise HTTPException(status_code=404, detail="CodeComponent not found")
    if component.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Use our new safe deletion method from the CRUD layer
    crud.code_component.remove_with_links(db=db, id=id)
    logger.info(f"Successfully deleted component {id}")
    # No return value is needed, as the 204 status code implies success with no content.
