"use client";

import { useEffect, useRef, useState, useMemo } from "react";

// --- Types ---

interface GraphNode {
  id: number;
  name: string;
  concept_type: string;
  source_type?: string;
  confidence_score: number;
}

interface GraphEdge {
  id: number;
  source_concept_id: number;
  target_concept_id: number;
  relationship_type: string;
  confidence_score: number;
}

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface OntologyGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: number | null;
  onSelectNode: (id: number | null) => void;
  onSelectEdge?: (edge: GraphEdge | null) => void;
}

// --- Color Map ---

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

function getTypeColor(type: string) {
  return TYPE_COLORS[type] || TYPE_COLORS.Default;
}

// --- Force Simulation ---

function runForceSimulation(
  nodes: SimNode[],
  edges: GraphEdge[],
  width: number,
  height: number,
  iterations: number = 100
): SimNode[] {
  const centerX = width / 2;
  const centerY = height / 2;
  const repulsion = 8000;
  const attraction = 0.005;
  const restLength = 180;
  const damping = 0.85;
  const centerPull = 0.01;

  for (let iter = 0; iter < iterations; iter++) {
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const force = repulsion / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        nodes[i].vx += fx;
        nodes[i].vy += fy;
        nodes[j].vx -= fx;
        nodes[j].vy -= fy;
      }
    }

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    edges.forEach((e) => {
      const src = nodeMap.get(e.source_concept_id);
      const tgt = nodeMap.get(e.target_concept_id);
      if (!src || !tgt) return;
      const dx = tgt.x - src.x;
      const dy = tgt.y - src.y;
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const force = attraction * (dist - restLength);
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      src.vx += fx;
      src.vy += fy;
      tgt.vx -= fx;
      tgt.vy -= fy;
    });

    nodes.forEach((n) => {
      n.vx += (centerX - n.x) * centerPull;
      n.vy += (centerY - n.y) * centerPull;
    });

    nodes.forEach((n) => {
      n.vx *= damping;
      n.vy *= damping;
      n.x += n.vx;
      n.y += n.vy;
      n.x = Math.max(80, Math.min(width - 80, n.x));
      n.y = Math.max(50, Math.min(height - 50, n.y));
    });
  }

  return nodes;
}

// --- Arrow Marker ---

function ArrowMarker({ id, color }: { id: string; color: string }) {
  return (
    <marker
      id={id}
      viewBox="0 0 10 6"
      refX="10"
      refY="3"
      markerWidth="8"
      markerHeight="6"
      orient="auto-start-reverse"
    >
      <path d="M 0 0 L 10 3 L 0 6 z" fill={color} />
    </marker>
  );
}

// --- Main Component ---
// Now uses a scrollable overflow container instead of zoom/pan

