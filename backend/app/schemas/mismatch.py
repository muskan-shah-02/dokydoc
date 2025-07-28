# This is the updated content for your file at:
# backend/app/schemas/mismatch.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime

# Import related schemas to provide full context in the API response
from .document import Document
from .code_component import CodeComponent

# --- A strongly-typed schema for the 'details' object ---
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
    confidence: Optional[str] = None
    details: MismatchDetails # Use the strongly-typed details schema
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
    """
    status: Optional[str] = None
    user_notes: Optional[str] = None


class MismatchInDBBase(MismatchBase):
    """
    Properties shared by models stored in the database.
    """
    id: int
    owner_id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    user_notes: Optional[str] = None

    # UPDATED: Correct Pydantic v2 configuration
    model_config = ConfigDict(
        from_attributes=True,
    )


class Mismatch(MismatchInDBBase):
    """
    The full Mismatch model to be returned by the API.
    """
    document: Document
    code_component: CodeComponent