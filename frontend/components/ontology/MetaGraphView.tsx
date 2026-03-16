"use client";

import { useCallback, useMemo, useRef, useState } from "react";

// --- Types ---

interface ProjectNode {
  id: number;
  name: string;
  initiative_id: number | null;
  repo_id: number | null;
  concept_count: number;
  relationship_count: number;
  file_count: number;
  top_concepts: string[];
  type_distribution: Record<string, number>;
  status: string;
}

interface CrossEdge {
  source_id: number;
  target_id: number;
  relationship_count: number;
  relationship_types: string[];
  avg_confidence?: number;
  confirmed_count?: number;
  candidate_count?: number;
}

interface Project {
  id: number;
  name: string;
}

interface MetaGraphData {
  nodes: ProjectNode[];
  cross_edges: CrossEdge[];
  total_concepts: number;
  total_relationships: number;
  total_cross_edges: number;
  projects: Project[];
}

// --- Color Palette for Projects ---

const PROJECT_COLORS = [
  { bg: "#dbeafe", border: "#3b82f6", text: "#1d4ed8", gradient: "#bfdbfe" },
  { bg: "#dcfce7", border: "#22c55e", text: "#15803d", gradient: "#bbf7d0" },
  { bg: "#fef3c7", border: "#f59e0b", text: "#b45309", gradient: "#fde68a" },
  { bg: "#fce7f3", border: "#ec4899", text: "#be185d", gradient: "#fbcfe8" },
  { bg: "#e0e7ff", border: "#6366f1", text: "#4338ca", gradient: "#c7d2fe" },
  { bg: "#f3e8ff", border: "#a855f7", text: "#7c3aed", gradient: "#e9d5ff" },
  { bg: "#ccfbf1", border: "#14b8a6", text: "#0f766e", gradient: "#99f6e4" },
  { bg: "#ffedd5", border: "#f97316", text: "#c2410c", gradient: "#fed7aa" },
];

const UNSCOPED_COLOR = { bg: "#f3f4f6", border: "#9ca3af", text: "#4b5563", gradient: "#e5e7eb" };

function getProjectColor(index: number) {
  return PROJECT_COLORS[index % PROJECT_COLORS.length];
}

// --- Component ---

