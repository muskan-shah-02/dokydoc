# This is the content for your UPDATED file at:
# backend/app/api/endpoints/validation.py

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app import crud
from app.api import deps
from app.schemas.mismatch import Mismatch
from app.services.validation_service import validation_service

router = APIRouter()

@router.get("/mismatches", response_model=List[Mismatch])
def get_mismatches(
    db: Session = Depends(deps.get_db),
    # current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Retrieve all detected mismatches.
    """
    return crud.mismatch.get_multi(db=db)


@router.post("/run-scan", status_code=202)
def run_validation_scan(
    *,
    document_ids: List[int], # Expect a list of integers in the request body
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    # current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Trigger a background task to run a validation scan for a specific
    list of documents.
    """
    if not document_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided for scanning.")

    background_tasks.add_task(
        validation_service.run_version_mismatch_check, db=db, document_ids=document_ids
    )
    return {"message": "Validation scan has been initiated in the background."}