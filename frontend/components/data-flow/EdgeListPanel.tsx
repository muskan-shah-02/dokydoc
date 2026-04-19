"use client";

import { FlowEdge, FlowNode } from "@/hooks/useDataFlow";
import { Badge } from "@/components/ui/badge";

const EDGE_COLOURS: Record<string, string> = {
  HTTP_TRIGGER:       "bg-blue-100 text-blue-800",
  SERVICE_CALL:       "bg-purple-100 text-purple-800",
  SCHEMA_VALIDATION:  "bg-gray-100 text-gray-800",
  DB_READ:            "bg-amber-100 text-amber-800",
  DB_WRITE:           "bg-orange-100 text-orange-800",
  EXTERNAL_API:       "bg-pink-100 text-pink-800",
  CACHE_READ:         "bg-teal-100 text-teal-800",
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

function nodeName(nodes: FlowNode[], id: number | null): string {
  if (id == null) return "external";
  return nodes.find((n) => n.id === id)?.name ?? `#${id}`;
}

/**
 * P3.8: Two-column table showing outbound (Calls) and inbound (Called By)
 * edges for the focused component.
 */
export function EdgeListPanel({ edges, nodes, focusedComponentId, onNodeClick }: EdgeListPanelProps) {
  const outbound = edges.filter((e) => e.source_component_id === focusedComponentId);
  const inbound  = edges.filter((e) => e.target_component_id === focusedComponentId);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Calls */}
      <div>
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Calls ({outbound.length})
        </h4>
        {outbound.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No outbound calls detected</p>
        ) : (
          <ul className="space-y-1">
            {outbound.map((e) => (
              <li
                key={e.id}
                className="flex items-center gap-2 text-sm p-1.5 rounded hover:bg-gray-50 cursor-pointer"
                onClick={() => e.target_component_id && onNodeClick?.(e.target_component_id)}
              >
                <Badge className={`text-[10px] px-1.5 py-0 font-mono shrink-0 ${EDGE_COLOURS[e.edge_type] ?? "bg-gray-100 text-gray-700"}`}>
                  {e.edge_type}
                </Badge>
                <span className="truncate text-gray-700">{e.data_summary}</span>
                <span className="text-gray-400 shrink-0 text-xs">
                  → {nodeName(nodes, e.target_component_id)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Called By */}
      <div>
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Called By ({inbound.length})
        </h4>
        {inbound.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No inbound callers detected</p>
        ) : (
          <ul className="space-y-1">
            {inbound.map((e) => (
              <li
                key={e.id}
                className="flex items-center gap-2 text-sm p-1.5 rounded hover:bg-gray-50 cursor-pointer"
                onClick={() => onNodeClick?.(e.source_component_id)}
              >
                <Badge className={`text-[10px] px-1.5 py-0 font-mono shrink-0 ${EDGE_COLOURS[e.edge_type] ?? "bg-gray-100 text-gray-700"}`}>
                  {e.edge_type}
                </Badge>
                <span className="text-gray-400 shrink-0 text-xs">
                  {nodeName(nodes, e.source_component_id)} →
                </span>
                <span className="truncate text-gray-700">{e.data_summary}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
