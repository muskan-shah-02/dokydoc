# This is the updated content for your file at:
# backend/app/schemas/mismatch.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

# Import related schemas to provide full context in the API response
from .document import Document
from .code_component import CodeComponent

# --- NEW: A strongly-typed schema for the 'details' object ---
# This matches the rich output from our new Gemini prompt.
class MismatchDetails(BaseModel):
    expected: str
    actual: str
    evidence_document: str
    evidence_code: str
    suggested_action: str

class MismatchBase(BaseModel):
    """
    Base properties for a mismatch, shared across creation and reading.
    """
    mismatch_type: str
    description: str
    severity: str
    confidence: Optional[str] = None # NEW: Add confidence field
    details: MismatchDetails # UPDATED: Use the strongly-typed details schema
    document_id: int
    code_component_id: int


class MismatchCreate(MismatchBase):
    """
    Properties to receive when creating a new mismatch via the API.
    """
    pass


class MismatchUpdate(BaseModel):
    """
    Properties to receive when updating a mismatch.
    A user can update the status or add notes.
    """
    status: Optional[str] = None
    user_notes: Optional[str] = None


class MismatchInDBBase(MismatchBase):
    """
    Properties shared by models stored in the database.
    Includes database-generated fields like id, owner_id, and timestamps.
    """
    id: int
    owner_id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    user_notes: Optional[str] = None

    class Config:
        # Pydantic v2 uses `from_attributes` instead of `orm_mode`
        from_attributes = True


class Mismatch(MismatchInDBBase):
    """
    The full Mismatch model to be returned by the API.
    It includes the complete related Document and CodeComponent objects,
    providing full context to the frontend in a single API call.
    """
    document: Document
    code_component: CodeComponent

