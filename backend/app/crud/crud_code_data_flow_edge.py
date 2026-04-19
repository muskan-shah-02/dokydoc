"""
Phase 3 — P3.3: CRUD for CodeDataFlowEdge.

Idempotent rebuild pattern: delete edges by source_component_id, then
bulk_create. No UPSERT is necessary because a component's outbound
edges are always rebuilt as a complete set from its structured_analysis.
"""
from typing import List, Optional, Sequence
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.code_data_flow_edge import CodeDataFlowEdge


class CRUDCodeDataFlowEdge:
    def get(self, db: Session, edge_id: int) -> Optional[CodeDataFlowEdge]:
        return db.query(CodeDataFlowEdge).filter(CodeDataFlowEdge.id == edge_id).first()

    def get_by_source(
        self,
        db: Session,
        *,
        source_component_id: int,
        tenant_id: int,
    ) -> List[CodeDataFlowEdge]:
        return (
            db.query(CodeDataFlowEdge)
            .filter(
                CodeDataFlowEdge.source_component_id == source_component_id,
                CodeDataFlowEdge.tenant_id == tenant_id,
            )
            .all()
        )

    def get_by_target(
        self,
        db: Session,
        *,
        target_component_id: int,
        tenant_id: int,
    ) -> List[CodeDataFlowEdge]:
        return (
            db.query(CodeDataFlowEdge)
            .filter(
                CodeDataFlowEdge.target_component_id == target_component_id,
                CodeDataFlowEdge.tenant_id == tenant_id,
            )
            .all()
        )

    def get_egocentric(
        self,
        db: Session,
        *,
        component_id: int,
        tenant_id: int,
    ) -> List[CodeDataFlowEdge]:
        """Return every edge where component is either the source or target."""
        return (
            db.query(CodeDataFlowEdge)
            .filter(
                CodeDataFlowEdge.tenant_id == tenant_id,
                or_(
                    CodeDataFlowEdge.source_component_id == component_id,
                    CodeDataFlowEdge.target_component_id == component_id,
                ),
            )
            .all()
        )

    def get_subgraph(
        self,
        db: Session,
        *,
        component_ids: Sequence[int],
        tenant_id: int,
    ) -> List[CodeDataFlowEdge]:
        """Edges where both endpoints are within the given component set."""
        if not component_ids:
            return []
        ids = list(component_ids)
        return (
            db.query(CodeDataFlowEdge)
            .filter(
                CodeDataFlowEdge.tenant_id == tenant_id,
                CodeDataFlowEdge.source_component_id.in_(ids),
                or_(
                    CodeDataFlowEdge.target_component_id.in_(ids),
                    CodeDataFlowEdge.target_component_id.is_(None),
                ),
            )
            .all()
        )

    def get_by_repository(
        self,
        db: Session,
        *,
        repository_id: int,
        tenant_id: int,
    ) -> List[CodeDataFlowEdge]:
        return (
            db.query(CodeDataFlowEdge)
            .filter(
                CodeDataFlowEdge.repository_id == repository_id,
                CodeDataFlowEdge.tenant_id == tenant_id,
            )
            .all()
        )

    def delete_by_component(
        self,
        db: Session,
        *,
        source_component_id: int,
        tenant_id: int,
    ) -> int:
        """Delete all outbound edges for a component — used before rebuild."""
        deleted = (
            db.query(CodeDataFlowEdge)
            .filter(
                CodeDataFlowEdge.source_component_id == source_component_id,
                CodeDataFlowEdge.tenant_id == tenant_id,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        return deleted

    def bulk_create(
        self,
        db: Session,
        *,
        edges: List[dict],
    ) -> int:
        """Insert a batch of edges. `edges` is a list of dicts matching model cols."""
        if not edges:
            return 0
        objs = [CodeDataFlowEdge(**e) for e in edges]
        db.add_all(objs)
        db.commit()
        return len(objs)

    def count_by_repository(
        self,
        db: Session,
        *,
        repository_id: int,
        tenant_id: int,
    ) -> int:
        return (
            db.query(CodeDataFlowEdge)
            .filter(
                CodeDataFlowEdge.repository_id == repository_id,
                CodeDataFlowEdge.tenant_id == tenant_id,
            )
            .count()
        )


code_data_flow_edge = CRUDCodeDataFlowEdge()
