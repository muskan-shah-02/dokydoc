"""
Phase 3 — P3.2 (revised): CodeDataFlowEdge model.

GAP-3 fix: Added 7 individual spec columns (source_function, target_function,
data_in_description, data_out_description, human_label, external_target_name,
step_index) previously missing from the first implementation.

edge_metadata JSONB is retained as a catch-all for extra context (HTTP verb,
path, DB table, etc.) that doesn't fit the structured columns.
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

EDGE_LABEL_TEMPLATES: dict[str, str] = {
    "HTTP_TRIGGER":      "User calls {method} {path}",
    "SERVICE_CALL":      "{source} invokes {target}",
    "SCHEMA_VALIDATION": "Validates data using {target}",
    "DB_READ":           "Reads from {table}",
    "DB_WRITE":          "Saves to {table}",
    "EXTERNAL_API":      "Calls external: {name}",
    "CACHE_READ":        "Reads cache: {key}",
    "CACHE_WRITE":       "Writes cache: {key}",
    "EVENT_PUBLISH":     "Publishes event: {topic}",
    "EVENT_CONSUME":     "Consumes event: {topic}",
}

SWIMLANE_MAP: dict[str, str] = {
    "ENDPOINT":   "api_layer",
    "MIDDLEWARE": "api_layer",
    "SERVICE":    "business_layer",
    "UTILITY":    "business_layer",
    "CRUD":       "data_layer",
    "MODEL":      "data_layer",
    "SCHEMA":     "contract_layer",
    "CONFIG":     "infra_layer",
    "TEST":       "infra_layer",
    "MIGRATION":  "infra_layer",
}


class CodeDataFlowEdge(Base):
    """
    A directed edge in the request/data flow graph.

    Idempotent rebuild: delete rows where source_component_id = X, then
    bulk_create fresh rows from the latest structured_analysis.

    step_index: ordering within a request trace (0-based, NULL = unordered).
    """
    __tablename__ = "code_data_flow_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)

    repository_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_component_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_components.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    target_component_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("code_components.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    edge_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # ---- Per-spec individual columns (GAP-3) ----
    # Function in the SOURCE file that initiates the call
    source_function: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Function in the TARGET file being called
    target_function: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Schema / type passed into the call
    data_in_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Schema / type returned from the call
    data_out_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Human-readable label for Mermaid edge captions
    human_label: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # For unresolved external targets (no DB record)
    external_target_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Ordering within a request trace; NULL = unordered
    step_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Catch-all JSONB for extra context (HTTP verb, path, DB table name, etc.)
    edge_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

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
        Index("ix_data_flow_edges_step", "source_component_id", "step_index"),
    )
