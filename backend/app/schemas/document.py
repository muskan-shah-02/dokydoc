# This is the updated content for your file at:
# backend/app/schemas/document.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# --- Base Schema ---
class DocumentBase(BaseModel):
    filename: str
    document_type: str
    version: str

# --- Create Schema ---
class DocumentCreate(DocumentBase):
    pass

# --- Update Schema ---
class DocumentUpdate(BaseModel):
    filename: Optional[str] = None
    document_type: Optional[str] = None
    version: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    file_size_kb: Optional[int] = None

# --- Main Document Schema (for API responses) ---
# This schema now includes all the new fields.
class Document(DocumentBase):
    id: int
    owner_id: int
    storage_path: str
    created_at: datetime
    
    # Add the new fields so they are included in API responses
    content: Optional[str] = None
    status: Optional[str] = None
    file_size_kb: Optional[int] = None

    # Pydantic v2 uses `from_attributes`
    class Config:
        from_attributes = True
