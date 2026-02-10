"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

/**
 * CrossGraphView — Bipartite graph visualization for document ↔ code concept mappings.
 *
 * Layout: Document concepts on the left, code concepts on the right,
 * with mapping lines connecting matched pairs across the gap.
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
  const [dimensions, setDimensions] = useState({ width: 900, height: 600 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [panning, setPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

  // Measure container
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setDimensions({ width, height });
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Layout: position nodes in two columns
  const nodeHeight = 38;
  const nodeWidth = 160;
  const gapX = 300; // space between columns
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

  // Pan handlers
  const handleCanvasMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget || (e.target as SVGElement).tagName === "rect") {
        setPanning(true);
        panStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
        onSelectMapping(null);
      }
    },
    [pan, onSelectMapping]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (panning) {
        setPan({
          x: panStart.current.panX + (e.clientX - panStart.current.x),
          y: panStart.current.panY + (e.clientY - panStart.current.y),
        });
      }
    },
    [panning]
  );

  const handleMouseUp = useCallback(() => setPanning(false), []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    setZoom((z) => Math.max(0.3, Math.min(3, z * (e.deltaY > 0 ? 0.9 : 1.1))));
  }, []);

  const totalHeight = Math.max(
    marginTop + documentNodes.length * spacing + 40,
    marginTop + codeNodes.length * spacing + 40,
    dimensions.height
  );

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
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      {/* Zoom controls */}
      <div className="absolute right-3 top-3 z-10 flex flex-col gap-1">
        <button onClick={() => setZoom((z) => Math.min(3, z * 1.2))} className="rounded-md border bg-white p-1.5 shadow-sm hover:bg-gray-50" title="Zoom in">
          <ZoomIn className="h-4 w-4 text-gray-600" />
        </button>
        <button onClick={() => setZoom((z) => Math.max(0.3, z * 0.8))} className="rounded-md border bg-white p-1.5 shadow-sm hover:bg-gray-50" title="Zoom out">
          <ZoomOut className="h-4 w-4 text-gray-600" />
        </button>
        <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} className="rounded-md border bg-white p-1.5 shadow-sm hover:bg-gray-50" title="Fit to view">
          <Maximize2 className="h-4 w-4 text-gray-600" />
        </button>
      </div>

      {/* Zoom level */}
      <div className="absolute bottom-3 right-3 z-10 rounded bg-white/80 px-2 py-0.5 text-xs text-gray-500">
        {Math.round(zoom * 100)}%
      </div>

      <svg
        width={dimensions.width}
        height={dimensions.height}
        className="cursor-grab active:cursor-grabbing"
        onMouseDown={handleCanvasMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          <rect x={0} y={0} width={dimensions.width / zoom} height={totalHeight / zoom} fill="transparent" />

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
              <g key={`doc-${n.id}`} transform={`translate(${pos.x}, ${pos.y})`} className="cursor-pointer" onClick={() => onSelectNode?.(n.id, "document")}>
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
              <g key={`code-${n.id}`} transform={`translate(${pos.x}, ${pos.y})`} className="cursor-pointer" onClick={() => onSelectNode?.(n.id, "code")}>
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
        </g>
      </svg>
    </div>
  );
}
