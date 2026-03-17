"""
GeneratedDoc model — stores AI-generated documentation artifacts.
Sprint 8: Auto Docs (Module 12).

doc_type values (Sprint A): component_spec, architecture_diagram, api_summary
doc_type values (Sprint B): brd, test_cases, data_models
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class GeneratedDoc(Base):
    __tablename__ = "generated_docs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # What was used as source context
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)  # "document" | "repository"
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # What was generated
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # component_spec | architecture_diagram | api_summary | brd | test_cases | data_models

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Markdown output
    doc_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)  # tokens, cost, etc.

    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    # completed | failed | generating

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
