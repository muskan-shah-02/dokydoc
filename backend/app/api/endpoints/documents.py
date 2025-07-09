# This is the final, updated content for your file at:
# backend/app/api/endpoints/documents.py

import shutil
from pathlib import Path
from typing import List, Any
import uuid
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.services.document_parser import parser # Import our new Gemini parser

router = APIRouter()

UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# --- This is our new background task function ---
def parse_and_update_document(db: Session, document_id: int, storage_path: str):
    """
    This function runs in the background. It calls the Gemini parser
    and updates the database record with the content and new status.
    """
    print(f"Background task started for document_id: {document_id}")
    document = crud.document.get(db=db, id=document_id)
    if not document:
        print(f"Background task could not find document_id: {document_id}")
        return

    # Check if parser was initialized correctly
    if parser is None:
        print("Parser not available. Skipping parsing.")
        update_data = {"status": "failed", "progress": 100}
        crud.document.update(db=db, db_obj=document, obj_in=update_data)
        return

    try:
        # Update progress to 25% before starting the API call
        crud.document.update(db=db, db_obj=document, obj_in={"progress": 25})
        
        content = parser.parse(storage_path)
        
        # Update progress to 100% on completion
        update_data = {
            "content": content,
            "status": "completed" if content else "failed",
            "progress": 100
        }
        crud.document.update(db=db, db_obj=document, obj_in=update_data)
        print(f"Background task finished for document_id: {document_id}")

    except Exception as e:
        print(f"An error occurred in the background task for document {document_id}: {e}")
        # Mark the document as failed in case of an error
        crud.document.update(db=db, db_obj=document, obj_in={"status": "failed", "progress": 100})


@router.get("/", response_model=List[schemas.Document])
def read_documents(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Retrieve all documents owned by the current user."""
    return crud.document.get_multi_by_owner(db=db, owner_id=current_user.id)


@router.get("/{document_id}", response_model=schemas.Document)
def read_document(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get a single document by ID."""
    document = crud.document.get(db=db, id=document_id)
    if not document or document.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found or not authorized")
    return document

# --- NEW STATUS ENDPOINT ---
@router.get("/{document_id}/status", response_model=schemas.DocumentStatus)
def get_document_status(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Gets the current parsing status and progress for a document."""
    document = crud.document.get(db=db, id=document_id)
    if not document or document.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found or not authorized")
    return {"status": document.status, "progress": document.progress}


@router.post("/upload", response_model=schemas.Document)
async def upload_document(
    background_tasks: BackgroundTasks,
    *,
    db: Session = Depends(deps.get_db),
    document_type: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Upload a new document and schedule Gemini parsing in the background."""
    # Save the file
    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    storage_path = UPLOAD_DIR / unique_filename
    file_size_kb = 0
    try:
        with storage_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size_kb = round(os.path.getsize(storage_path) / 1024)
    finally:
        file.file.close()

    # Create the initial database record
    document_in = schemas.DocumentCreate(filename=file.filename, document_type=document_type, version=version)
    document = crud.document.create_with_owner(
        db=db, obj_in=document_in, owner_id=current_user.id, storage_path=str(storage_path)
    )
    # Update with initial size and progress
    crud.document.update(db=db, db_obj=document, obj_in={"file_size_kb": file_size_kb, "progress": 10})


    # Add the slow parsing job to the background
    background_tasks.add_task(
        parse_and_update_document, 
        db=db, 
        document_id=document.id, 
        storage_path=str(storage_path)
    )

    return document
