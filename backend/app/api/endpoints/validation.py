# This is the content for your NEW file at:
# backend/app/api/endpoints/validation.py

from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.services.validation_service import validation_service # Import our new service

router = APIRouter()

@router.post("/run-scan", status_code=status.HTTP_202_ACCEPTED)
def run_validation_scan(
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Triggers a new validation scan in the background.
    For the MVP, this runs the version mismatch check.
    """
    # We add the scan to background tasks so the API can respond instantly.
    background_tasks.add_task(validation_service.run_version_mismatch_check, db=db)
    
    return {"message": "Validation scan has been scheduled to run in the background."}


@router.get("/mismatches", response_model=List[schemas.Mismatch])
def get_all_mismatches(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all detected mismatches.
    
    Note: In a real multi-tenant system, this would be filtered by the user's
    organization or project. For our MVP, we retrieve all of them.
    """
    mismatches = crud.mismatch.get_multi(db=db, skip=skip, limit=limit)
    return mismatches

