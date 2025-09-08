# This is the final, updated content for your file at:
# backend/app/api/endpoints/code_components.py

from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.services.code_analysis_service import code_analysis_service
from app.core.logging import LoggerMixin
from app.core.exceptions import NotFoundException, ValidationException

class CodeComponentEndpoints(LoggerMixin):
    """Code component endpoints with enhanced logging and error handling."""
    
    def __init__(self):
        super().__init__()

# Create instance for use in endpoints
code_component_endpoints = CodeComponentEndpoints()

router = APIRouter()


@router.get("/", response_model=List[schemas.CodeComponent])
def read_code_components(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all code components for the current user.
    """
    logger = code_component_endpoints.logger
    logger.info(f"Fetching code components for user {current_user.id}, skip={skip}, limit={limit}")
    
    code_components = crud.code_component.get_multi_by_owner(
        db=db, owner_id=current_user.id, skip=skip, limit=limit
    )
    
    logger.info(f"Retrieved {len(code_components)} code components for user {current_user.id}")
    return code_components


@router.post("/", response_model=schemas.CodeComponent)
def create_code_component(
    *,
    db: Session = Depends(deps.get_db),
    code_component_in: schemas.CodeComponentCreate,
    current_user: models.User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks
) -> Any:
    """
    Create new code component.
    """
    logger = code_component_endpoints.logger
    logger.info(f"Creating code component '{code_component_in.name}' for user {current_user.id}")
    
    try:
        code_component = crud.code_component.create_with_owner(
            db=db, obj_in=code_component_in, owner_id=current_user.id
        )

        # Add the new analysis service to the background queue
        # This triggers our new pipeline without making the user wait
        background_tasks.add_task(
            code_analysis_service.analyze_component_in_background,
            component_id=code_component.id
        )
        
        logger.info(f"Code component {code_component.id} created successfully and analysis scheduled")
        return code_component
        
    except Exception as e:
        logger.error(f"Failed to create code component: {e}")
        raise ValidationException(f"Failed to create code component: {str(e)}")


@router.get("/{id}", response_model=schemas.CodeComponent)
def read_code_component(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get code component by ID.
    """
    logger = code_component_endpoints.logger
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
    logger = code_component_endpoints.logger
    logger.info(f"User {current_user.email} attempting to delete component {id}")
    
    component = crud.code_component.get(db=db, id=id)
    if not component:
        logger.warning(f"Component {id} not found for deletion")
        raise HTTPException(status_code=404, detail="CodeComponent not found")
    
    if component.owner_id != current_user.id:
        logger.warning(f"User {current_user.email} attempted to delete component {id} owned by user {component.owner_id}")
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Use our new safe deletion method from the CRUD layer
    crud.code_component.remove_with_links(db=db, id=id)
    logger.info(f"Successfully deleted component {id}")
    # No return value is needed, as the 204 status code implies success with no content.
