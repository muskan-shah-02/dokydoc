# This is the updated content for your file at:
# backend/app/schemas/code_component.py

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

# --- Base Schema ---
# Defines the common properties shared across all related schemas.
class CodeComponentBase(BaseModel):
    name: str
    component_type: str
    location: str
    version: str

# --- Create Schema ---
# Defines the properties required to create a new component.
# This is what the API will expect in the request body on a POST.
class CodeComponentCreate(CodeComponentBase):
    pass

# --- Update Schema ---
# Defines the properties that can be updated. All are optional.
# This is what the API will expect in the request body on a PATCH/PUT.
class CodeComponentUpdate(BaseModel):
    name: Optional[str] = None
    component_type: Optional[str] = None
    location: Optional[str] = None
    version: Optional[str] = None
    summary: Optional[str] = None
    structured_analysis: Optional[Dict[str, Any]] = None
    analysis_status: Optional[str] = None

# --- InDBBase Schema (The one you asked about) ---
# This is a critical addition. It represents all the fields for a component
# as it exists in the database, including auto-generated fields like id, owner_id, etc.
# It serves as a reusable base for any schema that reads from the DB.
class CodeComponentInDBBase(CodeComponentBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # The new analysis fields are included here
    summary: Optional[str] = None
    structured_analysis: Optional[Dict[str, Any]] = None
    analysis_status: str

    class Config:
        # This vital setting allows Pydantic to read data directly from
        # a SQLAlchemy ORM model instance.
        orm_mode = True

# --- Main API Response Schema ---
# This is the final schema that will be used when returning data from the API.
# It inherits everything from our InDBBase and represents a complete object.
class CodeComponent(CodeComponentInDBBase):
    pass