export function MetaGraphView({
  data,
  onSelectMapping,
}: {
  data: MetaGraphData;
  onSelectMapping?: (nodeId: number) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  // Pan & zoom
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, w: 1000, h: 600 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0, vbx: 0, vby: 0 });

  // Drag
  const [dragId, setDragId] = useState<number | null>(null);
  const [nodePositions, setNodePositions] = useState<Map<number, { x: number; y: number }>>(new Map());
  const dragStartRef = useRef({ x: 0, y: 0, nodeX: 0, nodeY: 0 });
  const didDragRef = useRef(false); // Track if actual dragging happened

  const W = 1000;
  const H = 600;

  // Layout: position project bubbles in a ring
  const layoutNodes = useMemo(() => {
    const { nodes } = data;
    if (!nodes || nodes.length === 0) return [];

    const cx = W / 2;
    const cy = H / 2;
    const maxConcepts = Math.max(...nodes.map((n) => n.concept_count), 1);

    return nodes.map((n, i) => {
      const sizeFactor = 0.3 + 0.7 * (n.concept_count / maxConcepts);
      const radius = 50 + sizeFactor * 60; // 50-110px
      const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
      const spread = nodes.length === 1 ? 0 : Math.min(W, H) * 0.25;
      const color = n.initiative_id !== null && n.initiative_id >= 0
        ? getProjectColor(i)
        : UNSCOPED_COLOR;

      return {
        ...n,
        x: cx + Math.cos(angle) * spread,
        y: cy + Math.sin(angle) * spread,
        radius,
        color,
      };
    });
  }, [data]);

  // Get position (with drag override)
  const getPos = useCallback(
    (id: number) => {
      const override = nodePositions.get(id);
      if (override) return override;
      const node = layoutNodes.find((n) => n.id === id);
      return node ? { x: node.x, y: node.y } : { x: W / 2, y: H / 2 };
    },
    [layoutNodes, nodePositions]
  );

  const getNode = useCallback(
    (id: number) => layoutNodes.find((n) => n.id === id),
    [layoutNodes]
  );

  // Mouse handlers
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (dragId !== null) return;
      setIsPanning(true);
      panStart.current = { x: e.clientX, y: e.clientY, vbx: viewBox.x, vby: viewBox.y };
    },
    [dragId, viewBox]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (dragId !== null) {
        const svg = svgRef.current;
        if (!svg) return;
        const rect = svg.getBoundingClientRect();
        const scaleX = viewBox.w / rect.width;
        const scaleY = viewBox.h / rect.height;
        const dx = (e.clientX - dragStartRef.current.x) * scaleX;
        const dy = (e.clientY - dragStartRef.current.y) * scaleY;
        // Mark as real drag if moved more than 5px
        if (Math.abs(dx) + Math.abs(dy) > 5) {
          didDragRef.current = true;
        }
        setNodePositions((prev) => {
          const next = new Map(prev);
          next.set(dragId, {
            x: dragStartRef.current.nodeX + dx,
            y: dragStartRef.current.nodeY + dy,
          });
          return next;
        });
        return;
      }
      if (isPanning) {
        const svg = svgRef.current;
        if (!svg) return;
        const rect = svg.getBoundingClientRect();
        const scaleX = viewBox.w / rect.width;
        const scaleY = viewBox.h / rect.height;
        const dx = (e.clientX - panStart.current.x) * scaleX;
        const dy = (e.clientY - panStart.current.y) * scaleY;
        setViewBox((v) => ({ ...v, x: panStart.current.vbx - dx, y: panStart.current.vby - dy }));
      }
    },
    [dragId, isPanning, viewBox]
  );

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
    setDragId(null);
  }, []);

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const factor = e.deltaY > 0 ? 1.08 : 0.93;
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const mx = ((e.clientX - rect.left) / rect.width) * viewBox.w + viewBox.x;
      const my = ((e.clientY - rect.top) / rect.height) * viewBox.h + viewBox.y;
      setViewBox({
        x: mx - (mx - viewBox.x) * factor,
        y: my - (my - viewBox.y) * factor,
        w: viewBox.w * factor,
        h: viewBox.h * factor,
      });
    },
    [viewBox]
  );

  const handleNodeDragStart = useCallback(
    (id: number, e: React.MouseEvent) => {
      e.stopPropagation();
      setDragId(id);
      didDragRef.current = false; // Reset — haven't dragged yet
      const pos = getPos(id);
      dragStartRef.current = { x: e.clientX, y: e.clientY, nodeX: pos.x, nodeY: pos.y };
    },
    [getPos]
  );

  // Hovered node data
  const hoveredNode = useMemo(
    () => (hoveredId !== null ? layoutNodes.find((n) => n.id === hoveredId) : null),
    [hoveredId, layoutNodes]
  );

  // Max edge weight for scaling
  const maxEdgeWeight = useMemo(() => {
    if (!data.cross_edges || data.cross_edges.length === 0) return 1;
    return Math.max(...data.cross_edges.map((e) => e.relationship_count));
  }, [data.cross_edges]);

  if (!data.nodes || data.nodes.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border bg-white text-sm text-gray-400">
        No projects available. Create a project and analyze repositories to see the organizational brain.
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative h-full w-full select-none">
      <svg
        ref={svgRef}
        viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`}
        className="h-full w-full"
        style={{ cursor: dragId ? "grabbing" : isPanning ? "grabbing" : "grab" }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        <defs>
          <filter id="meta-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feFlood floodColor="#818cf8" floodOpacity="0.35" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <radialGradient id="meta-shine" cx="35%" cy="35%" r="65%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity={0.5} />
            <stop offset="100%" stopColor="#ffffff" stopOpacity={0} />
          </radialGradient>
        </defs>

        {/* Subtle background */}
        <rect
          x={viewBox.x - 200}
          y={viewBox.y - 200}
          width={viewBox.w + 400}
          height={viewBox.h + 400}
          fill="#fafbfc"
        />

        {/* Cross-project edges */}
        {(data.cross_edges || []).map((edge, i) => {
          const srcPos = getPos(edge.source_id);
          const tgtPos = getPos(edge.target_id);
          const srcNode = getNode(edge.source_id);
          const tgtNode = getNode(edge.target_id);
          if (!srcNode || !tgtNode) return null;

          const dx = tgtPos.x - srcPos.x;
          const dy = tgtPos.y - srcPos.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const nx = dx / dist;
          const ny = dy / dist;
          const sx = srcPos.x + nx * srcNode.radius;
          const sy = srcPos.y + ny * srcNode.radius;
          const ex = tgtPos.x - nx * tgtNode.radius;
          const ey = tgtPos.y - ny * tgtNode.radius;
          const curveMag = dist * 0.12;
          const cpx = (sx + ex) / 2 + ny * curveMag;
          const cpy = (sy + ey) / 2 - nx * curveMag;
          const path = `M ${sx} ${sy} Q ${cpx} ${cpy} ${ex} ${ey}`;

          const weight = edge.relationship_count;
          const normalizedWeight = weight / maxEdgeWeight;
          const strokeWidth = 2 + normalizedWeight * 3;
          const isHighlighted = hoveredId === edge.source_id || hoveredId === edge.target_id;

          // Confidence-based coloring
          const avgConf = edge.avg_confidence ?? 0.5;
          const confColor = avgConf >= 0.8 ? "#22c55e" : avgConf >= 0.5 ? "#f59e0b" : "#ef4444";
          const confirmedRatio = edge.confirmed_count && weight > 0
            ? edge.confirmed_count / weight : 0;

          return (
            <g key={`edge-${i}`}>
              <path
                d={path}
                fill="none"
                stroke={isHighlighted ? "#f97316" : confColor}
                strokeWidth={strokeWidth}
                strokeOpacity={isHighlighted ? 0.8 : 0.35 + confirmedRatio * 0.35}
                strokeDasharray={confirmedRatio >= 0.8 ? "none" : "8 4"}
              />
              <g transform={`translate(${cpx}, ${cpy})`}>
                <rect
                  x={-22}
                  y={-10}
                  width={44}
                  height={20}
                  rx={10}
                  fill={isHighlighted ? "#f97316" : "#f8fafc"}
                  stroke={isHighlighted ? "#f97316" : confColor}
                  strokeWidth={1}
                />
                <text
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill={isHighlighted ? "#fff" : "#64748b"}
                  fontSize={10}
                  fontWeight={600}
                >
                  {weight}
                  {avgConf > 0 && (
                    <tspan fontSize={8} opacity={0.7}> {Math.round(avgConf * 100)}%</tspan>
                  )}
                </text>
              </g>
            </g>
          );
        })}

        {/* Project bubbles */}
        {layoutNodes.map((node) => {
          const pos = getPos(node.id);
          const isHovered = hoveredId === node.id;
          const isDragging = dragId === node.id;

          const displayName =
            node.name.length > 20 ? node.name.slice(0, 18) + "..." : node.name;
          const topConcepts = node.top_concepts.slice(0, 3);

          return (
            <g
              key={node.id}
              transform={`translate(${pos.x}, ${pos.y})`}
              style={{ cursor: isDragging ? "grabbing" : "pointer" }}
              filter={isHovered ? "url(#meta-glow)" : undefined}
              onMouseDown={(e) => handleNodeDragStart(node.id, e)}
              onMouseEnter={(e) => {
                setHoveredId(node.id);
                setTooltipPos({ x: e.clientX, y: e.clientY });
              }}
              onMouseLeave={() => setHoveredId(null)}
              onClick={(e) => {
                // Only fire click if we didn't actually drag
                if (!didDragRef.current) {
                  e.stopPropagation();
                  onSelectMapping?.(node.id);
                }
              }}
            >
              {/* Outer ring */}
              <circle
                r={node.radius + 3}
                fill={node.color.border}
                opacity={isHovered ? 0.9 : 0.6}
              />
              {/* Inner fill */}
              <circle r={node.radius} fill={node.color.bg} />
              {/* Shine */}
              <circle r={node.radius} fill="url(#meta-shine)" opacity={0.4} />

              {/* Project name */}
              <text
                textAnchor="middle"
                dominantBaseline="central"
                y={-node.radius * 0.3}
                fill={node.color.text}
                fontSize={14}
                fontWeight={700}
              >
                {displayName}
              </text>

              {/* Stats line */}
              <text
                textAnchor="middle"
                dominantBaseline="central"
                y={-node.radius * 0.05}
                fill={node.color.text}
                fontSize={10}
                opacity={0.75}
              >
                {node.concept_count} concepts · {node.relationship_count} rels
              </text>

              {/* File count */}
              <text
                textAnchor="middle"
                dominantBaseline="central"
                y={node.radius * 0.15}
                fill={node.color.text}
                fontSize={9}
                opacity={0.6}
              >
                {node.file_count} files
              </text>

              {/* Top concepts */}
              {topConcepts.map((concept, ci) => {
                const truncated = concept.length > 18 ? concept.slice(0, 16) + ".." : concept;
                return (
                  <text
                    key={ci}
                    textAnchor="middle"
                    dominantBaseline="central"
                    y={node.radius * 0.35 + ci * 11}
                    fill={node.color.text}
                    fontSize={8}
                    opacity={0.45}
                  >
                    {truncated}
                  </text>
                );
              })}

              {/* Click hint */}
              <text
                textAnchor="middle"
                dominantBaseline="central"
                y={node.radius * 0.8}
                fill={node.color.border}
                fontSize={8}
                opacity={isHovered ? 0.8 : 0}
              >
                Click to explore →
              </text>
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {hoveredNode && (
        <div
          className="pointer-events-none absolute z-50 w-64 rounded-lg border border-gray-200 bg-white p-3 shadow-lg"
          style={{
            left: Math.min(
              tooltipPos.x - (containerRef.current?.getBoundingClientRect().left ?? 0) + 16,
              (containerRef.current?.clientWidth ?? 800) - 280
            ),
            top: Math.min(
              tooltipPos.y - (containerRef.current?.getBoundingClientRect().top ?? 0) - 10,
              (containerRef.current?.clientHeight ?? 600) - 180
            ),
          }}
        >
          <p className="text-sm font-semibold text-gray-900">{hoveredNode.name}</p>
          <div className="mt-1.5 space-y-1 text-xs text-gray-500">
            <p>
              <span className="font-medium text-gray-700">{hoveredNode.concept_count}</span> concepts ·{" "}
              <span className="font-medium text-gray-700">{hoveredNode.relationship_count}</span> relationships ·{" "}
              <span className="font-medium text-gray-700">{hoveredNode.file_count}</span> files
            </p>
            {hoveredNode.top_concepts.length > 0 && (
              <div>
                <p className="mt-1 font-medium text-gray-600">Top concepts:</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {hoveredNode.top_concepts.slice(0, 6).map((c, i) => (
                    <span key={i} className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {Object.keys(hoveredNode.type_distribution ?? {}).length > 0 && (
              <div className="mt-1">
                <p className="font-medium text-gray-600">Types:</p>
                <div className="mt-0.5 flex flex-wrap gap-1">
                  {Object.entries(hoveredNode.type_distribution ?? {})
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 5)
                    .map(([type, count]) => (
                      <span key={type} className="rounded bg-purple-50 px-1.5 py-0.5 text-[10px] text-purple-700">
                        {type}: {count}
                      </span>
                    ))}
                </div>
              </div>
            )}
          </div>
          <p className="mt-2 text-[10px] text-gray-400">Click to drill into system architecture</p>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-3 left-3 rounded-md border bg-white/90 px-3 py-2 text-[10px] text-gray-500 backdrop-blur-sm">
        <p className="font-semibold text-gray-700">Level 5 — Organizational Overview</p>
        <p className="mt-0.5">Bubble size = concept count</p>
        <p>Edge color = mapping confidence:
          <span className="ml-1 font-medium text-green-600">green</span> &ge;80%,
          <span className="ml-0.5 font-medium text-amber-600">amber</span> &ge;50%,
          <span className="ml-0.5 font-medium text-red-600">red</span> &lt;50%
        </p>
        <p>Solid edge = mostly confirmed · Dashed = candidates</p>
        <p className="mt-1 text-gray-400">Click a project to drill into L3 · Scroll to zoom · Drag to pan</p>
      </div>

      {/* Stats bar */}
      <div className="absolute bottom-3 right-3 rounded-md border bg-white/90 px-3 py-2 text-[10px] text-gray-500 backdrop-blur-sm">
        <span className="font-medium text-gray-700">{data.total_concepts}</span> concepts ·{" "}
        <span className="font-medium text-gray-700">{data.total_relationships}</span> relationships ·{" "}
        <span className="font-medium text-orange-600">{data.total_cross_edges}</span> cross-project
      </div>
    </div>
  );
}
