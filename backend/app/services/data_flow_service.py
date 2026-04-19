"""
Phase 3 — P3.4 (revised): DataFlowService.

GAP-7: Full keyword frozensets for CACHE and EVENT detection (was short tuples).
GAP-7: Deduplication guard before bulk_create.
GAP-9: Mermaid uses cylinder shape for MODEL nodes, diamond for externals.
GAP-3: build_flow_for_component populates all 7 individual spec columns.
GAP-12: Edges ordered by step_index in render_mermaid.
"""
from __future__ import annotations

from typing import Any, Optional
from collections import deque
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

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

# ── GAP-7: Exhaustive keyword frozensets ─────────────────────────────────────

_CACHE_READ_KEYWORDS = frozenset({
    "redis.get", "cache.get", "get_cache", "cache_get", "memcache.get",
    "client.get", "hget", "lrange", "smembers", "zrange", "getex",
    "cache.fetch", "r.get", "cache_service.get",
})
_CACHE_WRITE_KEYWORDS = frozenset({
    "redis.set", "cache.set", "set_cache", "cache_set", "memcache.set",
    "client.set", "hset", "lpush", "rpush", "sadd", "zadd", "setex",
    "cache.delete", "redis.delete", "cache_invalidate", "r.set", "r.setex",
    "cache_service.set", "cache_service.delete",
})
_CACHE_SERVICE_KEYWORDS = frozenset({
    "redis", "cache", "memcache", "memcached", "cacheservice", "redisclient",
    "cache_service", "r.get", "r.set",
})
_EVENT_PUBLISH_KEYWORDS = frozenset({
    ".delay(", ".apply_async(", "producer.send", "publish(",
    "sns.publish", "sqs.send_message", "rabbitmq.publish",
    "channel.publish", "task.apply_async", "celery_app.send_task",
    "send_task(", "emit(", "dispatch(",
})
_EVENT_CONSUME_KEYWORDS = frozenset({
    "@celery_app.task", "@app.task", "@shared_task", "@task(",
    "consumer.poll", "consumer.consume", "subscribe(",
    "sqs.receive_message", "channel.consume", "@dramatiq.actor",
    "@huey.task", "@rq.job",
})
_EVENT_SERVICE_KEYWORDS = frozenset({
    "celery", "kafka", "rabbitmq", "sqs", "sns", "dramatiq", "rq.",
    "huey", "event", "message_queue", "messagequeue", "broker",
    "pubsub", "pub_sub",
})
_EXTERNAL_KEYWORDS = frozenset({
    "http://", "https://", "requests.", "httpx.", "urllib",
    "fetch(", "axios.", "got(", "superagent",
})

_MAX_TRACE_DEPTH = 5

# ── Swimlane UI labels ────────────────────────────────────────────────────────
_LANE_LABELS = {
    "api_layer":      "API Layer",
    "business_layer": "Business Logic",
    "data_layer":     "Data Layer",
    "contract_layer": "Contracts",
    "infra_layer":    "Infrastructure",
}


