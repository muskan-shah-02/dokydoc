# This is the content for your NEW file at:
# backend/app/api/endpoints/code_components.py

from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps

router = APIRouter()

@router.get("/", response_model=List[schemas.CodeComponent])
def read_code_components(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all code components owned by the current user.
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
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Register a new code component in the system.
    """
    code_component = crud.code_component.create_with_owner(
        db=db, obj_in=component_in, owner_id=current_user.id
    )
    return code_component
