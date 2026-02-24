"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

// --- Types ---

interface MetaNode {
  id: number;
  name: string;
  concept_type: string;
  source_type: string;
  initiative_id: number | null;
  confidence_score: number;
}

interface MetaEdge {
  id: number;
  source_concept_id: number;
  target_concept_id: number;
  relationship_type: string;
  confidence_score: number;
  edge_type: "intra_project" | "cross_project";
  status?: string;
  mapping_method?: string;
  initiative_a_id?: number;
  initiative_b_id?: number;
}

interface Project {
  id: number;
  name: string;
}

interface MetaGraphData {
  nodes: MetaNode[];
  intra_edges: MetaEdge[];
  cross_edges: MetaEdge[];
  total_nodes: number;
  total_intra_edges: number;
  total_cross_edges: number;
  projects: Project[];
}

// --- Color Palette for Projects ---

const PROJECT_COLORS = [
  { bg: "#dbeafe", border: "#3b82f6", text: "#1d4ed8" }, // blue
  { bg: "#dcfce7", border: "#22c55e", text: "#15803d" }, // green
  { bg: "#fef3c7", border: "#f59e0b", text: "#b45309" }, // amber
  { bg: "#fce7f3", border: "#ec4899", text: "#be185d" }, // pink
  { bg: "#e0e7ff", border: "#6366f1", text: "#4338ca" }, // indigo
  { bg: "#f3e8ff", border: "#a855f7", text: "#7c3aed" }, // purple
  { bg: "#ccfbf1", border: "#14b8a6", text: "#0f766e" }, // teal
  { bg: "#ffedd5", border: "#f97316", text: "#c2410c" }, // orange
];

function getProjectColor(index: number) {
  return PROJECT_COLORS[index % PROJECT_COLORS.length];
}

const TYPE_ABBREV: Record<string, string> = {
  TECHNOLOGY: "T",
  PROCESS: "P",
  ACTOR: "A",
  RULE: "R",
  REQUIREMENT: "Rq",
  DATA_ENTITY: "D",
  SYSTEM: "S",
  FEATURE: "F",
};

// --- Force Simulation Node ---

interface SimNode extends MetaNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  fx?: number | null; // fixed position for dragging
  fy?: number | null;
}

// --- Component ---

