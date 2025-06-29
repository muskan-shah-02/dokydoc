# This is the content for your NEW file at:
# backend/app/schemas/code_component.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# --- Base Schema ---
# Contains fields common to creating and reading code components.
class CodeComponentBase(BaseModel):
    name: str
    component_type: str
    location: str
    version: str

# --- Create Schema ---
# This defines the data your API expects when a user registers a new code component.
class CodeComponentCreate(CodeComponentBase):
    pass

# --- Update Schema ---
# Defines the fields that can be updated. All are optional.
class CodeComponentUpdate(BaseModel):
    name: Optional[str] = None
    component_type: Optional[str] = None
    location: Optional[str] = None
    version: Optional[str] = None

# --- Main Schema for API Responses ---
# This is the schema used when returning code component data from the API.
class CodeComponent(CodeComponentBase):
    id: int
    owner_id: int
    created_at: datetime

    # Pydantic v2 uses `from_attributes` instead of `orm_mode`
    class Config:
        from_attributes = True

