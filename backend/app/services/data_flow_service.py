"""
Phase 3 — P3.4: DataFlowService.

Builds a directed request/data flow graph from already-extracted
`CodeComponent.structured_analysis` JSON. NO additional LLM calls are
made — edge extraction is purely deterministic.

Three public methods:
  * build_flow_for_component — idempotent rebuild for one component
  * get_request_trace         — BFS from an ENDPOINT outward
  * render_mermaid            — convert an edge list into Mermaid markup
"""
from __future__ import annotations

from typing import Any, Iterable, Optional
from collections import deque
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.crud.crud_code_data_flow_edge import code_data_flow_edge as crud_edge
from app.models.code_component import CodeComponent
from app.models.code_data_flow_edge import (
    CodeDataFlowEdge,
    VALID_EDGE_TYPES,
    EDGE_LABEL_TEMPLATES,
    SWIMLANE_MAP,
)

logger = get_logger("data_flow_service")

_CACHE_HINTS = ("cache", "redis", "memcache")
_EVENT_HINTS = ("publish", "emit", "kafka", "rabbit", "celery.send_task", "event_bus")
_EXTERNAL_HINTS = ("http://", "https://", "requests.", "httpx.", "urllib", "fetch(")
_MAX_TRACE_DEPTH = 5


class DataFlowService:

    # ---------------------------------------------------------------- build
    def build_flow_for_component(
        self,
        db: Session,
        *,
        component: CodeComponent,
    ) -> int:
        """Idempotent: delete component's outbound edges, then re-derive.

        Returns count of edges written.
        """
        if component is None or not component.structured_analysis:
            return 0

        tenant_id = component.tenant_id
        repository_id = component.repository_id
        analysis: dict[str, Any] = component.structured_analysis or {}

        edges: list[dict[str, Any]] = []

        file_role = self._resolve_file_role(analysis)

        # 1. HTTP_TRIGGER — ENDPOINT files expose API contracts
        if file_role in ("ENDPOINT", None):
            for contract in analysis.get("api_contracts") or []:
                method = (contract.get("method") or "GET").upper()
                path = contract.get("path") or ""
                if not path:
                    continue
                edges.append({
                    "tenant_id": tenant_id,
                    "repository_id": repository_id,
                    "source_component_id": component.id,
                    "target_component_id": component.id,  # self-loop: HTTP into this file
                    "edge_type": "HTTP_TRIGGER",
                    "data_summary": self._truncate(f"{method} {path}"),
                    "edge_metadata": {
                        "method": method,
                        "path": path,
                        "auth_required": contract.get("auth_required"),
                        "status_codes": contract.get("status_codes"),
                        "request_schema": contract.get("request_schema"),
                        "response_schema": contract.get("response_schema"),
                    },
                    "target_ref": None,
                })

        # 2. SERVICE_CALL / SCHEMA_VALIDATION — from explicit outbound_calls
        #    (populated by P3.1 enhanced prompt)
        for call in analysis.get("outbound_calls") or []:
            target_module = call.get("target_module") or ""
            target_function = call.get("target_function") or ""
            caller_function = call.get("caller_function") or ""
            target_id, resolved_ref = self._resolve_component_id(
                db, tenant_id=tenant_id, repository_id=repository_id,
                target_module=target_module, target_function=target_function,
            )
            edge_type = self._classify_outbound(target_module, target_function)
            label = self._build_human_label(
                edge_type,
                target_module=target_module,
                target_function=target_function,
                caller_function=caller_function,
            )
            edges.append({
                "tenant_id": tenant_id,
                "repository_id": repository_id,
                "source_component_id": component.id,
                "target_component_id": target_id,
                "edge_type": edge_type,
                "data_summary": self._truncate(label),
                "edge_metadata": {
                    "caller_function": caller_function,
                    "target_module": target_module,
                    "target_function": target_function,
                    "data_in": call.get("data_in"),
                    "data_out": call.get("data_out"),
                },
                "target_ref": resolved_ref,
            })

        # 3. Fallback SERVICE_CALL — from component_interactions when outbound_calls absent
        if not analysis.get("outbound_calls"):
            for inter in analysis.get("component_interactions") or []:
                itype = (inter.get("interaction_type") or "").lower()
                target_label = inter.get("target") or ""
                if not target_label or itype in ("inherits", "overrides"):
                    continue
                edge_type = "SCHEMA_VALIDATION" if itype == "validates_with" else "SERVICE_CALL"
                target_id, resolved_ref = self._resolve_component_id(
                    db, tenant_id=tenant_id, repository_id=repository_id,
                    target_module="", target_function=target_label,
                )
                edges.append({
                    "tenant_id": tenant_id,
                    "repository_id": repository_id,
                    "source_component_id": component.id,
                    "target_component_id": target_id,
                    "edge_type": edge_type,
                    "data_summary": self._truncate(
                        self._build_human_label(
                            edge_type,
                            target_module="",
                            target_function=target_label,
                            caller_function=inter.get("source") or "",
                        )
                    ),
                    "edge_metadata": {
                        "caller_function": inter.get("source"),
                        "target": target_label,
                        "data_passed": inter.get("data_passed"),
                    },
                    "target_ref": resolved_ref,
                })

        # 4. DB_READ / DB_WRITE — from data_model_relationships (weak) +
        #    data_flows (strong). We prefer data_flows since it has direction.
        for flow in analysis.get("data_flows") or []:
            source = (flow.get("source") or "").lower()
            dest = (flow.get("destination") or "").lower()
            dtype = (flow.get("data_type") or "").lower()
            name = flow.get("name") or ""

            if "db" in dest or "database" in dest or "insert" in dest or "update" in dest or "db write" in dest:
                edges.append(self._db_edge(
                    component, tenant_id, repository_id, "DB_WRITE",
                    table=self._extract_table(dest) or self._extract_table(name),
                    detail=name,
                ))
            elif "db" in source or "database" in source or "query" in source:
                edges.append(self._db_edge(
                    component, tenant_id, repository_id, "DB_READ",
                    table=self._extract_table(source) or self._extract_table(name),
                    detail=name,
                ))
            elif dtype == "db_record" and "write" in name.lower():
                edges.append(self._db_edge(
                    component, tenant_id, repository_id, "DB_WRITE",
                    table=self._extract_table(name), detail=name,
                ))
            elif dtype == "db_record":
                edges.append(self._db_edge(
                    component, tenant_id, repository_id, "DB_READ",
                    table=self._extract_table(name), detail=name,
                ))

            # EXTERNAL_API / CACHE / EVENT hints
            blob = f"{source} {dest} {name}".lower()
            if any(h in blob for h in _EXTERNAL_HINTS):
                edges.append({
                    "tenant_id": tenant_id,
                    "repository_id": repository_id,
                    "source_component_id": component.id,
                    "target_component_id": None,
                    "edge_type": "EXTERNAL_API",
                    "data_summary": self._truncate(
                        EDGE_LABEL_TEMPLATES["EXTERNAL_API"].format(target=name or "external")
                    ),
                    "edge_metadata": {"source": source, "destination": dest, "name": name},
                    "target_ref": name or "external",
                })
            if any(h in blob for h in _CACHE_HINTS):
                edge_type = "CACHE_WRITE" if "write" in blob or "set" in blob else "CACHE_READ"
                edges.append({
                    "tenant_id": tenant_id,
                    "repository_id": repository_id,
                    "source_component_id": component.id,
                    "target_component_id": None,
                    "edge_type": edge_type,
                    "data_summary": self._truncate(
                        EDGE_LABEL_TEMPLATES[edge_type].format(key=name or "cache")
                    ),
                    "edge_metadata": {"name": name},
                    "target_ref": None,
                })
            if any(h in blob for h in _EVENT_HINTS):
                edge_type = "EVENT_CONSUME" if "consume" in blob or "subscribe" in blob else "EVENT_PUBLISH"
                edges.append({
                    "tenant_id": tenant_id,
                    "repository_id": repository_id,
                    "source_component_id": component.id,
                    "target_component_id": None,
                    "edge_type": edge_type,
                    "data_summary": self._truncate(
                        EDGE_LABEL_TEMPLATES[edge_type].format(event=name or "event")
                    ),
                    "edge_metadata": {"name": name},
                    "target_ref": None,
                })

        # Filter out anything with an invalid edge_type (defensive).
        edges = [e for e in edges if e.get("edge_type") in VALID_EDGE_TYPES]

        # Rebuild: drop old + insert new.
        crud_edge.delete_by_component(
            db, source_component_id=component.id, tenant_id=tenant_id,
        )
        count = crud_edge.bulk_create(db, edges=edges)
        logger.info(
            "[P3.4] Rebuilt %d edges for component %s (role=%s)",
            count, component.id, file_role,
        )
        return count

    # ---------------------------------------------------------------- trace
    def get_request_trace(
        self,
        db: Session,
        *,
        component_id: int,
        tenant_id: int,
        max_depth: int = _MAX_TRACE_DEPTH,
    ) -> dict[str, Any]:
        """BFS from an ENDPOINT component outward — returns nodes + edges
        suitable for Mermaid or a D3-style renderer."""
        visited: set[int] = set()
        queue: deque[tuple[int, int]] = deque([(component_id, 0)])
        collected_edges: list[CodeDataFlowEdge] = []
        node_ids: set[int] = {component_id}

        while queue:
            cid, depth = queue.popleft()
            if cid in visited or depth >= max_depth:
                visited.add(cid)
                continue
            visited.add(cid)

            outbound = crud_edge.get_by_source(
                db, source_component_id=cid, tenant_id=tenant_id,
            )
            for edge in outbound:
                collected_edges.append(edge)
                if edge.target_component_id and edge.target_component_id not in visited:
                    node_ids.add(edge.target_component_id)
                    queue.append((edge.target_component_id, depth + 1))

        components = (
            db.query(CodeComponent)
            .filter(
                CodeComponent.id.in_(node_ids),
                CodeComponent.tenant_id == tenant_id,
            )
            .all()
        )
        nodes = [
            {
                "id": c.id,
                "name": c.name,
                "location": c.location,
                "file_role": self._resolve_file_role(c.structured_analysis or {}),
            }
            for c in components
        ]
        return {
            "root_component_id": component_id,
            "nodes": nodes,
            "edges": [self._edge_to_dict(e) for e in collected_edges],
            "depth_reached": min(max_depth, len(visited)),
        }

    # ---------------------------------------------------------------- render
    def render_mermaid(
        self,
        *,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        mode: str = "technical",
    ) -> str:
        """Return Mermaid flowchart markup.

        mode="technical" — shows every edge type with type-coloured labels
        mode="simple"    — collapses CACHE_* and SCHEMA_VALIDATION into the
                           nearest SERVICE_CALL / DB_* for business readers
        """
        if not nodes:
            return "flowchart LR\n    empty[No data flow detected]"

        lines = ["flowchart LR"]

        # Swimlane subgraphs
        lanes: dict[str, list[dict[str, Any]]] = {}
        for n in nodes:
            lane = SWIMLANE_MAP.get(n.get("file_role") or "", "business_layer")
            lanes.setdefault(lane, []).append(n)

        lane_titles = {
            "api_layer": "API Layer",
            "business_layer": "Business Logic",
            "data_layer": "Data Layer",
            "contract_layer": "Contracts",
            "infra_layer": "Infrastructure",
        }
        for lane_id, lane_nodes in lanes.items():
            lines.append(f"    subgraph {lane_id}[\"{lane_titles.get(lane_id, lane_id)}\"]")
            for n in lane_nodes:
                label = self._mermaid_label(n["name"])
                lines.append(f"        n{n['id']}[\"{label}\"]")
                lines.append(f"        click n{n['id']} call dokydocClick(\"{n['id']}\")")
            lines.append("    end")

        # Filter edges by mode
        render_edges = edges
        if mode == "simple":
            render_edges = [
                e for e in edges
                if e["edge_type"] not in ("CACHE_READ", "CACHE_WRITE", "SCHEMA_VALIDATION")
            ]

        for e in render_edges:
            src = f"n{e['source_component_id']}"
            tgt = (
                f"n{e['target_component_id']}"
                if e.get("target_component_id") else f"ext_{e['id']}"
            )
            if not e.get("target_component_id"):
                ext_label = self._mermaid_label(e.get("target_ref") or "external")
                lines.append(f"    {tgt}([\"{ext_label}\"])")
            label = self._mermaid_label(e.get("data_summary") or e["edge_type"])
            arrow = self._mermaid_arrow(e["edge_type"])
            lines.append(f"    {src} {arrow}|\"{label}\"| {tgt}")

        # Edge-type colour classes (technical mode only)
        if mode == "technical":
            lines.extend([
                "    classDef http_trigger fill:#dbeafe,stroke:#2563eb,color:#1e3a8a",
                "    classDef db_edge fill:#fef3c7,stroke:#d97706,color:#78350f",
                "    classDef external fill:#fce7f3,stroke:#db2777,color:#831843",
            ])

        return "\n".join(lines)

    # ---------------------------------------------------------------- helpers
    def _resolve_file_role(self, analysis: dict[str, Any]) -> Optional[str]:
        role = analysis.get("file_role")
        if role:
            return role
        file_type = (analysis.get("language_info") or {}).get("file_type") or ""
        ft = file_type.lower()
        if ft in ("controller", "route", "router"):
            return "ENDPOINT"
        if ft == "service":
            return "SERVICE"
        if ft == "model":
            return "MODEL"
        if ft == "middleware":
            return "MIDDLEWARE"
        if ft in ("utility", "util", "helper"):
            return "UTILITY"
        if ft == "config":
            return "CONFIG"
        if ft == "test":
            return "TEST"
        if ft == "migration":
            return "MIGRATION"
        if analysis.get("api_contracts"):
            return "ENDPOINT"
        return None

    def _classify_outbound(self, target_module: str, target_function: str) -> str:
        blob = f"{target_module} {target_function}".lower()
        if "schema" in blob or "pydantic" in blob or "validate" in blob:
            return "SCHEMA_VALIDATION"
        if any(h in blob for h in _CACHE_HINTS):
            return "CACHE_READ" if "get" in blob else "CACHE_WRITE"
        if any(h in blob for h in _EVENT_HINTS):
            return "EVENT_PUBLISH"
        if any(h in blob for h in _EXTERNAL_HINTS):
            return "EXTERNAL_API"
        if "crud" in blob or "repository" in blob or "query" in blob or "db." in blob:
            return "DB_READ" if "get" in blob or "find" in blob or "read" in blob else "DB_WRITE"
        return "SERVICE_CALL"

    def _resolve_component_id(
        self,
        db: Session,
        *,
        tenant_id: int,
        repository_id: Optional[int],
        target_module: str,
        target_function: str,
    ) -> tuple[Optional[int], Optional[str]]:
        """Best-effort lookup of target CodeComponent in the same repository."""
        if not target_module and not target_function:
            return None, None
        ref = ".".join(filter(None, [target_module, target_function]))
        if not repository_id:
            return None, ref
        # Try to match by location path suffix, else by name.
        q = db.query(CodeComponent).filter(
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.repository_id == repository_id,
        )
        if target_module:
            rows = q.filter(CodeComponent.location.ilike(f"%{target_module.replace('.', '/')}%")).limit(1).all()
            if rows:
                return rows[0].id, ref
        if target_function:
            rows = q.filter(CodeComponent.name.ilike(f"%{target_function}%")).limit(1).all()
            if rows:
                return rows[0].id, ref
        return None, ref

    def _build_human_label(
        self,
        edge_type: str,
        *,
        target_module: str = "",
        target_function: str = "",
        caller_function: str = "",
    ) -> str:
        target = target_function or target_module or "target"
        template = EDGE_LABEL_TEMPLATES.get(edge_type, "{target}")
        try:
            return template.format(
                target=target,
                method="",
                path="",
                table=target,
                key=target,
                event=target,
            )
        except KeyError:
            return f"{caller_function}->{target}" if caller_function else target

    def _db_edge(
        self,
        component: CodeComponent,
        tenant_id: int,
        repository_id: Optional[int],
        edge_type: str,
        *,
        table: Optional[str],
        detail: str,
    ) -> dict[str, Any]:
        return {
            "tenant_id": tenant_id,
            "repository_id": repository_id,
            "source_component_id": component.id,
            "target_component_id": None,
            "edge_type": edge_type,
            "data_summary": self._truncate(
                EDGE_LABEL_TEMPLATES[edge_type].format(table=table or "db")
            ),
            "edge_metadata": {"table": table, "detail": detail},
            "target_ref": table or None,
        }

    def _extract_table(self, text: str) -> Optional[str]:
        if not text:
            return None
        # Heuristic: grab a token that looks like a db.<table> or plural word.
        for token in text.replace(",", " ").replace(".", " ").split():
            t = token.strip("()[]{}'\"`:")
            if t.lower() in ("db", "database", "table", "record", "query", "write", "read"):
                continue
            if t.isidentifier() and len(t) > 2:
                return t
        return None

    def _truncate(self, s: str, limit: int = 250) -> str:
        if not s:
            return ""
        return s if len(s) <= limit else s[: limit - 1] + "…"

    def _mermaid_label(self, s: str) -> str:
        if not s:
            return "node"
        return (
            s.replace('"', "'")
             .replace("\n", " ")
             .replace("|", "/")
             .replace("{", "(")
             .replace("}", ")")[:80]
        )

    def _mermaid_arrow(self, edge_type: str) -> str:
        if edge_type == "HTTP_TRIGGER":
            return "==>"
        if edge_type in ("DB_READ", "DB_WRITE"):
            return "-.->"
        if edge_type == "EXTERNAL_API":
            return "--o"
        return "-->"

    def _edge_to_dict(self, e: CodeDataFlowEdge) -> dict[str, Any]:
        return {
            "id": e.id,
            "source_component_id": e.source_component_id,
            "target_component_id": e.target_component_id,
            "edge_type": e.edge_type,
            "data_summary": e.data_summary,
            "metadata": e.edge_metadata,
            "target_ref": e.target_ref,
        }


data_flow_service = DataFlowService()
