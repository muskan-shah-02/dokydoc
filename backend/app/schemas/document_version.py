"""
Pydantic schemas for Document Version Comparison.
Sprint 8.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DocumentVersionResponse(BaseModel):
    """A single version entry in the version history list."""
    id: int
    document_id: int
    version_number: int
    content_hash: str
    file_size: Optional[int] = None
    original_filename: Optional[str] = None
    uploaded_by_id: int
    uploaded_by_email: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentVersionListResponse(BaseModel):
    """List of document versions."""
    versions: List[DocumentVersionResponse]
    total: int


class DocumentDiffRequest(BaseModel):
    """Request to compare two specific versions."""
    version_a: int = Field(..., description="Version number of the older/left version")
    version_b: int = Field(..., description="Version number of the newer/right version")


class DiffLine(BaseModel):
    """A single line in a diff result."""
    line_number: int
    content: str
    change_type: str  # "added" | "removed" | "unchanged" | "context"


class DocumentDiffResponse(BaseModel):
    """Side-by-side diff between two document versions."""
    version_a: int
    version_b: int
    document_id: int
    # Unified diff lines for rendering
    lines_a: List[DiffLine]  # Left side (older version)
    lines_b: List[DiffLine]  # Right side (newer version)
    stats: dict  # {added_count, removed_count, unchanged_count, change_pct}
