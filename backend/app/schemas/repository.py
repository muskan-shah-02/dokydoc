"""
SPRINT 3: Repository Schemas (ARCH-04)

Pydantic schemas for Repository onboarding, update, and API responses.
"""

from pydantic import BaseModel, field_validator
from typing import Any, Dict, Optional
from datetime import datetime
import re


# --- Create ---
class RepositoryCreate(BaseModel):
    name: str
    url: str
    default_branch: Optional[str] = "main"
    description: Optional[str] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Basic URL validation for git repositories."""
        if not v.strip():
            raise ValueError("Repository URL cannot be empty")
        # Accept HTTPS git URLs, SSH git@, or local paths
        if not (v.startswith("http") or v.startswith("git@") or v.startswith("/")):
            raise ValueError("Invalid repository URL format")
        return v.strip()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Repository name cannot be empty")
        return v.strip()


# --- Update ---
class RepositoryUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    default_branch: Optional[str] = None
    description: Optional[str] = None


# --- Response ---
class RepositoryResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    url: str
    default_branch: str
    description: Optional[str] = None
    analysis_status: str
    last_analyzed_commit: Optional[str] = None
    total_files: int
    analyzed_files: int
    total_ai_cost_inr: Optional[float] = None
    error_message: Optional[str] = None
    synthesis_data: Optional[Dict[str, Any]] = None
    synthesis_status: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Response with progress percentage ---
class RepositoryWithProgress(RepositoryResponse):
    """Extended response that includes a computed progress percentage."""
    progress_percent: Optional[float] = None

    @classmethod
    def from_repo(cls, repo) -> "RepositoryWithProgress":
        data = {c.name: getattr(repo, c.name) for c in repo.__table__.columns}
        if repo.total_files > 0:
            data["progress_percent"] = round(
                (repo.analyzed_files / repo.total_files) * 100, 1
            )
        else:
            data["progress_percent"] = 0.0
        return cls(**data)
