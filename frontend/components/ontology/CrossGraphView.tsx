"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * CrossGraphView — Bipartite graph visualization for document ↔ code concept mappings.
 *
 * Layout: Document concepts on the left, code concepts on the right,
 * with mapping lines connecting matched pairs across the gap.
 * Scrollable container — no zoom/pan needed.
 */

// --- Types ---

interface ConceptNode {
  id: number;
  name: string;
  concept_type: string;
  source_type: string;
  confidence_score: number;
}

interface MappingEdge {
  id: number;
  document_concept_id: number;
  code_concept_id: number;
  document_concept_name: string;
  code_concept_name: string;
  mapping_method: string;
  confidence_score: number;
  status: string;
  relationship_type: string;
}

interface CrossGraphViewProps {
  documentNodes: ConceptNode[];
  codeNodes: ConceptNode[];
  mappings: MappingEdge[];
  selectedMappingId: number | null;
  onSelectMapping: (id: number | null) => void;
  onSelectNode?: (id: number, side: "document" | "code") => void;
}

// --- Color maps ---

const TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  Entity:    { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
  Process:   { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
  Attribute: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },
  Value:     { bg: "#f3e8ff", border: "#a855f7", text: "#6b21a8" },
  Event:     { bg: "#fee2e2", border: "#ef4444", text: "#991b1b" },
  Role:      { bg: "#ccfbf1", border: "#14b8a6", text: "#115e59" },
  Service:   { bg: "#e0e7ff", border: "#6366f1", text: "#3730a3" },
  Default:   { bg: "#f3f4f6", border: "#9ca3af", text: "#374151" },
};

const METHOD_COLORS: Record<string, string> = {
  exact: "#22c55e",
  fuzzy: "#f59e0b",
  ai_validated: "#8b5cf6",
};

const STATUS_COLORS: Record<string, string> = {
  confirmed: "#22c55e",
  candidate: "#f59e0b",
  rejected: "#ef4444",
};

function getTypeColor(type: string) {
  return TYPE_COLORS[type] || TYPE_COLORS.Default;
}

// --- Main Component ---

