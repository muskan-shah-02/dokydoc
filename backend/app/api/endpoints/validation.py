# This is the updated content for your file at:
# backend/app/api/endpoints/validation.py

from typing import Any, List
from fastapi import APIRouter, Depends, BackgroundTasks, status, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
# MANDATORY CHANGE: Remove the import of 'run_validation_scan_sync'
from app.services.validation_service import validation_service

router = APIRouter()

@router.get("/mismatches", response_model=List[schemas.Mismatch])
def read_mismatches(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all mismatches for the current user.
    """
    mismatches = crud.mismatch.get_multi_by_owner(
        db=db, owner_id=current_user.id, skip=skip, limit=limit
    )
    return mismatches

@router.post("/run-scan", status_code=status.HTTP_202_ACCEPTED)
def run_validation_scan(
    *,
    document_ids: List[int],
    current_user: models.User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Trigger a new validation scan for the current user on selected documents.
    """
    # Your existing logic is preserved
    if not document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one document ID must be provided"
        )
    
    # Your existing logic is preserved
    user_documents = crud.document.get_multi_by_owner(
        db=db, owner_id=current_user.id
    )
    user_doc_ids = {doc.id for doc in user_documents}
    invalid_doc_ids = set(document_ids) - user_doc_ids
    
    # Your existing logic is preserved
    if invalid_doc_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Documents not found or not owned by user: {list(invalid_doc_ids)}"
        )
    
    # MANDATORY CHANGE: Call the correct async method from the service object
    background_tasks.add_task(
        validation_service.run_validation_scan, 
        user_id=current_user.id,
        document_ids=document_ids
    )
    
    return {
        "message": f"Validation scan has been successfully started for {len(document_ids)} document(s).",
        "document_ids": document_ids
    }