export function OntologyGraph({
  nodes,
  edges,
  selectedId,
  onSelectNode,
  onSelectEdge,
}: OntologyGraphProps) {
  const [simNodes, setSimNodes] = useState<SimNode[]>([]);

  // Calculate canvas size based on node count — larger graph = more canvas area
  const canvasWidth = Math.max(900, Math.min(2400, nodes.length * 120));
  const canvasHeight = Math.max(600, Math.min(1600, nodes.length * 80));

  // Run simulation when nodes/edges change
  useEffect(() => {
    if (nodes.length === 0) {
      setSimNodes([]);
      return;
    }
    const initial: SimNode[] = nodes.map((n, i) => {
      const angle = (2 * Math.PI * i) / nodes.length;
      const radius = Math.min(canvasWidth, canvasHeight) * 0.3;
      return {
        ...n,
        x: canvasWidth / 2 + Math.cos(angle) * radius + (Math.random() - 0.5) * 40,
        y: canvasHeight / 2 + Math.sin(angle) * radius + (Math.random() - 0.5) * 40,
        vx: 0,
        vy: 0,
      };
    });
    const result = runForceSimulation(initial, edges, canvasWidth, canvasHeight, 150);
    setSimNodes([...result]);
  }, [nodes, edges, canvasWidth, canvasHeight]);

  const nodeMap = new Map(simNodes.map((n) => [n.id, n]));

  function edgeLabelPos(e: GraphEdge) {
    const src = nodeMap.get(e.source_concept_id);
    const tgt = nodeMap.get(e.target_concept_id);
    if (!src || !tgt) return null;
    return { x: (src.x + tgt.x) / 2, y: (src.y + tgt.y) / 2 };
  }

  function edgePath(e: GraphEdge) {
    const src = nodeMap.get(e.source_concept_id);
    const tgt = nodeMap.get(e.target_concept_id);
    if (!src || !tgt) return "";
    const dx = tgt.x - src.x;
    const dy = tgt.y - src.y;
    const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
    const nodeRadius = 30;
    const sx = src.x + (dx / dist) * nodeRadius;
    const sy = src.y + (dy / dist) * nodeRadius;
    const tx = tgt.x - (dx / dist) * nodeRadius;
    const ty = tgt.y - (dy / dist) * nodeRadius;
    return `M ${sx} ${sy} L ${tx} ${ty}`;
  }

  if (nodes.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center text-gray-400">
        <svg className="mb-3 h-16 w-16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
          <circle cx="12" cy="5" r="3" />
          <circle cx="5" cy="19" r="3" />
          <circle cx="19" cy="19" r="3" />
          <path d="M12 8v3m-5.5 5.5L9 14m5.5 2.5L15 14" />
        </svg>
        <p className="text-sm font-medium">No concepts yet</p>
        <p className="mt-1 text-xs">Upload and analyze documents to build your knowledge graph</p>
      </div>
    );
  }

  return (
    <div className="overflow-auto rounded-lg border bg-white" style={{ maxHeight: "70vh" }}>
      <svg width={canvasWidth} height={canvasHeight}>
        <defs>
          <ArrowMarker id="arrow-default" color="#9ca3af" />
          <ArrowMarker id="arrow-selected" color="#3b82f6" />
        </defs>

        {/* Background click to deselect */}
        <rect
          x={0} y={0}
          width={canvasWidth} height={canvasHeight}
          fill="#fafbfc"
          onClick={() => onSelectNode(null)}
        />

        {/* Grid pattern for visual reference */}
        <g opacity={0.3}>
          {Array.from({ length: Math.ceil(canvasWidth / 100) }).map((_, i) => (
            <line key={`vg-${i}`} x1={i * 100} y1={0} x2={i * 100} y2={canvasHeight} stroke="#e5e7eb" strokeWidth={0.5} />
          ))}
          {Array.from({ length: Math.ceil(canvasHeight / 100) }).map((_, i) => (
            <line key={`hg-${i}`} x1={0} y1={i * 100} x2={canvasWidth} y2={i * 100} stroke="#e5e7eb" strokeWidth={0.5} />
          ))}
        </g>

        {/* Edges */}
        {edges.map((e) => {
          const isConnected =
            selectedId === e.source_concept_id || selectedId === e.target_concept_id;
          const labelPos = edgeLabelPos(e);
          return (
            <g key={`edge-${e.id}`}>
              <path
                d={edgePath(e)}
                stroke={isConnected ? "#3b82f6" : "#d1d5db"}
                strokeWidth={isConnected ? 2.5 : 1.5}
                fill="none"
                markerEnd={`url(#arrow-${isConnected ? "selected" : "default"})`}
                className="cursor-pointer"
                onClick={(ev) => {
                  ev.stopPropagation();
                  onSelectEdge?.(e);
                }}
              />
              {labelPos && (
                <g transform={`translate(${labelPos.x}, ${labelPos.y})`}>
                  <rect
                    x={-(e.relationship_type.length * 3.2 + 8)}
                    y={-9}
                    width={e.relationship_type.length * 6.4 + 16}
                    height={18}
                    rx={4}
                    fill={isConnected ? "#eff6ff" : "#f9fafb"}
                    stroke={isConnected ? "#93c5fd" : "#e5e7eb"}
                    strokeWidth={0.5}
                  />
                  <text
                    textAnchor="middle"
                    dy="4"
                    className="pointer-events-none select-none"
                    fontSize={10}
                    fontWeight={500}
                    fill={isConnected ? "#2563eb" : "#6b7280"}
                  >
                    {e.relationship_type}
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {simNodes.map((n) => {
          const color = getTypeColor(n.concept_type);
          const isSelected = n.id === selectedId;
          const textWidth = n.name.length * 7 + 24;
          const nodeWidth = Math.max(90, textWidth);
          const nodeHeight = 40;
          return (
            <g
              key={`node-${n.id}`}
              transform={`translate(${n.x}, ${n.y})`}
              onClick={(e) => { e.stopPropagation(); onSelectNode(n.id); }}
              className="cursor-pointer"
            >
              {/* Selection ring */}
              {isSelected && (
                <rect
                  x={-nodeWidth / 2 - 4}
                  y={-nodeHeight / 2 - 4}
                  width={nodeWidth + 8}
                  height={nodeHeight + 8}
                  rx={14}
                  fill="none"
                  stroke="#3b82f6"
                  strokeWidth={2.5}
                  opacity={0.6}
                />
              )}
              {/* Shadow */}
              <rect
                x={-nodeWidth / 2 + 2}
                y={-nodeHeight / 2 + 2}
                width={nodeWidth}
                height={nodeHeight}
                rx={10}
                fill="#00000008"
              />
              {/* Node body */}
              <rect
                x={-nodeWidth / 2}
                y={-nodeHeight / 2}
                width={nodeWidth}
                height={nodeHeight}
                rx={10}
                fill={color.bg}
                stroke={isSelected ? "#3b82f6" : color.border}
                strokeWidth={isSelected ? 2 : 1.5}
              />
              {/* Source type badge */}
              {n.source_type && n.source_type !== "document" && (
                <g transform={`translate(${-nodeWidth / 2 + 10}, ${-nodeHeight / 2 + 11})`}>
                  <rect x={-7} y={-7} width={14} height={14} rx={3}
                    fill={n.source_type === "code" ? "#dcfce7" : "#e0e7ff"}
                    stroke={n.source_type === "code" ? "#22c55e" : "#6366f1"}
                    strokeWidth={1}
                  />
                  <text textAnchor="middle" dy="4" fontSize={8} fontWeight={700}
                    fill={n.source_type === "code" ? "#166534" : "#3730a3"}
                    className="pointer-events-none select-none"
                  >
                    {n.source_type === "code" ? "C" : "B"}
                  </text>
                </g>
              )}
              {/* Confidence dot */}
              <circle
                cx={nodeWidth / 2 - 10}
                cy={-nodeHeight / 2 + 10}
                r={4}
                fill={
                  n.confidence_score >= 0.8
                    ? "#22c55e"
                    : n.confidence_score >= 0.5
                      ? "#f59e0b"
                      : "#ef4444"
                }
              />
              {/* Name */}
              <text
                textAnchor="middle"
                dy="1"
                fontSize={12}
                fontWeight={600}
                fill={color.text}
                className="pointer-events-none select-none"
              >
                {n.name.length > 18 ? n.name.substring(0, 16) + "..." : n.name}
              </text>
              {/* Type label */}
              <text
                textAnchor="middle"
                dy="14"
                fontSize={9}
                fill={color.text}
                opacity={0.6}
                className="pointer-events-none select-none"
              >
                {n.concept_type}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