export function CrossGraphView({
  documentNodes,
  codeNodes,
  mappings,
  selectedMappingId,
  onSelectMapping,
  onSelectNode,
}: CrossGraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(900);

  // Measure container width for responsive layout
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const { width } = entries[0].contentRect;
      if (width > 0) setContainerWidth(width);
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Layout constants
  const nodeHeight = 38;
  const nodeWidth = 160;
  const gapX = Math.min(Math.max(200, containerWidth - 2 * nodeWidth - 120), 400); // cap gap to prevent excessive spread
  const marginTop = 60;
  const marginLeft = 40;
  const spacing = 52;

  const leftX = marginLeft;
  const rightX = marginLeft + nodeWidth + gapX;

  const docPositions = new Map<number, { x: number; y: number }>();
  documentNodes.forEach((n, i) => {
    docPositions.set(n.id, { x: leftX + nodeWidth / 2, y: marginTop + i * spacing + nodeHeight / 2 });
  });

  const codePositions = new Map<number, { x: number; y: number }>();
  codeNodes.forEach((n, i) => {
    codePositions.set(n.id, { x: rightX + nodeWidth / 2, y: marginTop + i * spacing + nodeHeight / 2 });
  });

  // SVG auto-sizes to fit all content
  const totalHeight = Math.max(
    marginTop + documentNodes.length * spacing + 40,
    marginTop + codeNodes.length * spacing + 40,
    300
  );
  const totalWidth = rightX + nodeWidth + marginLeft;

  if (documentNodes.length === 0 && codeNodes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-gray-400">
        <svg className="mb-3 h-16 w-16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
          <circle cx="6" cy="8" r="3" />
          <circle cx="18" cy="8" r="3" />
          <circle cx="6" cy="16" r="3" />
          <circle cx="18" cy="16" r="3" />
          <path d="M9 8h6M9 16h6" />
        </svg>
        <p className="text-sm font-medium">No cross-graph data yet</p>
        <p className="mt-1 text-xs">Run the mapping pipeline to discover connections</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full overflow-auto rounded-lg border bg-white"
    >
      {/* Node count indicator */}
      <div className="sticky left-0 top-0 z-10 flex items-center gap-4 border-b bg-white/90 px-4 py-2 backdrop-blur-sm">
        <span className="text-xs font-medium text-blue-700">
          Doc Concepts: {documentNodes.length}
        </span>
        <span className="text-xs font-medium text-green-700">
          Code Concepts: {codeNodes.length}
        </span>
        <span className="text-xs font-medium text-gray-500">
          Mappings: {mappings.length}
        </span>
      </div>

      <svg
        width={Math.max(totalWidth, containerWidth)}
        height={totalHeight}
        className="cursor-default"
        onClick={() => onSelectMapping(null)}
      >
        {/* Subtle grid background */}
        <defs>
          <pattern id="crossgraph-grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#f1f5f9" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#crossgraph-grid)" />

        {/* Column headers */}
        <text x={leftX + nodeWidth / 2} y={30} textAnchor="middle" fontSize={13} fontWeight={700} fill="#1e40af">
          Document Concepts ({documentNodes.length})
        </text>
        <text x={rightX + nodeWidth / 2} y={30} textAnchor="middle" fontSize={13} fontWeight={700} fill="#166534">
          Code Concepts ({codeNodes.length})
        </text>

        {/* Mapping edges */}
        {mappings.map((m) => {
          const src = docPositions.get(m.document_concept_id);
          const tgt = codePositions.get(m.code_concept_id);
          if (!src || !tgt) return null;
          const isSelected = m.id === selectedMappingId;
          const color = STATUS_COLORS[m.status] || "#9ca3af";
          const midX = (src.x + nodeWidth / 2 + tgt.x - nodeWidth / 2) / 2;
          const midY = (src.y + tgt.y) / 2;

          return (
            <g key={`mapping-${m.id}`}>
              <path
                d={`M ${src.x + nodeWidth / 2} ${src.y} C ${midX} ${src.y}, ${midX} ${tgt.y}, ${tgt.x - nodeWidth / 2} ${tgt.y}`}
                stroke={isSelected ? "#3b82f6" : color}
                strokeWidth={isSelected ? 3 : 1.5}
                strokeDasharray={m.status === "candidate" ? "6,3" : "none"}
                fill="none"
                className="cursor-pointer transition-colors"
                onClick={(e) => { e.stopPropagation(); onSelectMapping(m.id); }}
              />
              {/* Method badge at midpoint */}
              <g transform={`translate(${midX}, ${midY})`}>
                <rect x={-28} y={-10} width={56} height={20} rx={10} fill={isSelected ? "#eff6ff" : "white"} stroke={isSelected ? "#3b82f6" : color} strokeWidth={1} />
                <text textAnchor="middle" dy="4" fontSize={9} fontWeight={600} fill={METHOD_COLORS[m.mapping_method] || "#6b7280"}>
                  {m.mapping_method}
                </text>
              </g>
            </g>
          );
        })}

        {/* Document nodes (left) */}
        {documentNodes.map((n) => {
          const pos = docPositions.get(n.id);
          if (!pos) return null;
          const color = getTypeColor(n.concept_type);
          const hasMapping = mappings.some((m) => m.document_concept_id === n.id);
          return (
            <g key={`doc-${n.id}`} transform={`translate(${pos.x}, ${pos.y})`} className="cursor-pointer" onClick={(e) => { e.stopPropagation(); onSelectNode?.(n.id, "document"); }}>
              <rect x={-nodeWidth / 2} y={-nodeHeight / 2} width={nodeWidth} height={nodeHeight} rx={8} fill={color.bg} stroke={hasMapping ? color.border : "#d1d5db"} strokeWidth={hasMapping ? 2 : 1} />
              {!hasMapping && <rect x={-nodeWidth / 2} y={-nodeHeight / 2} width={nodeWidth} height={nodeHeight} rx={8} fill="none" stroke="#ef4444" strokeWidth={1} strokeDasharray="4,2" opacity={0.5} />}
              <text textAnchor="middle" dy="1" fontSize={11} fontWeight={600} fill={color.text} className="pointer-events-none select-none">
                {n.name.length > 18 ? n.name.substring(0, 16) + "..." : n.name}
              </text>
              <text textAnchor="middle" dy="13" fontSize={8} fill={color.text} opacity={0.6} className="pointer-events-none select-none">
                {n.concept_type}
              </text>
            </g>
          );
        })}

        {/* Code nodes (right) */}
        {codeNodes.map((n) => {
          const pos = codePositions.get(n.id);
          if (!pos) return null;
          const color = getTypeColor(n.concept_type);
          const hasMapping = mappings.some((m) => m.code_concept_id === n.id);
          return (
            <g key={`code-${n.id}`} transform={`translate(${pos.x}, ${pos.y})`} className="cursor-pointer" onClick={(e) => { e.stopPropagation(); onSelectNode?.(n.id, "code"); }}>
              <rect x={-nodeWidth / 2} y={-nodeHeight / 2} width={nodeWidth} height={nodeHeight} rx={8} fill={color.bg} stroke={hasMapping ? color.border : "#d1d5db"} strokeWidth={hasMapping ? 2 : 1} />
              {!hasMapping && <rect x={-nodeWidth / 2} y={-nodeHeight / 2} width={nodeWidth} height={nodeHeight} rx={8} fill="none" stroke="#f59e0b" strokeWidth={1} strokeDasharray="4,2" opacity={0.5} />}
              <text textAnchor="middle" dy="1" fontSize={11} fontWeight={600} fill={color.text} className="pointer-events-none select-none">
                {n.name.length > 18 ? n.name.substring(0, 16) + "..." : n.name}
              </text>
              <text textAnchor="middle" dy="13" fontSize={8} fill={color.text} opacity={0.6} className="pointer-events-none select-none">
                {n.concept_type}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
