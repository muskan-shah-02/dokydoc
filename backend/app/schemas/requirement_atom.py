from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class RequirementAtomBase(BaseModel):
    atom_id: str
    atom_type: str
    content: str
    criticality: str = "standard"
    document_version: Optional[str] = None


class RequirementAtomCreate(RequirementAtomBase):
    document_id: int


class RequirementAtomInDB(RequirementAtomBase):
    id: int
    tenant_id: int
    document_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequirementAtom(RequirementAtomInDB):
    pass
