# This is the content for your NEW file at:
# backend/app/schemas/document_code_link.py

from pydantic import BaseModel

# --- Base Schema ---
# Contains the essential fields needed to describe a link.
class DocumentCodeLinkBase(BaseModel):
    document_id: int
    code_component_id: int

# --- Create Schema ---
# This defines the data your API will expect when creating a new link.
class DocumentCodeLinkCreate(DocumentCodeLinkBase):
    pass

# --- Main Schema for API Responses ---
# This is the schema used when returning link data from the API.
class DocumentCodeLink(DocumentCodeLinkBase):
    id: int

    # Pydantic v2 uses `from_attributes` instead of `orm_mode`
    # to allow creating the schema from a database model instance.
    class Config:
        from_attributes = True