export function MetaGraphView({
  data,
  onSelectMapping,
}: {
  data: MetaGraphData;
  onSelectMapping?: (mappingId: number) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [nodes, setNodes] = useState<SimNode[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<number | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; node: SimNode } | null>(null);

  // Zoom / pan state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

  // Drag state
  const [dragNodeId, setDragNodeId] = useState<number | null>(null);
  const dragRef = useRef<{ startX: number; startY: number } | null>(null);

  // Search
  const [search, setSearch] = useState("");

  const allEdges = useMemo(
    () => [...data.intra_edges, ...data.cross_edges],
    [data.intra_edges, data.cross_edges]
  );

  // Project color map
  const projectColorMap = useMemo(() => {
    const map = new Map<number, { bg: string; border: string; text: string }>();
    data.projects.forEach((p, i) => map.set(p.id, getProjectColor(i)));
    return map;
  }, [data.projects]);

  const unscopedColor = { bg: "#f3f4f6", border: "#9ca3af", text: "#4b5563" };

  // World dimensions for simulation
  const WORLD_W = 1600;
  const WORLD_H = 1000;

  // Force simulation
  useEffect(() => {
    if (data.nodes.length === 0) return;

    const projectGroups = new Map<number | null, MetaNode[]>();
    data.nodes.forEach((n) => {
      const key = n.initiative_id;
      if (!projectGroups.has(key)) projectGroups.set(key, []);
      projectGroups.get(key)!.push(n);
    });

    const groupKeys = Array.from(projectGroups.keys());
    const clusterRadius = Math.min(WORLD_W, WORLD_H) * 0.3;
    const centerX = WORLD_W / 2;
    const centerY = WORLD_H / 2;

    const simNodes: SimNode[] = [];
    groupKeys.forEach((key, gi) => {
      const group = projectGroups.get(key)!;
      const angle = (gi / Math.max(groupKeys.length, 1)) * 2 * Math.PI;
      const cx = centerX + Math.cos(angle) * clusterRadius;
      const cy = centerY + Math.sin(angle) * clusterRadius;

      group.forEach((n, ni) => {
        const innerAngle = (ni / Math.max(group.length, 1)) * 2 * Math.PI;
        const spread = Math.min(200, group.length * 18);
        simNodes.push({
          ...n,
          x: cx + Math.cos(innerAngle) * spread + (Math.random() - 0.5) * 40,
          y: cy + Math.sin(innerAngle) * spread + (Math.random() - 0.5) * 40,
          vx: 0,
          vy: 0,
        });
      });
    });

    const nodeMap = new Map(simNodes.map((n) => [n.id, n]));
    const iterations = 120;

    for (let iter = 0; iter < iterations; iter++) {
      const alpha = 1 - iter / iterations;

      // Stronger repulsion for better spacing
      for (let i = 0; i < simNodes.length; i++) {
        for (let j = i + 1; j < simNodes.length; j++) {
          const a = simNodes[i];
          const b = simNodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          // Much stronger repulsion
          const force = (3000 * alpha) / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          a.vx -= fx;
          a.vy -= fy;
          b.vx += fx;
          b.vy += fy;
        }
      }

      // Edge attraction
      allEdges.forEach((e) => {
        const source = nodeMap.get(e.source_concept_id);
        const target = nodeMap.get(e.target_concept_id);
        if (!source || !target) return;
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const strength = e.edge_type === "cross_project" ? 0.01 : 0.04;
        const force = dist * strength * alpha;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        source.vx += fx;
        source.vy += fy;
        target.vx -= fx;
        target.vy -= fy;
      });

      // Center pull
      simNodes.forEach((n) => {
        n.vx += (centerX - n.x) * 0.003 * alpha;
        n.vy += (centerY - n.y) * 0.003 * alpha;
      });

      // Apply velocity with damping
      simNodes.forEach((n) => {
        n.x += n.vx * 0.4;
        n.y += n.vy * 0.4;
        n.vx *= 0.8;
        n.vy *= 0.8;
        n.x = Math.max(80, Math.min(WORLD_W - 80, n.x));
        n.y = Math.max(60, Math.min(WORLD_H - 60, n.y));
      });
    }

    setNodes([...simNodes]);
    // Auto-fit: reset pan and zoom
    setPan({ x: 0, y: 0 });
    setZoom(1);
  }, [data, allEdges]);

  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  // Search highlight
  const searchLower = search.toLowerCase();
  const matchedIds = useMemo(() => {
    if (!searchLower) return new Set<number>();
    return new Set(
      nodes
        .filter(
          (n) =>
            n.name.toLowerCase().includes(searchLower) ||
            n.concept_type.toLowerCase().includes(searchLower)
        )
        .map((n) => n.id)
    );
  }, [nodes, searchLower]);

  // Connected edges/nodes for selected node
  const selectedEdges = useMemo(() => {
    if (!selectedNodeId) return new Set<number>();
    return new Set(
      allEdges
        .filter(
          (e) =>
            e.source_concept_id === selectedNodeId ||
            e.target_concept_id === selectedNodeId
        )
        .map((e) => e.id)
    );
  }, [allEdges, selectedNodeId]);

  const connectedNodeIds = useMemo(() => {
    if (!selectedNodeId) return new Set<number>();
    const ids = new Set<number>();
    ids.add(selectedNodeId);
    allEdges.forEach((e) => {
      if (e.source_concept_id === selectedNodeId) ids.add(e.target_concept_id);
      if (e.target_concept_id === selectedNodeId) ids.add(e.source_concept_id);
    });
    return ids;
  }, [allEdges, selectedNodeId]);

  // --- Zoom handlers ---
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.08 : 0.08;
      setZoom((z) => Math.max(0.2, Math.min(3, z + delta)));
    },
    []
  );

  const zoomIn = () => setZoom((z) => Math.min(3, z + 0.2));
  const zoomOut = () => setZoom((z) => Math.max(0.2, z - 0.2));
  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // --- Pan handlers ---
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      // Only pan on background (not node) click
      if ((e.target as Element).closest(".meta-node")) return;
      setIsPanning(true);
      panStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
    },
    [pan]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (dragNodeId !== null && dragRef.current) {
        // Drag node
        const rect = svgRef.current?.getBoundingClientRect();
        if (!rect) return;
        const nx = (e.clientX - rect.left - pan.x) / zoom;
        const ny = (e.clientY - rect.top - pan.y) / zoom;
        setNodes((prev) =>
          prev.map((n) =>
            n.id === dragNodeId
              ? { ...n, x: Math.max(40, Math.min(WORLD_W - 40, nx)), y: Math.max(30, Math.min(WORLD_H - 30, ny)) }
              : n
          )
        );
        return;
      }
      if (!isPanning) return;
      const dx = e.clientX - panStart.current.x;
      const dy = e.clientY - panStart.current.y;
      setPan({ x: panStart.current.panX + dx, y: panStart.current.panY + dy });
    },
    [isPanning, dragNodeId, pan, zoom]
  );

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
    setDragNodeId(null);
    dragRef.current = null;
  }, []);

  // --- Node drag ---
  const handleNodeDragStart = useCallback(
    (e: React.MouseEvent, nodeId: number) => {
      e.stopPropagation();
      setDragNodeId(nodeId);
      dragRef.current = { startX: e.clientX, startY: e.clientY };
    },
    []
  );

  // --- Tooltip ---
  const handleNodeHover = useCallback(
    (e: React.MouseEvent, node: SimNode) => {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setHoveredNodeId(node.id);
      setTooltip({
        x: e.clientX - rect.left + 12,
        y: e.clientY - rect.top - 8,
        node,
      });
    },
    []
  );

  const handleNodeLeave = useCallback(() => {
    setHoveredNodeId(null);
    setTooltip(null);
  }, []);

  if (data.nodes.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border bg-white text-sm text-gray-400">
        No concepts available for meta-graph. Create projects and extract ontology first.
      </div>
    );
  }

  const viewBox = `0 0 ${WORLD_W} ${WORLD_H}`;

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-white px-4 py-2.5">
        {/* Legend */}
        <span className="text-xs font-medium text-gray-500">Projects:</span>
        {data.projects.map((p, i) => {
          const color = getProjectColor(i);
          return (
            <div key={p.id} className="flex items-center gap-1.5">
              <span
                className="inline-block h-3 w-3 rounded-sm border"
                style={{ backgroundColor: color.bg, borderColor: color.border }}
              />
              <span className="text-xs text-gray-600">{p.name}</span>
            </div>
          );
        })}

        <div className="mx-2 h-4 w-px bg-gray-200" />

        {/* Edge legend */}
        <span className="flex items-center gap-1 text-xs text-gray-400">
          <span className="h-px w-5 bg-gray-400" /> Intra
        </span>
        <span className="flex items-center gap-1 text-xs text-gray-400">
          <span className="h-px w-5 border-t-2 border-dashed border-orange-400" /> Cross
        </span>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Search */}
        <input
          type="text"
          placeholder="Search nodes..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-40 rounded border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-700 placeholder-gray-400 focus:border-blue-300 focus:outline-none"
        />

        {/* Zoom controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={zoomOut}
            className="rounded border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs text-gray-600 hover:bg-gray-100"
          >
            -
          </button>
          <span className="min-w-[3rem] text-center text-xs text-gray-500">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={zoomIn}
            className="rounded border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs text-gray-600 hover:bg-gray-100"
          >
            +
          </button>
          <button
            onClick={resetView}
            className="ml-1 rounded border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs text-gray-600 hover:bg-gray-100"
            title="Reset view"
          >
            Fit
          </button>
        </div>
      </div>

      {/* Graph canvas */}
      <div
        ref={containerRef}
        className="relative overflow-hidden rounded-lg border bg-white"
        style={{ height: "600px", cursor: isPanning ? "grabbing" : dragNodeId ? "grabbing" : "grab" }}
        onWheel={handleWheel}
      >
        <svg
          ref={svgRef}
          width="100%"
          height="100%"
          viewBox={viewBox}
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "0 0",
          }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          className="select-none"
        >
          {/* Background grid */}
          <defs>
            <pattern
              id="metaGrid"
              width="50"
              height="50"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 50 0 L 0 0 0 50"
                fill="none"
                stroke="#f0f0f0"
                strokeWidth="0.5"
              />
            </pattern>
            <marker
              id="metaArrow"
              viewBox="0 0 10 10"
              refX="22"
              refY="5"
              markerWidth="4"
              markerHeight="4"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
            </marker>
            <marker
              id="metaCrossArrow"
              viewBox="0 0 10 10"
              refX="22"
              refY="5"
              markerWidth="4"
              markerHeight="4"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#f97316" />
            </marker>
            {/* Glow filter for search matches */}
            <filter id="searchGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <rect width={WORLD_W} height={WORLD_H} fill="url(#metaGrid)" />

          {/* Project cluster backgrounds */}
          {data.projects.map((p, i) => {
            const color = getProjectColor(i);
            const projectNodes = nodes.filter((n) => n.initiative_id === p.id);
            if (projectNodes.length === 0) return null;

            const padding = 50;
            const minX = Math.min(...projectNodes.map((n) => n.x)) - padding;
            const minY = Math.min(...projectNodes.map((n) => n.y)) - padding;
            const maxX = Math.max(...projectNodes.map((n) => n.x)) + padding;
            const maxY = Math.max(...projectNodes.map((n) => n.y)) + padding;

            return (
              <g key={`cluster-${p.id}`}>
                <rect
                  x={minX}
                  y={minY}
                  width={maxX - minX}
                  height={maxY - minY}
                  rx={16}
                  fill={color.bg}
                  fillOpacity={0.15}
                  stroke={color.border}
                  strokeWidth={1}
                  strokeDasharray="8 4"
                  strokeOpacity={0.5}
                />
                <text
                  x={minX + 12}
                  y={minY + 18}
                  fontSize={12}
                  fontWeight={600}
                  fill={color.text}
                  opacity={0.7}
                >
                  {p.name}
                </text>
              </g>
            );
          })}

          {/* Intra-project edges */}
          {data.intra_edges.map((e) => {
            const source = nodeMap.get(e.source_concept_id);
            const target = nodeMap.get(e.target_concept_id);
            if (!source || !target) return null;
            const dimmed =
              selectedNodeId !== null && !selectedEdges.has(e.id);
            return (
              <line
                key={`intra-${e.id}`}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke="#cbd5e1"
                strokeWidth={1}
                opacity={dimmed ? 0.1 : 0.6}
                markerEnd="url(#metaArrow)"
              />
            );
          })}

          {/* Cross-project edges */}
          {data.cross_edges.map((e) => {
            const source = nodeMap.get(e.source_concept_id);
            const target = nodeMap.get(e.target_concept_id);
            if (!source || !target) return null;
            const color =
              e.status === "confirmed"
                ? "#22c55e"
                : e.status === "candidate"
                ? "#f59e0b"
                : "#ef4444";
            const dimmed =
              selectedNodeId !== null && !selectedEdges.has(e.id);
            return (
              <g key={`cross-${e.id}`}>
                <line
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  stroke={color}
                  strokeWidth={2}
                  strokeDasharray="8 4"
                  opacity={dimmed ? 0.1 : 0.8}
                  markerEnd="url(#metaCrossArrow)"
                  className="cursor-pointer"
                  onClick={() => onSelectMapping?.(e.id)}
                />
                {!dimmed && (
                  <text
                    x={(source.x + target.x) / 2}
                    y={(source.y + target.y) / 2 - 8}
                    fontSize={8}
                    fill={color}
                    textAnchor="middle"
                    fontWeight={600}
                    opacity={0.8}
                  >
                    {e.relationship_type?.replace(/_/g, " ")}
                  </text>
                )}
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const color = node.initiative_id
              ? projectColorMap.get(node.initiative_id) || unscopedColor
              : unscopedColor;
            const isSelected = selectedNodeId === node.id;
            const isHovered = hoveredNodeId === node.id;
            const isSearchMatch = searchLower && matchedIds.has(node.id);
            const dimmed =
              selectedNodeId !== null &&
              !connectedNodeIds.has(node.id);
            const searchDimmed =
              searchLower && !matchedIds.has(node.id);
            const opacity = dimmed || searchDimmed ? 0.15 : 1;
            const r = isSelected || isHovered ? 18 : 14;

            return (
              <g
                key={node.id}
                className="meta-node"
                style={{ cursor: "pointer", opacity }}
                onClick={() =>
                  setSelectedNodeId(isSelected ? null : node.id)
                }
                onMouseDown={(e) => handleNodeDragStart(e, node.id)}
                onMouseEnter={(e) => handleNodeHover(e, node)}
                onMouseLeave={handleNodeLeave}
                filter={isSearchMatch ? "url(#searchGlow)" : undefined}
              >
                {/* Outer ring for selected */}
                {isSelected && (
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={22}
                    fill="none"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    strokeDasharray="4 2"
                    opacity={0.5}
                  />
                )}
                {/* Node circle */}
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={r}
                  fill={color.bg}
                  stroke={
                    isSelected
                      ? "#2563eb"
                      : isSearchMatch
                      ? "#f59e0b"
                      : color.border
                  }
                  strokeWidth={isSelected ? 2.5 : isSearchMatch ? 2 : 1.5}
                />
                {/* Type badge */}
                <text
                  x={node.x}
                  y={node.y + 4}
                  textAnchor="middle"
                  fontSize={10}
                  fontWeight={700}
                  fill={color.text}
                >
                  {TYPE_ABBREV[node.concept_type] || node.concept_type.charAt(0)}
                </text>
                {/* Label */}
                <text
                  x={node.x}
                  y={node.y + 28}
                  textAnchor="middle"
                  fontSize={8}
                  fill="#374151"
                  fontWeight={isSelected ? 600 : 400}
                >
                  {node.name.length > 22
                    ? node.name.slice(0, 20) + "..."
                    : node.name}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="pointer-events-none absolute z-50 rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-lg"
            style={{ left: tooltip.x, top: tooltip.y, maxWidth: 280 }}
          >
            <div className="text-sm font-semibold text-gray-900">
              {tooltip.node.name}
            </div>
            <div className="mt-0.5 flex items-center gap-2 text-xs text-gray-500">
              <span className="rounded bg-gray-100 px-1.5 py-0.5 font-medium">
                {tooltip.node.concept_type}
              </span>
              <span>
                {tooltip.node.source_type === "code"
                  ? "Code"
                  : tooltip.node.source_type === "both"
                  ? "Code + Doc"
                  : "Document"}
              </span>
              <span>
                {Math.round(tooltip.node.confidence_score * 100)}% confidence
              </span>
            </div>
            {tooltip.node.initiative_id && (
              <div className="mt-1 text-xs text-gray-400">
                Project:{" "}
                {data.projects.find((p) => p.id === tooltip.node.initiative_id)
                  ?.name || "Unknown"}
              </div>
            )}
          </div>
        )}

        {/* Instructions overlay */}
        <div className="absolute bottom-2 left-2 rounded bg-black/40 px-2 py-1 text-[10px] text-white/70">
          Scroll to zoom &middot; Drag background to pan &middot; Drag nodes to
          reposition &middot; Click node to focus
        </div>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-4 rounded-lg border bg-white px-4 py-2 text-xs text-gray-500">
        <span>{data.total_nodes} concepts</span>
        <span>{data.total_intra_edges} intra-project edges</span>
        <span className="font-medium text-orange-600">
          {data.total_cross_edges} cross-project edges
        </span>
        <span>{data.projects.length} projects</span>
        {selectedNodeId && (
          <>
            <span className="mx-1 text-gray-300">|</span>
            <span className="font-medium text-blue-600">
              {nodes.find((n) => n.id === selectedNodeId)?.name} selected
            </span>
            <button
              onClick={() => setSelectedNodeId(null)}
              className="ml-1 text-gray-400 hover:text-gray-600"
            >
              Clear
            </button>
          </>
        )}
      </div>
    </div>
  );
}
