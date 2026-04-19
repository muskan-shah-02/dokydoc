"use client";

import Link from "next/link";
import { FlowEdge, FlowNode } from "@/hooks/useDataFlow";
import { Badge } from "@/components/ui/badge";

const EDGE_COLOURS: Record<string, string> = {
  HTTP_TRIGGER:       "bg-blue-100 text-blue-800",
  SERVICE_CALL:       "bg-purple-100 text-purple-800",
  SCHEMA_VALIDATION:  "bg-gray-100 text-gray-700",
  DB_READ:            "bg-amber-100 text-amber-800",
  DB_WRITE:           "bg-orange-100 text-orange-800",
  EXTERNAL_API:       "bg-pink-100 text-pink-800",
  CACHE_READ:         "bg-teal-100 text-teal-700",
  CACHE_WRITE:        "bg-cyan-100 text-cyan-800",
  EVENT_PUBLISH:      "bg-green-100 text-green-800",
  EVENT_CONSUME:      "bg-lime-100 text-lime-800",
};

interface EdgeListPanelProps {
  edges: FlowEdge[];
  nodes: FlowNode[];
  focusedComponentId?: number;
  onNodeClick?: (id: number) => void;
}

function nodeById(nodes: FlowNode[], id: number | null): FlowNode | undefined {
  if (id == null) return undefined;
  return nodes.find((n) => (n as any).component_id === id || (n as any).id === id);
}

function NodeLink({
  nodes, id, fallback, onClick,
}: {
  nodes: FlowNode[]; id: number | null;
  fallback?: string; onClick?: (id: number) => void;
}) {
  if (id == null) {
    return <span className="text-gray-400 text-xs">{fallback ?? "external"}</span>;
  }
  const node = nodeById(nodes, id);
  const name = node?.name ?? fallback ?? `#${id}`;
  return (
    <Link
      href={`/dashboard/code/${id}`}
      className="text-xs text-violet-600 hover:underline truncate max-w-[120px]"
      onClick={(e) => { if (onClick) { e.preventDefault(); onClick(id); } }}
      title={node?.location}
    >
      {name}
    </Link>
  );
}

function EdgeRow({
  edge, nodes, direction, onNodeClick,
}: {
  edge: FlowEdge; nodes: FlowNode[];
  direction: "out" | "in"; onNodeClick?: (id: number) => void;
}) {
  const colourClass = EDGE_COLOURS[edge.edge_type] ?? "bg-gray-100 text-gray-700";
  const linkedId = direction === "out" ? edge.target_component_id : edge.source_component_id;
  const extName = (edge as any).external_target_name;
  const humanLabel = (edge as any).human_label || edge.data_summary;
  const dataIn = (edge as any).data_in_description;
  const dataOut = (edge as any).data_out_description;
  const srcFn = (edge as any).source_function;
  const tgtFn = (edge as any).target_function;

  return (
    <li className="p-2 rounded border border-gray-100 hover:bg-gray-50 space-y-1 text-xs">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge className={`text-[10px] px-1.5 py-0 font-mono shrink-0 ${colourClass}`}>
          {edge.edge_type}
        </Badge>
        {(edge as any).step_index != null && (
          <span className="text-gray-300 font-mono text-[10px]">#{(edge as any).step_index}</span>
        )}
        {/* GAP-8: link to component page */}
        <NodeLink
          nodes={nodes} id={linkedId}
          fallback={extName ?? (direction === "out" ? "target" : "source")}
          onClick={onNodeClick}
        />
      </div>

      {/* Human label */}
      {humanLabel && (
        <p className="text-gray-600 italic">{humanLabel}</p>
      )}

      {/* Function context */}
      {(srcFn || tgtFn) && (
        <p className="text-gray-400 font-mono">
          {srcFn && <span>{srcFn}()</span>}
          {srcFn && tgtFn && <span className="mx-1">→</span>}
          {tgtFn && <span>{tgtFn}()</span>}
        </p>
      )}

      {/* GAP-8: data_in / data_out descriptions */}
      {dataIn && (
        <p className="text-gray-500">
          <span className="font-medium text-gray-400">in: </span>{dataIn}
        </p>
      )}
      {dataOut && (
        <p className="text-gray-500">
          <span className="font-medium text-gray-400">out: </span>{dataOut}
        </p>
      )}
    </li>
  );
}

/**
 * P3.8 (revised): Two-column Calls / Called By panel.
 * GAP-8: Links on target names, data_in/data_out descriptions shown.
 */
export function EdgeListPanel({
  edges, nodes, focusedComponentId, onNodeClick,
}: EdgeListPanelProps) {
  const outbound = edges.filter((e) => e.source_component_id === focusedComponentId);
  const inbound  = edges.filter((e) => e.target_component_id === focusedComponentId);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Calls ({outbound.length})
        </h4>
        {outbound.length === 0
          ? <p className="text-sm text-gray-400 italic">No outbound calls detected</p>
          : (
            <ul className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {outbound.map((e) => (
                <EdgeRow key={e.id} edge={e} nodes={nodes} direction="out" onNodeClick={onNodeClick} />
              ))}
            </ul>
          )}
      </div>

      <div>
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Called By ({inbound.length})
        </h4>
        {inbound.length === 0
          ? <p className="text-sm text-gray-400 italic">No inbound callers detected</p>
          : (
            <ul className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {inbound.map((e) => (
                <EdgeRow key={e.id} edge={e} nodes={nodes} direction="in" onNodeClick={onNodeClick} />
              ))}
            </ul>
          )}
      </div>
    </div>
  );
}
