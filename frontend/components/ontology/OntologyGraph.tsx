"use client";

import { useEffect, useRef, useState, useMemo, useCallback } from "react";

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
  cluster?: string;
}

interface Cluster {
  key: string;
  label: string;
  nodes: SimNode[];
  cx: number;
  cy: number;
  radius: number;
  color: { bg: string; border: string; text: string };
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

// --- Clustered Force Simulation ---
// Groups nodes by concept_type, positions clusters in a circle,
// then runs a lighter force simulation WITHIN each cluster.

function buildClusters(
  nodes: SimNode[],
  edges: GraphEdge[],
  canvasWidth: number,
  canvasHeight: number
): Cluster[] {
  // Group nodes by concept_type
  const groups = new Map<string, SimNode[]>();
  nodes.forEach((n) => {
    const key = n.concept_type || "Default";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push({ ...n, cluster: key });
  });

  const clusterKeys = Array.from(groups.keys()).sort();
  const centerX = canvasWidth / 2;
  const centerY = canvasHeight / 2;
  const clusterCount = clusterKeys.length;

  // Position clusters in a circle around center
  const clusterRadius = Math.min(canvasWidth, canvasHeight) * 0.35;
  const clusters: Cluster[] = [];

  clusterKeys.forEach((key, i) => {
    const clusterNodes = groups.get(key)!;
    const angle = (2 * Math.PI * i) / clusterCount - Math.PI / 2;
    const cx = centerX + Math.cos(angle) * clusterRadius;
    const cy = centerY + Math.sin(angle) * clusterRadius;

    // Arrange nodes within cluster in a compact circle
    const nodeCount = clusterNodes.length;
    const innerRadius = Math.max(60, Math.min(200, nodeCount * 15));

    // Build edge lookup for this cluster's nodes
    const clusterNodeIds = new Set(clusterNodes.map((n) => n.id));

    clusterNodes.forEach((n, j) => {
      if (nodeCount <= 1) {
        n.x = cx;
        n.y = cy;
      } else {
        const a = (2 * Math.PI * j) / nodeCount;
        n.x = cx + Math.cos(a) * innerRadius + (Math.random() - 0.5) * 20;
        n.y = cy + Math.sin(a) * innerRadius + (Math.random() - 0.5) * 20;
      }
      n.vx = 0;
      n.vy = 0;
    });

    // Light intra-cluster force simulation (only 40 iterations, only within-cluster pairs)
    const intraEdges = edges.filter(
      (e) => clusterNodeIds.has(e.source_concept_id) && clusterNodeIds.has(e.target_concept_id)
    );

    for (let iter = 0; iter < 40; iter++) {
      // Repulsion within cluster (limited)
      for (let a = 0; a < clusterNodes.length; a++) {
        for (let b = a + 1; b < clusterNodes.length; b++) {
          const dx = clusterNodes[a].x - clusterNodes[b].x;
          const dy = clusterNodes[a].y - clusterNodes[b].y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = 3000 / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          clusterNodes[a].vx += fx;
          clusterNodes[a].vy += fy;
          clusterNodes[b].vx -= fx;
          clusterNodes[b].vy -= fy;
        }
      }

      // Attraction along intra-cluster edges
      const nodeMap = new Map(clusterNodes.map((n) => [n.id, n]));
      intraEdges.forEach((e) => {
        const src = nodeMap.get(e.source_concept_id);
        const tgt = nodeMap.get(e.target_concept_id);
        if (!src || !tgt) return;
        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const force = 0.01 * (dist - 100);
        src.vx += (dx / dist) * force;
        src.vy += (dy / dist) * force;
        tgt.vx -= (dx / dist) * force;
        tgt.vy -= (dy / dist) * force;
      });

      // Pull toward cluster center
      clusterNodes.forEach((n) => {
        n.vx += (cx - n.x) * 0.02;
        n.vy += (cy - n.y) * 0.02;
        n.vx *= 0.8;
        n.vy *= 0.8;
        n.x += n.vx;
        n.y += n.vy;
      });
    }

    clusters.push({
      key,
      label: `${key} (${nodeCount})`,
      nodes: clusterNodes,
      cx,
      cy,
      radius: innerRadius + 40,
      color: getTypeColor(key),
    });
  });

  return clusters;
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
  const [zoom, setZoom] = useState(1);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 });
  const [expandedCluster, setExpandedCluster] = useState<string | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  // Determine if we're in large-graph mode (>200 nodes = cluster view)
  const isLargeGraph = nodes.length > 200;

  // Canvas sizing
  const canvasWidth = isLargeGraph
    ? Math.max(1400, Math.min(4000, nodes.length * 4))
    : Math.max(900, Math.min(2400, nodes.length * 120));
  const canvasHeight = isLargeGraph
    ? Math.max(1000, Math.min(3000, nodes.length * 3))
    : Math.max(600, Math.min(1600, nodes.length * 80));

  // Build clusters or simple simulation
  const { clusters, simNodes } = useMemo(() => {
    if (nodes.length === 0) return { clusters: [], simNodes: [] };

    if (isLargeGraph) {
      // Cluster mode for large graphs
      const initial: SimNode[] = nodes.map((n) => ({
        ...n, x: 0, y: 0, vx: 0, vy: 0,
      }));
      const cls = buildClusters(initial, edges, canvasWidth, canvasHeight);
      const allNodes = cls.flatMap((c) => c.nodes);
      return { clusters: cls, simNodes: allNodes };
    } else {
      // Standard force simulation for small graphs
      const initial: SimNode[] = nodes.map((n, i) => {
        const angle = (2 * Math.PI * i) / nodes.length;
        const radius = Math.min(canvasWidth, canvasHeight) * 0.3;
        return {
          ...n,
          x: canvasWidth / 2 + Math.cos(angle) * radius + (Math.random() - 0.5) * 40,
          y: canvasHeight / 2 + Math.sin(angle) * radius + (Math.random() - 0.5) * 40,
          vx: 0, vy: 0,
        };
      });

      // Run standard simulation with fewer iterations
      const iterations = Math.min(100, Math.max(30, 3000 / nodes.length));
      const centerX = canvasWidth / 2;
      const centerY = canvasHeight / 2;

      for (let iter = 0; iter < iterations; iter++) {
        for (let i = 0; i < initial.length; i++) {
          for (let j = i + 1; j < initial.length; j++) {
            const dx = initial[i].x - initial[j].x;
            const dy = initial[i].y - initial[j].y;
            const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
            const force = 8000 / (dist * dist);
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            initial[i].vx += fx; initial[i].vy += fy;
            initial[j].vx -= fx; initial[j].vy -= fy;
          }
        }

        const nodeMap = new Map(initial.map((n) => [n.id, n]));
        edges.forEach((e) => {
          const src = nodeMap.get(e.source_concept_id);
          const tgt = nodeMap.get(e.target_concept_id);
          if (!src || !tgt) return;
          const dx = tgt.x - src.x;
          const dy = tgt.y - src.y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = 0.005 * (dist - 180);
          src.vx += (dx / dist) * force; src.vy += (dy / dist) * force;
          tgt.vx -= (dx / dist) * force; tgt.vy -= (dy / dist) * force;
        });

        initial.forEach((n) => {
          n.vx += (centerX - n.x) * 0.01;
          n.vy += (centerY - n.y) * 0.01;
          n.vx *= 0.85; n.vy *= 0.85;
          n.x += n.vx; n.y += n.vy;
          n.x = Math.max(80, Math.min(canvasWidth - 80, n.x));
          n.y = Math.max(50, Math.min(canvasHeight - 50, n.y));
        });
      }

      return { clusters: [], simNodes: initial };
    }
  }, [nodes, edges, canvasWidth, canvasHeight, isLargeGraph]);

  const nodeMap = useMemo(
    () => new Map(simNodes.map((n) => [n.id, n])),
    [simNodes]
  );

  // Visible nodes (for large graphs, only show expanded cluster or cluster summaries)
  const visibleNodes = useMemo(() => {
    if (!isLargeGraph) return simNodes;
    if (!expandedCluster) return []; // In cluster overview, individual nodes hidden
    return simNodes.filter((n) => n.cluster === expandedCluster);
  }, [isLargeGraph, expandedCluster, simNodes]);

  // Visible edges
  const visibleEdges = useMemo(() => {
    if (!isLargeGraph) return edges;
    if (!expandedCluster) return [];
    const visibleIds = new Set(visibleNodes.map((n) => n.id));
    return edges.filter(
      (e) => visibleIds.has(e.source_concept_id) && visibleIds.has(e.target_concept_id)
    );
  }, [isLargeGraph, expandedCluster, edges, visibleNodes]);

  // Inter-cluster edges (for cluster-level view)
  const interClusterEdges = useMemo(() => {
    if (!isLargeGraph || expandedCluster) return [];
    const nodeToCluster = new Map<number, string>();
    simNodes.forEach((n) => {
      if (n.cluster) nodeToCluster.set(n.id, n.cluster);
    });
    const seen = new Set<string>();
    const result: { from: string; to: string; count: number }[] = [];
    const countMap = new Map<string, number>();

    edges.forEach((e) => {
      const srcCluster = nodeToCluster.get(e.source_concept_id);
      const tgtCluster = nodeToCluster.get(e.target_concept_id);
      if (srcCluster && tgtCluster && srcCluster !== tgtCluster) {
        const key = [srcCluster, tgtCluster].sort().join("||");
        countMap.set(key, (countMap.get(key) || 0) + 1);
      }
    });

    countMap.forEach((count, key) => {
      const [from, to] = key.split("||");
      result.push({ from, to, count });
    });

    return result;
  }, [isLargeGraph, expandedCluster, edges, simNodes]);

  // Zoom/Pan handlers
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom((z) => Math.max(0.2, Math.min(3, z * delta)));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 1 || e.button === 0 && e.altKey) {
      setIsPanning(true);
      panStartRef.current = { x: e.clientX, y: e.clientY, panX, panY };
      e.preventDefault();
    }
  }, [panX, panY]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return;
    const dx = e.clientX - panStartRef.current.x;
    const dy = e.clientY - panStartRef.current.y;
    setPanX(panStartRef.current.panX + dx);
    setPanY(panStartRef.current.panY + dy);
  }, [isPanning]);

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
  }, []);

  // Reset view
  const resetView = useCallback(() => {
    setZoom(1);
    setPanX(0);
    setPanY(0);
    setExpandedCluster(null);
  }, []);

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
    <div className="relative rounded-lg border bg-white" style={{ maxHeight: "75vh", overflow: "hidden" }}>
      {/* Controls overlay */}
      <div className="absolute top-3 right-3 z-20 flex items-center gap-2">
        <div className="flex items-center gap-1 rounded-lg bg-white/90 border shadow-sm px-2 py-1 backdrop-blur-sm">
          <button
            onClick={() => setZoom((z) => Math.min(3, z * 1.2))}
            className="px-2 py-0.5 text-sm font-bold text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded"
          >+</button>
          <span className="text-xs font-mono text-gray-500 min-w-[3rem] text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={() => setZoom((z) => Math.max(0.2, z * 0.8))}
            className="px-2 py-0.5 text-sm font-bold text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded"
          >-</button>
        </div>
        <button
          onClick={resetView}
          className="rounded-lg bg-white/90 border shadow-sm px-2 py-1 text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-100 backdrop-blur-sm"
        >
          Reset
        </button>
        {isLargeGraph && expandedCluster && (
          <button
            onClick={() => setExpandedCluster(null)}
            className="rounded-lg bg-blue-50 border border-blue-200 shadow-sm px-2 py-1 text-xs text-blue-700 hover:bg-blue-100 backdrop-blur-sm"
          >
            ← All Clusters
          </button>
        )}
      </div>

      {/* Info overlay */}
      <div className="absolute top-3 left-3 z-20 rounded-lg bg-white/90 border shadow-sm px-3 py-1.5 backdrop-blur-sm">
        <div className="flex items-center gap-3 text-xs">
          <span className="font-medium text-gray-700">{nodes.length} concepts</span>
          <span className="text-gray-500">{edges.length} relationships</span>
          {isLargeGraph && (
            <span className="text-blue-600 font-medium">
              {expandedCluster ? `Viewing: ${expandedCluster}` : `${clusters.length} clusters`}
            </span>
          )}
          <span className="text-gray-400 text-[10px]">Scroll=zoom · Alt+drag=pan</span>
        </div>
      </div>

      {/* SVG Canvas */}
      <div
        ref={containerRef}
        style={{ width: "100%", height: "70vh", cursor: isPanning ? "grabbing" : "default" }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <svg
          width="100%"
          height="100%"
          viewBox={`${-panX / zoom} ${-panY / zoom} ${(containerRef.current?.clientWidth || 900) / zoom} ${(containerRef.current?.clientHeight || 600) / zoom}`}
        >
          <defs>
            <ArrowMarker id="arrow-default" color="#9ca3af" />
            <ArrowMarker id="arrow-selected" color="#3b82f6" />
            <ArrowMarker id="arrow-cluster" color="#94a3b8" />
          </defs>

          {/* Background */}
          <rect
            x={-panX / zoom}
            y={-panY / zoom}
            width={(containerRef.current?.clientWidth || 2000) / zoom}
            height={(containerRef.current?.clientHeight || 1500) / zoom}
            fill="#fafbfc"
            onClick={() => { onSelectNode(null); setExpandedCluster(null); }}
          />

          {/* Grid */}
          <g opacity={0.15}>
            {Array.from({ length: Math.ceil(canvasWidth / 100) + 1 }).map((_, i) => (
              <line key={`vg-${i}`} x1={i * 100} y1={0} x2={i * 100} y2={canvasHeight} stroke="#cbd5e1" strokeWidth={0.5} />
            ))}
            {Array.from({ length: Math.ceil(canvasHeight / 100) + 1 }).map((_, i) => (
              <line key={`hg-${i}`} x1={0} y1={i * 100} x2={canvasWidth} y2={i * 100} stroke="#cbd5e1" strokeWidth={0.5} />
            ))}
          </g>

          {/* === CLUSTER VIEW (Large Graphs) === */}
          {isLargeGraph && !expandedCluster && (
            <>
              {/* Inter-cluster edges */}
              {interClusterEdges.map((ice, idx) => {
                const srcCluster = clusters.find((c) => c.key === ice.from);
                const tgtCluster = clusters.find((c) => c.key === ice.to);
                if (!srcCluster || !tgtCluster) return null;
                const midX = (srcCluster.cx + tgtCluster.cx) / 2;
                const midY = (srcCluster.cy + tgtCluster.cy) / 2;
                return (
                  <g key={`ice-${idx}`}>
                    <line
                      x1={srcCluster.cx} y1={srcCluster.cy}
                      x2={tgtCluster.cx} y2={tgtCluster.cy}
                      stroke="#94a3b8"
                      strokeWidth={Math.min(4, 1 + ice.count * 0.3)}
                      strokeDasharray="8,4"
                      opacity={0.5}
                    />
                    <g transform={`translate(${midX}, ${midY})`}>
                      <rect x={-12} y={-9} width={24} height={18} rx={9} fill="white" stroke="#94a3b8" strokeWidth={1} />
                      <text textAnchor="middle" dy="4" fontSize={9} fontWeight={600} fill="#64748b" className="pointer-events-none">
                        {ice.count}
                      </text>
                    </g>
                  </g>
                );
              })}

              {/* Cluster bubbles */}
              {clusters.map((cluster) => (
                <g
                  key={`cluster-${cluster.key}`}
                  className="cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation();
                    setExpandedCluster(cluster.key);
                    // Zoom to fit cluster
                    setZoom(1.5);
                    const containerW = containerRef.current?.clientWidth || 900;
                    const containerH = containerRef.current?.clientHeight || 600;
                    setPanX((containerW / 2 - cluster.cx) * 1.5);
                    setPanY((containerH / 2 - cluster.cy) * 1.5);
                  }}
                >
                  {/* Cluster background circle */}
                  <circle
                    cx={cluster.cx} cy={cluster.cy}
                    r={cluster.radius}
                    fill={cluster.color.bg}
                    stroke={cluster.color.border}
                    strokeWidth={2}
                    opacity={0.6}
                  />
                  {/* Cluster hover ring */}
                  <circle
                    cx={cluster.cx} cy={cluster.cy}
                    r={cluster.radius}
                    fill="transparent"
                    stroke={cluster.color.border}
                    strokeWidth={0}
                    className="hover:stroke-[3px] transition-all"
                  />
                  {/* Mini node dots inside cluster */}
                  {cluster.nodes.slice(0, 30).map((n, i) => (
                    <circle
                      key={`dot-${n.id}`}
                      cx={n.x} cy={n.y}
                      r={3}
                      fill={cluster.color.border}
                      opacity={0.4}
                    />
                  ))}
                  {/* Cluster label */}
                  <text
                    x={cluster.cx} y={cluster.cy - 8}
                    textAnchor="middle"
                    fontSize={14}
                    fontWeight={700}
                    fill={cluster.color.text}
                    className="pointer-events-none"
                  >
                    {cluster.key}
                  </text>
                  <text
                    x={cluster.cx} y={cluster.cy + 10}
                    textAnchor="middle"
                    fontSize={11}
                    fill={cluster.color.text}
                    opacity={0.7}
                    className="pointer-events-none"
                  >
                    {cluster.nodes.length} concepts
                  </text>
                  <text
                    x={cluster.cx} y={cluster.cy + 24}
                    textAnchor="middle"
                    fontSize={10}
                    fill={cluster.color.border}
                    className="pointer-events-none"
                  >
                    Click to expand →
                  </text>
                </g>
              ))}
            </>
          )}

          {/* === DETAIL VIEW (Expanded cluster or small graph) === */}
          {((!isLargeGraph) || expandedCluster) && (
            <>
              {/* Edges */}
              {visibleEdges.map((e) => {
                const src = nodeMap.get(e.source_concept_id);
                const tgt = nodeMap.get(e.target_concept_id);
                if (!src || !tgt) return null;
                const isConnected = selectedId === e.source_concept_id || selectedId === e.target_concept_id;
                const path = edgePath(e);
                if (!path) return null;

                const midX = (src.x + tgt.x) / 2;
                const midY = (src.y + tgt.y) / 2;

                return (
                  <g key={`edge-${e.id}`}>
                    <path
                      d={path}
                      stroke={isConnected ? "#3b82f6" : "#d1d5db"}
                      strokeWidth={isConnected ? 2.5 : 1.5}
                      fill="none"
                      markerEnd={`url(#arrow-${isConnected ? "selected" : "default"})`}
                      className="cursor-pointer"
                      onClick={(ev) => { ev.stopPropagation(); onSelectEdge?.(e); }}
                    />
                    <g transform={`translate(${midX}, ${midY})`}>
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
                        textAnchor="middle" dy="4"
                        className="pointer-events-none select-none"
                        fontSize={10} fontWeight={500}
                        fill={isConnected ? "#2563eb" : "#6b7280"}
                      >
                        {e.relationship_type}
                      </text>
                    </g>
                  </g>
                );
              })}

              {/* Nodes */}
              {visibleNodes.map((n) => {
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
                    {isSelected && (
                      <rect
                        x={-nodeWidth / 2 - 4} y={-nodeHeight / 2 - 4}
                        width={nodeWidth + 8} height={nodeHeight + 8}
                        rx={14} fill="none" stroke="#3b82f6" strokeWidth={2.5} opacity={0.6}
                      />
                    )}
                    <rect
                      x={-nodeWidth / 2 + 2} y={-nodeHeight / 2 + 2}
                      width={nodeWidth} height={nodeHeight}
                      rx={10} fill="#00000008"
                    />
                    <rect
                      x={-nodeWidth / 2} y={-nodeHeight / 2}
                      width={nodeWidth} height={nodeHeight}
                      rx={10}
                      fill={color.bg}
                      stroke={isSelected ? "#3b82f6" : color.border}
                      strokeWidth={isSelected ? 2 : 1.5}
                    />
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
                    <circle
                      cx={nodeWidth / 2 - 10} cy={-nodeHeight / 2 + 10} r={4}
                      fill={n.confidence_score >= 0.8 ? "#22c55e" : n.confidence_score >= 0.5 ? "#f59e0b" : "#ef4444"}
                    />
                    <text
                      textAnchor="middle" dy="1" fontSize={12} fontWeight={600}
                      fill={color.text} className="pointer-events-none select-none"
                    >
                      {n.name.length > 18 ? n.name.substring(0, 16) + "..." : n.name}
                    </text>
                    <text
                      textAnchor="middle" dy="14" fontSize={9}
                      fill={color.text} opacity={0.6}
                      className="pointer-events-none select-none"
                    >
                      {n.concept_type}
                    </text>
                  </g>
                );
              })}
            </>
          )}
        </svg>
      </div>
    </div>
  );
}
