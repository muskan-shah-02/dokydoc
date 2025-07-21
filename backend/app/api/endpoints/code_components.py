# This is the updated content for your file at:
# backend/app/api/endpoints/code_components.py

from typing import List, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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
    component_in: schemas.CodeComponentCreate,
    # --- FIX: Corrected function name ---
    current_user: models.User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Create new code component and trigger AI analysis in the background.
    """
    code_component = crud.code_component.create_with_owner(
        db=db, obj_in=component_in, owner_id=current_user.id
    )
    
    background_tasks.add_task(
        code_analysis_service.analyze_component, component_id=code_component.id
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
