"""
Pydantic schemas for Approval Workflow.
Sprint 6.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ApprovalCreate(BaseModel):
    """Schema for creating a new approval request."""
    entity_type: str  # "document" | "repository" | "mismatch_resolution" | "requirement_trace" | "validation_report"
    entity_id: int
    entity_name: Optional[str] = None
    approval_level: int = 1
    request_notes: Optional[str] = None


class ApprovalResolve(BaseModel):
    """Schema for resolving (approve/reject/request revision) an approval."""
    resolution_notes: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Schema for approval in API responses."""
    id: int
    tenant_id: int
    entity_type: str
    entity_id: int
    entity_name: Optional[str] = None
    status: str
    requested_by_id: int
    requested_by_email: Optional[str] = None
    resolved_by_id: Optional[int] = None
    resolved_by_email: Optional[str] = None
    approval_level: int
    request_notes: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApprovalStatsResponse(BaseModel):
    """Schema for approval statistics."""
    total: int
    pending: int
    approved: int
    rejected: int
    revision_requested: int
    by_entity_type: dict
