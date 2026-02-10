"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

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
  fx?: number | null; // fixed position (for dragging)
  fy?: number | null;
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
  const restLength = 150;
  const damping = 0.85;
  const centerPull = 0.01;

  for (let iter = 0; iter < iterations; iter++) {
    // Repulsion between all pairs
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

    // Attraction along edges
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

    // Centering force
    nodes.forEach((n) => {
      n.vx += (centerX - n.x) * centerPull;
      n.vy += (centerY - n.y) * centerPull;
    });

    // Update positions with damping
    nodes.forEach((n) => {
      if (n.fx != null) {
        n.x = n.fx;
        n.y = n.fy!;
        n.vx = 0;
        n.vy = 0;
      } else {
        n.vx *= damping;
        n.vy *= damping;
        n.x += n.vx;
        n.y += n.vy;
        // Keep in bounds
        n.x = Math.max(60, Math.min(width - 60, n.x));
        n.y = Math.max(40, Math.min(height - 40, n.y));
      }
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

export function OntologyGraph({
  nodes,
  edges,
  selectedId,
  onSelectNode,
  onSelectEdge,
}: OntologyGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState<number | null>(null);
  const [panning, setPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

  // Measure container
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) {
        setDimensions({ width, height });
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Run simulation when nodes/edges/dimensions change
  useEffect(() => {
    if (nodes.length === 0) {
      setSimNodes([]);
      return;
    }
    const { width, height } = dimensions;
    const initial: SimNode[] = nodes.map((n, i) => {
      const angle = (2 * Math.PI * i) / nodes.length;
      const radius = Math.min(width, height) * 0.3;
      return {
        ...n,
        x: width / 2 + Math.cos(angle) * radius + (Math.random() - 0.5) * 40,
        y: height / 2 + Math.sin(angle) * radius + (Math.random() - 0.5) * 40,
        vx: 0,
        vy: 0,
      };
    });
    const result = runForceSimulation(initial, edges, width, height, 150);
    setSimNodes([...result]);
  }, [nodes, edges, dimensions]);

  // Drag handlers
  const handleNodeMouseDown = useCallback(
    (e: React.MouseEvent, nodeId: number) => {
      e.stopPropagation();
      setDragging(nodeId);
      onSelectNode(nodeId);
    },
    [onSelectNode]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (dragging !== null) {
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect) return;
        const x = (e.clientX - rect.left - pan.x) / zoom;
        const y = (e.clientY - rect.top - pan.y) / zoom;
        setSimNodes((prev) =>
          prev.map((n) => (n.id === dragging ? { ...n, x, y, fx: x, fy: y } : n))
        );
      } else if (panning) {
        const dx = e.clientX - panStart.current.x;
        const dy = e.clientY - panStart.current.y;
        setPan({
          x: panStart.current.panX + dx,
          y: panStart.current.panY + dy,
        });
      }
    },
    [dragging, panning, pan, zoom]
  );

  const handleMouseUp = useCallback(() => {
    if (dragging !== null) {
      setSimNodes((prev) =>
        prev.map((n) => (n.id === dragging ? { ...n, fx: null, fy: null } : n))
      );
    }
    setDragging(null);
    setPanning(false);
  }, [dragging]);

  const handleCanvasMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget || (e.target as SVGElement).tagName === "rect") {
        setPanning(true);
        panStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
        onSelectNode(null);
      }
    },
    [pan, onSelectNode]
  );

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom((z) => Math.max(0.3, Math.min(3, z * delta)));
  }, []);

  const fitToView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const nodeMap = new Map(simNodes.map((n) => [n.id, n]));

  // Edge label positions
  function edgeLabelPos(e: GraphEdge) {
    const src = nodeMap.get(e.source_concept_id);
    const tgt = nodeMap.get(e.target_concept_id);
    if (!src || !tgt) return null;
    return { x: (src.x + tgt.x) / 2, y: (src.y + tgt.y) / 2 };
  }

  // Compute edge path with offset from node center (so arrow doesn't overlap node)
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
      <div className="flex h-full flex-col items-center justify-center text-gray-400">
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
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      {/* Zoom controls */}
      <div className="absolute right-3 top-3 z-10 flex flex-col gap-1">
        <button
          onClick={() => setZoom((z) => Math.min(3, z * 1.2))}
          className="rounded-md border bg-white p-1.5 shadow-sm hover:bg-gray-50"
          title="Zoom in"
        >
          <ZoomIn className="h-4 w-4 text-gray-600" />
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(0.3, z * 0.8))}
          className="rounded-md border bg-white p-1.5 shadow-sm hover:bg-gray-50"
          title="Zoom out"
        >
          <ZoomOut className="h-4 w-4 text-gray-600" />
        </button>
        <button
          onClick={fitToView}
          className="rounded-md border bg-white p-1.5 shadow-sm hover:bg-gray-50"
          title="Fit to view"
        >
          <Maximize2 className="h-4 w-4 text-gray-600" />
        </button>
      </div>

      {/* Zoom level indicator */}
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
        <defs>
          <ArrowMarker id="arrow-default" color="#9ca3af" />
          <ArrowMarker id="arrow-selected" color="#3b82f6" />
        </defs>

        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Background */}
          <rect
            x={0}
            y={0}
            width={dimensions.width / zoom}
            height={dimensions.height / zoom}
            fill="transparent"
          />

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
                  strokeWidth={isConnected ? 2 : 1.5}
                  fill="none"
                  markerEnd={`url(#arrow-${isConnected ? "selected" : "default"})`}
                  className="cursor-pointer transition-colors"
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
            const nodeWidth = Math.max(80, textWidth);
            const nodeHeight = 36;
            return (
              <g
                key={`node-${n.id}`}
                transform={`translate(${n.x}, ${n.y})`}
                onMouseDown={(e) => handleNodeMouseDown(e, n.id)}
                className="cursor-pointer"
              >
                {/* Selection ring */}
                {isSelected && (
                  <rect
                    x={-nodeWidth / 2 - 3}
                    y={-nodeHeight / 2 - 3}
                    width={nodeWidth + 6}
                    height={nodeHeight + 6}
                    rx={12}
                    fill="none"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    className="animate-pulse"
                  />
                )}
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
                {/* Source type indicator (top-left) */}
                {n.source_type && n.source_type !== "document" && (
                  <g transform={`translate(${-nodeWidth / 2 + 8}, ${-nodeHeight / 2 + 10})`}>
                    <rect x={-6} y={-6} width={12} height={12} rx={2}
                      fill={n.source_type === "code" ? "#dcfce7" : n.source_type === "both" ? "#e0e7ff" : "transparent"}
                      stroke={n.source_type === "code" ? "#22c55e" : "#6366f1"}
                      strokeWidth={1}
                    />
                    <text textAnchor="middle" dy="3" fontSize={7} fontWeight={700}
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
                  {n.name.length > 16 ? n.name.substring(0, 14) + "..." : n.name}
                </text>
                {/* Type label below */}
                <text
                  textAnchor="middle"
                  dy="13"
                  fontSize={9}
                  fill={color.text}
                  opacity={0.7}
                  className="pointer-events-none select-none"
                >
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
