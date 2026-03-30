from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

from .document import Document
from .code_component import CodeComponent


class MismatchDetails(BaseModel):
    expected: str = ""
    actual: str = ""
    evidence_document: str = ""
    evidence_code: str = ""
    suggested_action: str = ""
    # For reverse mismatches: SCOPE_CREEP | IMPLICIT_REQUIREMENT | UNDOCUMENTED
    classification: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class MismatchBase(BaseModel):
    mismatch_type: str
    description: str
    severity: str
    confidence: Optional[str] = None
    details: MismatchDetails
    document_id: int
    code_component_id: int
    direction: Optional[str] = "forward"
    requirement_atom_id: Optional[int] = None


class MismatchCreate(MismatchBase):
    pass


class MismatchUpdate(BaseModel):
    status: Optional[str] = None
    user_notes: Optional[str] = None


class MismatchInDBBase(MismatchBase):
    id: int
    owner_id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    user_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Mismatch(MismatchInDBBase):
    document: Document
    code_component: CodeComponent
