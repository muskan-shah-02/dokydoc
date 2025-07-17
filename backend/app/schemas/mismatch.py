# This is the content for your NEW file at:
# backend/app/schemas/mismatch.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# --- Base Schema ---
# Contains fields needed to create a new mismatch record.
class MismatchBase(BaseModel):
    mismatch_type: str
    description: str
    document_id: int
    code_component_id: int

# --- Create Schema ---
# This defines the data your API expects when creating a new mismatch.
class MismatchCreate(MismatchBase):
    pass

# --- Update Schema ---
# This defines the fields that can be updated, primarily the status.
class MismatchUpdate(BaseModel):
    status: Optional[str] = None

# --- Main Schema for API Responses ---
# This is the schema used when returning mismatch data from the API.
# It includes all the database fields.
class Mismatch(MismatchBase):
    id: int
    status: str
    detected_at: datetime

    # Pydantic v2 uses `from_attributes` to create the schema from a DB model.
    class Config:
        from_attributes = True

