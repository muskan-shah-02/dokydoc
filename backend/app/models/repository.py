"""
Repository Model (SPRINT 3: ARCH-04)

Represents a code repository (GitHub, GitLab, etc.) that contains multiple files.
This is the parent entity for scalable code analysis — the Repo Agent analyzes
files within a repository, creating CodeComponent records for each.

Relationship:
  Repository (1) ---> (N) CodeComponent (via repository_id FK)
"""

from typing import List, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

if TYPE_CHECKING:
    from .code_component import CodeComponent


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Analysis tracking
    analysis_status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False, index=True
    )  # pending, analyzing, completed, failed
    last_analyzed_commit: Mapped[str] = mapped_column(String(100), nullable=True)
    total_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    analyzed_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    # Skipped files — tracked but not evaluated (binary, compiled, images, etc.)
    skipped_files: Mapped[list] = mapped_column(JSONB, nullable=True)

    # Language breakdown from pre-analysis scan (populated before LLM analysis runs)
    # e.g. {"python": 246, "typescript": 105, "markdown": 21}
    analyze_language_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Synthesis (Reduce Phase — combines per-file analyses into System Architecture)
    synthesis_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
    synthesis_status: Mapped[str] = mapped_column(String(50), nullable=True)
    # synthesis_status: null → "running" → "completed" | "failed"

    # Owner
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    def __repr__(self):
        return f"<Repository(id={self.id}, name='{self.name}', status='{self.analysis_status}')>"
