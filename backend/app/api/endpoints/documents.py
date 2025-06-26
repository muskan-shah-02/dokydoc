# This is the content for your NEW file at:
# backend/app/api/endpoints/documents.py

import shutil
from pathlib import Path
from typing import List, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps

router = APIRouter()

# Define the directory where uploaded files will be stored.
# We create it if it doesn't exist.
UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/", response_model=List[schemas.Document])
def read_documents(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all documents owned by the current user.
    """
    documents = crud.document.get_multi_by_owner(
        db=db, owner_id=current_user.id, skip=skip, limit=limit
    )
    return documents


@router.post("/upload", response_model=schemas.Document)
async def upload_document(
    *,
    db: Session = Depends(deps.get_db),
    document_type: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Upload a new document.

    This endpoint handles the file upload, saves the file to the server's
    filesystem, and creates a corresponding record in the database.
    """
    # Generate a unique filename to prevent conflicts.
    # We use a UUID and keep the original file extension.
    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    storage_path = UPLOAD_DIR / unique_filename

    # Save the uploaded file to the filesystem.
    # We use shutil.copyfileobj for efficient file handling.
    try:
        with storage_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    # Create the document metadata object to be stored in the database.
    document_in = schemas.DocumentCreate(
        filename=file.filename,
        document_type=document_type,
        version=version,
    )

    # Use our CRUD function to create the database record.
    # Note: We pass the string representation of the path for storage.
    document = crud.document.create_with_owner(
        db=db,
        obj_in=document_in,
        owner_id=current_user.id,
        storage_path=str(storage_path),
    )

    return document