"""
Phase 3 — P3.3 (revised): CRUD for CodeDataFlowEdge.

GAP-4: get_egocentric now returns (edges_in, edges_out) tuple.
GAP-5: count_by_repository returns breakdown dict by edge_type.
GAP-12: All list queries ordered by step_index ASC NULLS LAST.
"""
from typing import List, Optional, Sequence, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.models.code_data_flow_edge import CodeDataFlowEdge

# Canonical analysis_status values (GAP-15A)
ANALYSIS_STATUS_COMPLETE = ("completed", "complete")


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
            .order_by(CodeDataFlowEdge.step_index.asc().nullslast())
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
            .order_by(CodeDataFlowEdge.step_index.asc().nullslast())
            .all()
        )

    def get_egocentric(
        self,
        db: Session,
        *,
        component_id: int,
        tenant_id: int,
    ) -> Tuple[List[CodeDataFlowEdge], List[CodeDataFlowEdge]]:
        """Return (edges_in, edges_out) ordered by step_index ASC NULLS LAST.

        GAP-4 fix: was previously returning a flat list — now returns a tuple
        so callers can cleanly separate inbound callers from outbound callees.
        """
        edges_out = (
            db.query(CodeDataFlowEdge)
            .filter(
                CodeDataFlowEdge.source_component_id == component_id,
                CodeDataFlowEdge.tenant_id == tenant_id,
            )
            .order_by(CodeDataFlowEdge.step_index.asc().nullslast())
            .all()
        )
        edges_in = (
            db.query(CodeDataFlowEdge)
            .filter(
                CodeDataFlowEdge.target_component_id == component_id,
                CodeDataFlowEdge.tenant_id == tenant_id,
            )
            .order_by(CodeDataFlowEdge.step_index.asc().nullslast())
            .all()
        )
        return edges_in, edges_out

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
            .order_by(CodeDataFlowEdge.step_index.asc().nullslast())
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
            .order_by(CodeDataFlowEdge.step_index.asc().nullslast())
            .all()
        )

    def delete_by_component(
        self,
        db: Session,
        *,
        source_component_id: int,
        tenant_id: int,
    ) -> int:
        """Delete all outbound edges for a component before rebuild."""
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
        """Insert a batch of edges. Supports all 7 individual spec columns."""
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
    ) -> dict:
        """Return edge-type breakdown dict — e.g. {"HTTP_TRIGGER": 5, ...}.

        GAP-5 fix: was previously returning a plain int.
        """
        rows = (
            db.query(CodeDataFlowEdge.edge_type, func.count(CodeDataFlowEdge.id))
            .filter(
                CodeDataFlowEdge.repository_id == repository_id,
                CodeDataFlowEdge.tenant_id == tenant_id,
            )
            .group_by(CodeDataFlowEdge.edge_type)
            .all()
        )
        return {edge_type: count for edge_type, count in rows}

    def count_total_by_repository(
        self,
        db: Session,
        *,
        repository_id: int,
        tenant_id: int,
    ) -> int:
        """Plain integer count for stats endpoints."""
        return (
            db.query(CodeDataFlowEdge)
            .filter(
                CodeDataFlowEdge.repository_id == repository_id,
                CodeDataFlowEdge.tenant_id == tenant_id,
            )
            .count()
        )


code_data_flow_edge = CRUDCodeDataFlowEdge()