class DataFlowService:

    # ── build ─────────────────────────────────────────────────────────────────

    def build_flow_for_component(
        self,
        db: Session,
        *,
        component: CodeComponent,
    ) -> int:
        """Idempotent: delete outbound edges then re-derive from structured_analysis.

        Populates all 7 individual spec columns (GAP-3 fix).
        Deduplication guard prevents duplicate rows (GAP-7 fix).
        Returns count of edges written.
        """
        if component is None or not component.structured_analysis:
            return 0

        tenant_id = component.tenant_id
        repository_id = component.repository_id
        analysis: dict[str, Any] = component.structured_analysis or {}
        file_role = self._resolve_file_role(analysis)

        edges: list[dict[str, Any]] = []
        step = 0  # monotonically increasing step_index within this component

        # 1. HTTP_TRIGGER — from api_contracts
        if file_role in ("ENDPOINT", None):
            for contract in analysis.get("api_contracts") or []:
                method = (contract.get("method") or "GET").upper()
                path = contract.get("path") or ""
                if not path:
                    continue
                label = EDGE_LABEL_TEMPLATES["HTTP_TRIGGER"].format(
                    method=method, path=path)
                edges.append(self._make_edge(
                    tenant_id=tenant_id, repository_id=repository_id,
                    source_id=component.id, target_id=component.id,
                    edge_type="HTTP_TRIGGER",
                    source_function=None, target_function=None,
                    data_in=contract.get("request_schema"),
                    data_out=contract.get("response_schema"),
                    human_label=label, external_name=None, step=step,
                    metadata={
                        "method": method, "path": path,
                        "auth_required": contract.get("auth_required"),
                        "status_codes": contract.get("status_codes"),
                    },
                ))
                step += 1

        # 2. SERVICE_CALL / SCHEMA_VALIDATION — from outbound_calls (P3.1)
        for call in analysis.get("outbound_calls") or []:
            target_module = call.get("target_module") or ""
            target_fn = call.get("target_function") or ""
            caller_fn = call.get("caller_function") or ""
            target_id, resolved_ref = self._resolve_component_id(
                db, tenant_id=tenant_id, repository_id=repository_id,
                target_module=target_module, target_function=target_fn,
            )
            edge_type = self._classify_outbound(target_module, target_fn)
            label = EDGE_LABEL_TEMPLATES.get(edge_type, "{target}").format(
                source=caller_fn, target=target_fn or target_module,
                method="", path="", table=target_fn, key=target_fn,
                name=target_fn, topic=target_fn,
            )
            edges.append(self._make_edge(
                tenant_id=tenant_id, repository_id=repository_id,
                source_id=component.id, target_id=target_id,
                edge_type=edge_type,
                source_function=caller_fn or None,
                target_function=target_fn or None,
                data_in=call.get("data_in"), data_out=call.get("data_out"),
                human_label=label,
                external_name=resolved_ref if not target_id else None,
                step=step, metadata={
                    "target_module": target_module,
                    "target_function": target_fn,
                },
            ))
            step += 1

        # 3. Fallback SERVICE_CALL — from component_interactions when no outbound_calls
        if not analysis.get("outbound_calls"):
            for inter in analysis.get("component_interactions") or []:
                itype = (inter.get("interaction_type") or "").lower()
                target_label = inter.get("target") or ""
                source_label = inter.get("source") or ""
                if not target_label or itype in ("inherits", "overrides"):
                    continue
                edge_type = (
                    "SCHEMA_VALIDATION" if itype == "validates_with" else "SERVICE_CALL"
                )
                target_id, resolved_ref = self._resolve_component_id(
                    db, tenant_id=tenant_id, repository_id=repository_id,
                    target_module="", target_function=target_label,
                )
                label = EDGE_LABEL_TEMPLATES[edge_type].format(
                    source=source_label, target=target_label,
                    method="", path="", table=target_label, key=target_label,
                    name=target_label, topic=target_label,
                )
                edges.append(self._make_edge(
                    tenant_id=tenant_id, repository_id=repository_id,
                    source_id=component.id, target_id=target_id,
                    edge_type=edge_type,
                    source_function=source_label or None,
                    target_function=target_label or None,
                    data_in=inter.get("data_passed"), data_out=None,
                    human_label=label,
                    external_name=resolved_ref if not target_id else None,
                    step=step, metadata={"interaction_type": itype},
                ))
                step += 1

        # 4. DB / External / Cache / Event — from data_flows
        for flow in analysis.get("data_flows") or []:
            src_text = (flow.get("source") or "").lower()
            dst_text = (flow.get("destination") or "").lower()
            dtype = (flow.get("data_type") or "").lower()
            name = flow.get("name") or ""
            blob = f"{src_text} {dst_text} {name}".lower()

            if "db" in dst_text or "write" in dst_text or "insert" in dst_text:
                edges.append(self._db_edge(
                    component, tenant_id, repository_id, "DB_WRITE",
                    table=self._extract_table(dst_text) or self._extract_table(name),
                    detail=name, step=step,
                ))
                step += 1
            elif "db" in src_text or "query" in src_text or dtype == "db_record":
                edges.append(self._db_edge(
                    component, tenant_id, repository_id, "DB_READ",
                    table=self._extract_table(src_text) or self._extract_table(name),
                    detail=name, step=step,
                ))
                step += 1

            # External API
            if any(h in blob for h in _EXTERNAL_KEYWORDS):
                edges.append(self._make_edge(
                    tenant_id=tenant_id, repository_id=repository_id,
                    source_id=component.id, target_id=None,
                    edge_type="EXTERNAL_API",
                    source_function=None, target_function=None,
                    data_in=None, data_out=None,
                    human_label=EDGE_LABEL_TEMPLATES["EXTERNAL_API"].format(
                        name=name or "external"),
                    external_name=name or "external",
                    step=step, metadata={"source": src_text, "destination": dst_text},
                ))
                step += 1

            # Cache
            cache_rw = self._detect_cache_rw(blob)
            if cache_rw:
                edges.append(self._make_edge(
                    tenant_id=tenant_id, repository_id=repository_id,
                    source_id=component.id, target_id=None,
                    edge_type=cache_rw,
                    source_function=None, target_function=None,
                    data_in=None, data_out=None,
                    human_label=EDGE_LABEL_TEMPLATES[cache_rw].format(key=name or "cache"),
                    external_name="redis/cache",
                    step=step, metadata={"name": name},
                ))
                step += 1

            # Event
            event_type = self._detect_event_type(blob)
            if event_type:
                edges.append(self._make_edge(
                    tenant_id=tenant_id, repository_id=repository_id,
                    source_id=component.id, target_id=None,
                    edge_type=event_type,
                    source_function=None, target_function=None,
                    data_in=None, data_out=None,
                    human_label=EDGE_LABEL_TEMPLATES[event_type].format(topic=name or "event"),
                    external_name=name or "event-bus",
                    step=step, metadata={"name": name},
                ))
                step += 1

        # ── GAP-7: Deduplication guard ────────────────────────────────────────
        seen: set[tuple] = set()
        deduped: list[dict] = []
        for e in edges:
            if e.get("edge_type") not in VALID_EDGE_TYPES:
                continue
            key = (
                e["source_component_id"],
                e.get("target_component_id"),
                e["edge_type"],
                e.get("external_target_name") or "",
                e.get("source_function") or "",
            )
            if key not in seen:
                seen.add(key)
                deduped.append(e)

        crud_edge.delete_by_component(
            db, source_component_id=component.id, tenant_id=tenant_id,
        )
        count = crud_edge.bulk_create(db, edges=deduped)
        logger.info(
            "[P3.4] Built %d edges for component %s (role=%s, step_count=%d)",
            count, component.id, file_role, step,
        )
        return count

    # ── request trace ─────────────────────────────────────────────────────────

    def get_request_trace(
        self,
        db: Session,
        *,
        component_id: int,
        tenant_id: int,
        max_depth: int = _MAX_TRACE_DEPTH,
    ) -> dict[str, Any]:
        """BFS from an ENDPOINT component — returns nodes, edges, both mermaid modes."""
        visited: set[int] = set()
        queue: deque[tuple[int, int]] = deque([(component_id, 0)])
        collected: list[CodeDataFlowEdge] = []
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
                collected.append(edge)
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
        nodes = [self._component_to_node(c) for c in components]
        edge_dicts = [self._edge_to_dict(e) for e in collected]

        edges_built_at = None
        if collected:
            edges_built_at = max(
                (e.created_at for e in collected if e.created_at), default=None
            )

        return {
            "root_component_id": component_id,
            "start_component_id": component_id,
            "depth": min(max_depth, len(visited)),
            "nodes": nodes,
            "edges": edge_dicts,
            "mermaid_technical": self.render_mermaid(nodes=nodes, edges=edge_dicts, mode="technical"),
            "mermaid_simple": self.render_mermaid(nodes=nodes, edges=edge_dicts, mode="simple"),
            "total_nodes": len(nodes),
            "total_edges": len(edge_dicts),
            "edges_built_at": edges_built_at.isoformat() if edges_built_at else None,
            "depth_reached": min(max_depth, len(visited)),
        }

    # ── render_mermaid ────────────────────────────────────────────────────────

    def render_mermaid(
        self,
        *,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        mode: str = "technical",
    ) -> str:
        """Return Mermaid flowchart LR markup.

        GAP-9 fix: MODEL nodes → cylinder [("name")], external nodes → {name}.
        GAP-12 fix: edges sorted by step_index.
        """
        if not nodes:
            return "flowchart LR\n    empty[No data flow detected]"

        lines = ["flowchart LR"]

        # Swimlane subgraphs
        lanes: dict[str, list[dict]] = {}
        for n in nodes:
            lane = SWIMLANE_MAP.get(n.get("file_role") or "", "business_layer")
            lanes.setdefault(lane, []).append(n)

        for lane_id, lane_nodes in lanes.items():
            lines.append(f'    subgraph {lane_id}["{_LANE_LABELS.get(lane_id, lane_id)}"]')
            for n in lane_nodes:
                nid = f"n{n.get('component_id') or n.get('id') or id(n)}"
                label = self._mermaid_label(n["name"])
                role = n.get("file_role") or ""
                # GAP-9: cylinder shape for database/model nodes
                if role in ("MODEL", "MIGRATION"):
                    lines.append(f'        {nid}[("{label}")]')
                else:
                    lines.append(f'        {nid}["{label}"]')
                cid = n.get("component_id") or n.get("id")
                if cid:
                    lines.append(f'        click {nid} call dokydocClick("{cid}")')
            lines.append("    end")

        # Filter edges by mode
        render_edges = edges
        if mode == "simple":
            render_edges = [
                e for e in edges
                if e["edge_type"] not in ("CACHE_READ", "CACHE_WRITE", "SCHEMA_VALIDATION")
            ]

        # GAP-12: sort by step_index
        def _step(e: dict) -> int:
            v = e.get("step_index")
            return v if v is not None else 9999

        render_edges = sorted(render_edges, key=_step)

        for e in render_edges:
            src = f"n{e['source_component_id']}"
            if e.get("target_component_id"):
                tgt = f"n{e['target_component_id']}"
            else:
                # GAP-9: external nodes use diamond/stadium shape
                ext_id = f"ext_{e.get('id', id(e))}"
                ext_label = self._mermaid_label(
                    e.get("external_target_name") or
                    e.get("target_ref") or "external"
                )
                # diamond shape for externals
                lines.append(f'    {ext_id}{{"{ext_label}"}}')
                tgt = ext_id

            label = self._mermaid_label(
                e.get("human_label") or
                e.get("data_summary") or
                e["edge_type"]
            )
            arrow = self._mermaid_arrow(e["edge_type"])
            lines.append(f'    {src} {arrow}|"{label}"| {tgt}')

        # Colour classes (technical mode)
        if mode == "technical":
            lines.extend([
                "    classDef http_trigger fill:#dbeafe,stroke:#2563eb,color:#1e3a8a",
                "    classDef db_edge fill:#fef3c7,stroke:#d97706,color:#78350f",
                "    classDef external fill:#fce7f3,stroke:#db2777,color:#831843",
                "    classDef model_node fill:#f0fdf4,stroke:#16a34a,color:#14532d",
            ])

        return "\n".join(lines)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _resolve_file_role(self, analysis: dict[str, Any]) -> Optional[str]:
        role = analysis.get("file_role")
        if role:
            return role
        file_type = (analysis.get("language_info") or {}).get("file_type") or ""
        ft = file_type.lower()
        mapping = {
            "controller": "ENDPOINT", "route": "ENDPOINT",
            "router": "ENDPOINT", "handler": "ENDPOINT", "view": "ENDPOINT",
            "service": "SERVICE",
            "schema": "SCHEMA", "serializer": "SCHEMA", "validator": "SCHEMA",
            "model": "MODEL", "entity": "MODEL",
            "repository": "CRUD", "crud": "CRUD", "dao": "CRUD",
            "middleware": "MIDDLEWARE", "interceptor": "MIDDLEWARE",
            "utility": "UTILITY", "util": "UTILITY", "helper": "UTILITY",
            "config": "CONFIG", "settings": "CONFIG", "constants": "CONFIG",
            "test": "TEST", "migration": "MIGRATION",
        }
        if ft in mapping:
            return mapping[ft]
        if analysis.get("api_contracts"):
            return "ENDPOINT"
        return None

    def _classify_outbound(self, target_module: str, target_function: str) -> str:
        blob = f"{target_module} {target_function}".lower()
        if "schema" in blob or "pydantic" in blob or "validate" in blob:
            return "SCHEMA_VALIDATION"
        if any(k in blob for k in _CACHE_READ_KEYWORDS):
            return "CACHE_READ"
        if any(k in blob for k in _CACHE_WRITE_KEYWORDS):
            return "CACHE_WRITE"
        if any(k in blob for k in _CACHE_SERVICE_KEYWORDS):
            return "CACHE_READ"
        if any(k in blob for k in _EVENT_PUBLISH_KEYWORDS):
            return "EVENT_PUBLISH"
        if any(k in blob for k in _EVENT_CONSUME_KEYWORDS):
            return "EVENT_CONSUME"
        if any(k in blob for k in _EXTERNAL_KEYWORDS):
            return "EXTERNAL_API"
        if "crud" in blob or "repository" in blob or "dao" in blob or "db." in blob:
            return "DB_READ" if any(w in blob for w in ("get", "find", "read", "fetch")) else "DB_WRITE"
        return "SERVICE_CALL"

    def _detect_cache_rw(self, blob: str) -> Optional[str]:
        if any(k in blob for k in _CACHE_WRITE_KEYWORDS):
            return "CACHE_WRITE"
        if any(k in blob for k in _CACHE_READ_KEYWORDS):
            return "CACHE_READ"
        if any(k in blob for k in _CACHE_SERVICE_KEYWORDS):
            return "CACHE_READ"
        return None

    def _detect_event_type(self, blob: str) -> Optional[str]:
        if any(k in blob for k in _EVENT_CONSUME_KEYWORDS):
            return "EVENT_CONSUME"
        if any(k in blob for k in _EVENT_PUBLISH_KEYWORDS):
            return "EVENT_PUBLISH"
        if any(k in blob for k in _EVENT_SERVICE_KEYWORDS):
            return "EVENT_PUBLISH"
        return None

    def _resolve_component_id(
        self,
        db: Session,
        *,
        tenant_id: int,
        repository_id: Optional[int],
        target_module: str,
        target_function: str,
    ) -> tuple[Optional[int], Optional[str]]:
        ref = ".".join(filter(None, [target_module, target_function]))
        if not repository_id or not ref:
            return None, ref or None
        q = db.query(CodeComponent).filter(
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.repository_id == repository_id,
        )
        if target_module:
            rows = q.filter(
                CodeComponent.location.ilike(f"%{target_module.replace('.', '/')}%")
            ).limit(1).all()
            if rows:
                return rows[0].id, ref
        if target_function:
            rows = q.filter(
                CodeComponent.name.ilike(f"%{target_function}%")
            ).limit(1).all()
            if rows:
                return rows[0].id, ref
        return None, ref

    def _make_edge(
        self, *, tenant_id, repository_id, source_id, target_id,
        edge_type, source_function, target_function,
        data_in, data_out, human_label, external_name, step, metadata=None,
    ) -> dict:
        return {
            "tenant_id": tenant_id,
            "repository_id": repository_id,
            "source_component_id": source_id,
            "target_component_id": target_id,
            "edge_type": edge_type,
            "source_function": source_function,
            "target_function": target_function,
            "data_in_description": str(data_in)[:500] if data_in else None,
            "data_out_description": str(data_out)[:500] if data_out else None,
            "human_label": self._truncate(human_label, 490) if human_label else None,
            "external_target_name": external_name[:195] if external_name else None,
            "step_index": step,
            "edge_metadata": metadata,
            # data_summary kept for backward compat
            "data_summary": self._truncate(human_label or edge_type, 250),
        }

    def _db_edge(
        self,
        component: CodeComponent,
        tenant_id: int,
        repository_id: Optional[int],
        edge_type: str,
        *,
        table: Optional[str],
        detail: str,
        step: int,
    ) -> dict:
        label = EDGE_LABEL_TEMPLATES[edge_type].format(table=table or "db")
        return self._make_edge(
            tenant_id=tenant_id, repository_id=repository_id,
            source_id=component.id, target_id=None,
            edge_type=edge_type,
            source_function=None, target_function=None,
            data_in=None, data_out=None,
            human_label=label,
            external_name=table,
            step=step,
            metadata={"table": table, "detail": detail},
        )

    def _extract_table(self, text: str) -> Optional[str]:
        if not text:
            return None
        skip = {"db", "database", "table", "record", "query", "write", "read",
                "insert", "update", "select", "delete", "from", "into"}
        for token in text.replace(",", " ").replace(".", " ").split():
            t = token.strip("()[]{}'\"`:")
            if t.lower() in skip:
                continue
            if t.isidentifier() and len(t) > 2:
                return t
        return None

    def _component_to_node(self, c: CodeComponent) -> dict:
        return {
            "component_id": c.id,
            "id": c.id,
            "name": c.name,
            "location": c.location,
            "file_role": self._resolve_file_role(c.structured_analysis or {}),
            "summary": c.summary,
            "is_external": False,
        }

    def _edge_to_dict(self, e: CodeDataFlowEdge) -> dict:
        return {
            "id": e.id,
            "source_component_id": e.source_component_id,
            "target_component_id": e.target_component_id,
            "edge_type": e.edge_type,
            "source_function": e.source_function,
            "target_function": e.target_function,
            "data_in_description": e.data_in_description,
            "data_out_description": e.data_out_description,
            "human_label": e.human_label,
            "external_target_name": e.external_target_name,
            "step_index": e.step_index,
            "data_summary": e.human_label or e.edge_type,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }

    def _truncate(self, s: str, limit: int = 250) -> str:
        if not s:
            return ""
        return s if len(s) <= limit else s[:limit - 1] + "…"

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
        arrows = {
            "HTTP_TRIGGER": "==>",
            "DB_READ": "-.->",
            "DB_WRITE": "-.->",
            "EXTERNAL_API": "--o",
            "CACHE_READ": "-.-",
            "CACHE_WRITE": "-.-",
            "EVENT_PUBLISH": "-->",
            "EVENT_CONSUME": "<--",
        }
        return arrows.get(edge_type, "-->")


data_flow_service = DataFlowService()
