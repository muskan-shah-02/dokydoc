from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime


# --- Initiative Asset Schemas ---

class InitiativeAssetBase(BaseModel):
    initiative_id: int
    asset_type: str = Field(..., pattern="^(DOCUMENT|REPOSITORY)$")
    asset_id: int


class InitiativeAssetCreate(InitiativeAssetBase):
    pass


class InitiativeAssetUpdate(BaseModel):
    is_active: Optional[bool] = None


class InitiativeAssetResponse(InitiativeAssetBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# --- Initiative Schemas ---

class InitiativeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = Field(default="ACTIVE", pattern="^(ACTIVE|COMPLETED|CANCELLED)$")


class InitiativeCreate(InitiativeBase):
    pass


class InitiativeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(ACTIVE|COMPLETED|CANCELLED)$")


class InitiativeResponse(InitiativeBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InitiativeWithAssets(InitiativeResponse):
    assets: List[InitiativeAssetResponse] = []
