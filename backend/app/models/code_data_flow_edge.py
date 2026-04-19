"""
Phase 3 — P3.2: CodeDataFlowEdge model.

Represents a directed edge between two CodeComponents in the
request/data flow graph. Edges are derived deterministically from the
already-extracted `structured_analysis` JSON — there is no additional
LLM cost associated with building them.

direction: source_component -> target_component
edge_type: one of VALID_EDGE_TYPES (enforced via CHECK constraint)
data_summary: short human-readable label (e.g. "POST /auth/login -> authenticate_user")
metadata: JSONB with extra context (HTTP verb, path, DB table, etc.)
"""
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .code_component import CodeComponent  # noqa: F401
    from .repository import Repository  # noqa: F401


# Keep in sync with the DB CHECK constraint in the migration (s18a1).
VALID_EDGE_TYPES: tuple[str, ...] = (
    "HTTP_TRIGGER",
    "SERVICE_CALL",
    "SCHEMA_VALIDATION",
    "DB_READ",
    "DB_WRITE",
    "EXTERNAL_API",
    "CACHE_READ",
    "CACHE_WRITE",
    "EVENT_PUBLISH",
    "EVENT_CONSUME",
)

# Used by DataFlowService._build_human_label when metadata is thin.
EDGE_LABEL_TEMPLATES: dict[str, str] = {
    "HTTP_TRIGGER": "{method} {path}",
    "SERVICE_CALL": "calls {target}",
    "SCHEMA_VALIDATION": "validates via {target}",
    "DB_READ": "reads {table}",
    "DB_WRITE": "writes {table}",
    "EXTERNAL_API": "calls external {target}",
    "CACHE_READ": "cache.get({key})",
    "CACHE_WRITE": "cache.set({key})",
    "EVENT_PUBLISH": "publishes {event}",
    "EVENT_CONSUME": "consumes {event}",
}

# Maps a file_role (extracted by the enhanced prompt in P3.1) to a
# Mermaid swimlane subgraph id. Used by DataFlowService.render_mermaid.
SWIMLANE_MAP: dict[str, str] = {
    "ENDPOINT": "api_layer",
    "MIDDLEWARE": "api_layer",
    "SERVICE": "business_layer",
    "UTILITY": "business_layer",
    "CRUD": "data_layer",
    "MODEL": "data_layer",
    "SCHEMA": "contract_layer",
    "CONFIG": "infra_layer",
    "TEST": "infra_layer",
    "MIGRATION": "infra_layer",
}


class CodeDataFlowEdge(Base):
    """
    A directed edge in the request/data flow graph.

    The combination (tenant_id, source_component_id, target_component_id,
    edge_type, data_summary) is treated as idempotent — rebuilds delete
    rows by source_component_id and re-insert via bulk_create.
    """
    __tablename__ = "code_data_flow_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)

    # Repository scope — both endpoints of an edge are in the same repo.
    repository_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True, index=True
    )

    source_component_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_components.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Target may be NULL for unresolved externals (e.g. target_module not in repo).
    target_component_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("code_components.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    edge_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Short human label — shown as the Mermaid edge caption.
    data_summary: Mapped[str] = mapped_column(String(255), nullable=False)

    # Structured metadata — HTTP verb, path, DB table, etc.
    edge_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=True)

    # For unresolved targets, keep the raw reference string for UX.
    target_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    source_component: Mapped["CodeComponent"] = relationship(
        "CodeComponent", foreign_keys=[source_component_id]
    )
    target_component: Mapped[Optional["CodeComponent"]] = relationship(
        "CodeComponent", foreign_keys=[target_component_id]
    )

    __table_args__ = (
        CheckConstraint(
            "edge_type IN ('HTTP_TRIGGER','SERVICE_CALL','SCHEMA_VALIDATION',"
            "'DB_READ','DB_WRITE','EXTERNAL_API','CACHE_READ','CACHE_WRITE',"
            "'EVENT_PUBLISH','EVENT_CONSUME')",
            name="ck_data_flow_edge_type",
        ),
        Index("ix_data_flow_edges_tenant_repo", "tenant_id", "repository_id"),
        Index("ix_data_flow_edges_source_type", "source_component_id", "edge_type"),
    )
