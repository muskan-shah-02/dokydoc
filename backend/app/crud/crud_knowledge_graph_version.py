"""
CRUD operations for KnowledgeGraphVersion.

Handles graph snapshot storage, versioning, and delta computation.
"""

import hashlib
import json
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from app.models.knowledge_graph_version import KnowledgeGraphVersion


class CRUDKnowledgeGraphVersion:

    def __init__(self):
        self.model = KnowledgeGraphVersion

    def get_current(
        self, db: Session, *, source_type: str, source_id: int, tenant_id: int
    ) -> Optional[KnowledgeGraphVersion]:
        """Get the current (latest) graph version for a source entity."""
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.source_type == source_type,
            self.model.source_id == source_id,
            self.model.is_current == True,
        ).first()

    def get_history(
        self, db: Session, *, source_type: str, source_id: int, tenant_id: int
    ) -> List[KnowledgeGraphVersion]:
        """Get all versions for a source entity, newest first."""
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.source_type == source_type,
            self.model.source_id == source_id,
        ).order_by(self.model.version.desc()).all()

    def get_by_version(
        self, db: Session, *, source_type: str, source_id: int,
        version: int, tenant_id: int
    ) -> Optional[KnowledgeGraphVersion]:
        """Get a specific version."""
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id,
            self.model.source_type == source_type,
            self.model.source_id == source_id,
            self.model.version == version,
        ).first()

    def save_version(
        self, db: Session, *, source_type: str, source_id: int,
        tenant_id: int, graph_data: dict
    ) -> KnowledgeGraphVersion:
        """
        Save a new graph version. If the graph hasn't changed (same hash),
        returns the existing current version without creating a new one.

        If changed:
        1. Marks old current as not-current
        2. Computes delta (added/removed nodes and edges)
        3. Creates new version with is_current=True
        """
        new_hash = self._compute_hash(graph_data)

        # Check if current version exists and has same hash
        current = self.get_current(
            db, source_type=source_type, source_id=source_id, tenant_id=tenant_id
        )

        if current and current.graph_hash == new_hash:
            return current  # No changes — skip version creation

        # Compute version number and delta
        next_version = (current.version + 1) if current else 1
        delta = self._compute_delta(current.graph_data, graph_data) if current else None

        # Mark old version as not-current
        if current:
            current.is_current = False
            db.add(current)

        # Create new version
        new_version = self.model(
            tenant_id=tenant_id,
            source_type=source_type,
            source_id=source_id,
            version=next_version,
            is_current=True,
            graph_data=graph_data,
            graph_hash=new_hash,
            graph_delta=delta,
        )
        db.add(new_version)
        db.flush()
        return new_version

    def get_diff(
        self, db: Session, *, source_type: str, source_id: int,
        version_a: int, version_b: int, tenant_id: int
    ) -> Optional[dict]:
        """Compute delta between any two versions."""
        va = self.get_by_version(
            db, source_type=source_type, source_id=source_id,
            version=version_a, tenant_id=tenant_id
        )
        vb = self.get_by_version(
            db, source_type=source_type, source_id=source_id,
            version=version_b, tenant_id=tenant_id
        )
        if not va or not vb:
            return None
        return self._compute_delta(va.graph_data, vb.graph_data)

    @staticmethod
    def _compute_hash(graph_data: dict) -> str:
        """SHA256 hash of graph data for change detection."""
        # Sort keys for deterministic hashing
        canonical = json.dumps(graph_data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _compute_delta(old_data: dict, new_data: dict) -> dict:
        """Compute what changed between two graph versions."""
        old_nodes = {n.get("id", n.get("name", "")): n for n in old_data.get("nodes", [])}
        new_nodes = {n.get("id", n.get("name", "")): n for n in new_data.get("nodes", [])}

        old_edges = {
            f"{e.get('source', '')}→{e.get('target', '')}:{e.get('type', '')}": e
            for e in old_data.get("edges", [])
        }
        new_edges = {
            f"{e.get('source', '')}→{e.get('target', '')}:{e.get('type', '')}": e
            for e in new_data.get("edges", [])
        }

        added_nodes = [new_nodes[k] for k in set(new_nodes) - set(old_nodes)]
        removed_nodes = [old_nodes[k] for k in set(old_nodes) - set(new_nodes)]
        added_edges = [new_edges[k] for k in set(new_edges) - set(old_edges)]
        removed_edges = [old_edges[k] for k in set(old_edges) - set(new_edges)]

        summary_parts = []
        if added_nodes:
            summary_parts.append(f"+{len(added_nodes)} nodes")
        if removed_nodes:
            summary_parts.append(f"-{len(removed_nodes)} nodes")
        if added_edges:
            summary_parts.append(f"+{len(added_edges)} edges")
        if removed_edges:
            summary_parts.append(f"-{len(removed_edges)} edges")

        return {
            "added_nodes": added_nodes,
            "removed_nodes": removed_nodes,
            "added_edges": added_edges,
            "removed_edges": removed_edges,
            "summary": ", ".join(summary_parts) if summary_parts else "No changes",
        }


knowledge_graph_version = CRUDKnowledgeGraphVersion()
