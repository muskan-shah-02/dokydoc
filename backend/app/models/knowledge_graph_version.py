"""
Knowledge Graph Version Model

Stores pre-built graph snapshots for fast rendering and versioning.
Each version captures the full graph (nodes + edges) for a source entity
(code component or document) at a point in time.

Enables:
- Fast graph loading (~50ms from pre-built JSON vs ~500ms from DB rebuild)
- Version history for change tracking
- Delta computation between versions for diff views
- Branch comparison (old graph vs new graph after re-analysis)
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base_class import Base


class KnowledgeGraphVersion(Base):
    __tablename__ = "knowledge_graph_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # What this graph is for: "component" (code file) or "document"
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # ID of the code_component or document
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Version tracking
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Pre-built graph data: { nodes: [...], edges: [...], metadata: {...} }
    graph_data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # SHA256 hash of graph_data for fast change detection
    graph_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Delta from previous version: { added_nodes, removed_nodes, added_edges, removed_edges, summary }
    graph_delta: Mapped[dict] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self):
        return (
            f"<KnowledgeGraphVersion(id={self.id}, source={self.source_type}:{self.source_id}, "
            f"v={self.version}, current={self.is_current})>"
        )
