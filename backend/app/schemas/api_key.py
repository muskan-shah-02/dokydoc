"""
Pydantic schemas for API Key management.
Sprint 8: API Key Authentication.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    expires_days: Optional[int] = Field(None, ge=1, le=365)


class ApiKeyResponse(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    name: str
    key_prefix: str
    is_active: bool
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    request_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned only at creation — includes the raw key (never stored)."""
    raw_key: str


class ApiKeyListResponse(BaseModel):
    api_keys: list[ApiKeyResponse]
    total: int
