"use client";

import { useEffect, useRef, useState, useMemo, useCallback } from "react";

// --- Types ---

interface GraphNode {
  id: number;
  name: string;
  concept_type: string;
  source_type?: string;
  confidence_score: number;
  description?: string;
  source_component_id?: number;
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
  degree: number;
  w: number; // computed width
}

interface Cluster {
  key: string;
  label: string;
  nodes: SimNode[];
  cx: number;
  cy: number;
  radius: number;
  color: { bg: string; border: string; text: string; gradient: string };
}

interface OntologyGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: number | null;
  onSelectNode: (id: number | null) => void;
  onSelectEdge?: (edge: GraphEdge | null) => void;
}

// --- Aesthetic Color Palette ---

const TYPE_COLORS: Record<
  string,
  { bg: string; border: string; text: string; gradient: string }
> = {
  Entity: {
    bg: "#eff6ff",
    border: "#60a5fa",
    text: "#1e40af",
    gradient: "#dbeafe",
  },
  Process: {
    bg: "#f0fdf4",
    border: "#4ade80",
    text: "#166534",
    gradient: "#dcfce7",
  },
  Attribute: {
    bg: "#fffbeb",
    border: "#fbbf24",
    text: "#92400e",
    gradient: "#fef3c7",
  },
  Value: {
    bg: "#faf5ff",
    border: "#c084fc",
    text: "#6b21a8",
    gradient: "#f3e8ff",
  },
  Event: {
    bg: "#fef2f2",
    border: "#f87171",
    text: "#991b1b",
    gradient: "#fee2e2",
  },
  Role: {
    bg: "#f0fdfa",
    border: "#2dd4bf",
    text: "#115e59",
    gradient: "#ccfbf1",
  },
  Service: {
    bg: "#eef2ff",
    border: "#818cf8",
    text: "#3730a3",
    gradient: "#e0e7ff",
  },
  Rule: {
    bg: "#fff7ed",
    border: "#fb923c",
    text: "#9a3412",
    gradient: "#ffedd5",
  },
  Default: {
    bg: "#f9fafb",
    border: "#9ca3af",
    text: "#374151",
    gradient: "#f3f4f6",
  },
};

function getTypeColor(type: string) {
  return TYPE_COLORS[type] || TYPE_COLORS.Default;
}

// --- Relationship edge color ---

const REL_COLORS: Record<string, string> = {
  contains: "#60a5fa",
  uses: "#4ade80",
  depends_on: "#fbbf24",
  implements: "#818cf8",
  extends: "#c084fc",
  relates_to: "#9ca3af",
  produces: "#f87171",
  consumes: "#2dd4bf",
  defined_in: "#60a5fa",
  calls: "#22c55e",
  delegates_to: "#14b8a6",
  enforces: "#f59e0b",
  exposes_endpoint: "#8b5cf6",
  protects: "#ef4444",
  validates: "#f97316",
  flows_to: "#06b6d4",
  followed_by: "#6366f1",
  inherits: "#a855f7",
  configures: "#84cc16",
  tests: "#ec4899",
  specifies: "#3b82f6",
  has_many: "#10b981",
  belongs_to: "#10b981",
};

function getRelColor(rel: string): string {
  const key = rel.toLowerCase().replace(/\s+/g, "_");
  return REL_COLORS[key] || "#94a3b8";
}

// --- Node width calculation ---

function nodeWidth(name: string): number {
  return Math.max(120, Math.min(240, name.length * 8.5 + 48));
}

const NODE_HEIGHT = 52;
const NODE_RX = 16;

// --- Mind-Map Layout ---
// Places the most-connected node at center, arranges connected nodes
// in concentric rings with even angular spacing per ring.

function mindMapLayout(
  nodes: SimNode[],
  edges: GraphEdge[],
  canvasW: number,
  canvasH: number
): SimNode[] {
  if (nodes.length === 0) return nodes;
  if (nodes.length === 1) {
    nodes[0].x = canvasW / 2;
    nodes[0].y = canvasH / 2;
    return nodes;
  }

  // Build adjacency for degree
  const adj = new Map<number, Set<number>>();
  nodes.forEach((n) => adj.set(n.id, new Set()));
  edges.forEach((e) => {
    adj.get(e.source_concept_id)?.add(e.target_concept_id);
    adj.get(e.target_concept_id)?.add(e.source_concept_id);
  });

  // Assign degree
  nodes.forEach((n) => {
    n.degree = adj.get(n.id)?.size ?? 0;
    n.w = nodeWidth(n.name);
  });

  // Find root = highest degree node
  const sorted = [...nodes].sort((a, b) => b.degree - a.degree);
  const root = sorted[0];

  // BFS from root to assign levels
  const visited = new Set<number>();
  const levels = new Map<number, number>();
  const queue: number[] = [root.id];
  visited.add(root.id);
  levels.set(root.id, 0);

  while (queue.length > 0) {
    const curr = queue.shift()!;
    const currLevel = levels.get(curr)!;
    for (const neighbor of adj.get(curr) || []) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        levels.set(neighbor, currLevel + 1);
        queue.push(neighbor);
      }
    }
  }

  // Orphan nodes (not reachable from root) — assign level based on type grouping
  let maxLevel = 0;
  levels.forEach((l) => {
    if (l > maxLevel) maxLevel = l;
  });
  nodes.forEach((n) => {
    if (!levels.has(n.id)) {
      levels.set(n.id, maxLevel + 1);
    }
  });

  // Group by level
  const byLevel = new Map<number, SimNode[]>();
  nodes.forEach((n) => {
    const lv = levels.get(n.id) ?? 0;
    if (!byLevel.has(lv)) byLevel.set(lv, []);
    byLevel.get(lv)!.push(n);
  });

  const centerX = canvasW / 2;
  const centerY = canvasH / 2;

  // Ring radii — generous spacing
  const ringGap = Math.max(
    180,
    Math.min(300, canvasW / ((maxLevel + 2) * 2))
  );

  const allLevels = Array.from(byLevel.keys()).sort((a, b) => a - b);

  for (const lv of allLevels) {
    const ring = byLevel.get(lv)!;
    if (lv === 0) {
      // Center node
      ring.forEach((n) => {
        n.x = centerX;
        n.y = centerY;
      });
      continue;
    }

    const radius = ringGap * lv;
    // Sort ring nodes by their parent's angle for natural branching
    ring.sort((a, b) => {
      const aParents = Array.from(adj.get(a.id) || []).filter(
        (id) => (levels.get(id) ?? 999) < lv
      );
      const bParents = Array.from(adj.get(b.id) || []).filter(
        (id) => (levels.get(id) ?? 999) < lv
      );
      const aAngle = aParents.length > 0
        ? Math.atan2(
            (nodes.find((n) => n.id === aParents[0])?.y ?? centerY) - centerY,
            (nodes.find((n) => n.id === aParents[0])?.x ?? centerX) - centerX
          )
        : 0;
      const bAngle = bParents.length > 0
        ? Math.atan2(
            (nodes.find((n) => n.id === bParents[0])?.y ?? centerY) - centerY,
            (nodes.find((n) => n.id === bParents[0])?.x ?? centerX) - centerX
          )
        : 0;
      return aAngle - bAngle;
    });

    const count = ring.length;
    const angleStep = (2 * Math.PI) / Math.max(count, 1);
    const startAngle = -Math.PI / 2; // start from top

    ring.forEach((n, i) => {
      const angle = startAngle + angleStep * i;
      n.x = centerX + Math.cos(angle) * radius;
      n.y = centerY + Math.sin(angle) * radius;
    });
  }

  // Force repulsion pass to remove overlaps (50 iterations for better separation)
  for (let iter = 0; iter < 50; iter++) {
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const minDist = (nodes[i].w + nodes[j].w) / 2 + 50;
        if (dist < minDist) {
          const push = (minDist - dist) * 0.35;
          const px = (dx / dist) * push;
          const py = (dy / dist) * push;
          // Don't push root
          if (levels.get(nodes[i].id) !== 0) {
            nodes[i].x += px;
            nodes[i].y += py;
          }
          if (levels.get(nodes[j].id) !== 0) {
            nodes[j].x -= px;
            nodes[j].y -= py;
          }
        }
      }
    }
  }

  return nodes;
}

// --- Clustered Layout for Large Graphs ---

function buildClusters(
  nodes: SimNode[],
  edges: GraphEdge[],
  canvasWidth: number,
  canvasHeight: number
): Cluster[] {
  const groups = new Map<string, SimNode[]>();
  nodes.forEach((n) => {
    const key = n.concept_type || "Default";
    n.w = nodeWidth(n.name);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push({ ...n, cluster: key });
  });

  const clusterKeys = Array.from(groups.keys()).sort();
  const centerX = canvasWidth / 2;
  const centerY = canvasHeight / 2;
  const clusterCount = clusterKeys.length;
  const clusterRadius = Math.min(canvasWidth, canvasHeight) * 0.35;
  const clusters: Cluster[] = [];

  clusterKeys.forEach((key, i) => {
    const clusterNodes = groups.get(key)!;
    const angle = (2 * Math.PI * i) / clusterCount - Math.PI / 2;
    const cx = centerX + Math.cos(angle) * clusterRadius;
    const cy = centerY + Math.sin(angle) * clusterRadius;

    const nodeCount = clusterNodes.length;
    const innerRadius = Math.max(80, Math.min(280, nodeCount * 20));
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

    const intraEdges = edges.filter(
      (e) =>
        clusterNodeIds.has(e.source_concept_id) &&
        clusterNodeIds.has(e.target_concept_id)
    );

    for (let iter = 0; iter < 40; iter++) {
      for (let a = 0; a < clusterNodes.length; a++) {
        for (let b = a + 1; b < clusterNodes.length; b++) {
          const dx = clusterNodes[a].x - clusterNodes[b].x;
          const dy = clusterNodes[a].y - clusterNodes[b].y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = 5000 / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          clusterNodes[a].vx += fx;
          clusterNodes[a].vy += fy;
          clusterNodes[b].vx -= fx;
          clusterNodes[b].vy -= fy;
        }
      }

      const nodeMap = new Map(clusterNodes.map((n) => [n.id, n]));
      intraEdges.forEach((e) => {
        const src = nodeMap.get(e.source_concept_id);
        const tgt = nodeMap.get(e.target_concept_id);
        if (!src || !tgt) return;
        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const force = 0.01 * (dist - 120);
        src.vx += (dx / dist) * force;
        src.vy += (dy / dist) * force;
        tgt.vx -= (dx / dist) * force;
        tgt.vy -= (dy / dist) * force;
      });

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
      radius: innerRadius + 50,
      color: getTypeColor(key),
    });
  });

  return clusters;
}

// --- Curved edge path (bezier) ---

function curvedEdgePath(
  sx: number,
  sy: number,
  tx: number,
  ty: number
): string {
  const dx = tx - sx;
  const dy = ty - sy;
  const dist = Math.sqrt(dx * dx + dy * dy);
  // Curvature proportional to distance, perpendicular offset
  const curvature = Math.min(40, dist * 0.15);
  // Perpendicular vector
  const nx = -dy / (dist || 1);
  const ny = dx / (dist || 1);
  const mx = (sx + tx) / 2 + nx * curvature;
  const my = (sy + ty) / 2 + ny * curvature;
  return `M ${sx} ${sy} Q ${mx} ${my} ${tx} ${ty}`;
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
  const [hoveredNodeId, setHoveredNodeId] = useState<number | null>(null);
  const [dragNodeId, setDragNodeId] = useState<number | null>(null);
  const [nodePositions, setNodePositions] = useState<Map<number, { x: number; y: number }>>(new Map());
  const dragStartRef = useRef({ x: 0, y: 0, nodeX: 0, nodeY: 0 });

  const isLargeGraph = nodes.length > 200;

  // Canvas sizing — generous for readability
  const canvasWidth = isLargeGraph
    ? Math.max(1600, Math.min(5000, nodes.length * 5))
    : Math.max(1200, Math.min(3200, nodes.length * 160));
  const canvasHeight = isLargeGraph
    ? Math.max(1200, Math.min(4000, nodes.length * 4))
    : Math.max(800, Math.min(2400, nodes.length * 100));

  // Build layout
  const { clusters, simNodes } = useMemo(() => {
    if (nodes.length === 0) return { clusters: [], simNodes: [] };

    if (isLargeGraph) {
      const initial: SimNode[] = nodes.map((n) => ({
        ...n,
        x: 0,
        y: 0,
        vx: 0,
        vy: 0,
        degree: 0,
        w: nodeWidth(n.name),
      }));
      const cls = buildClusters(initial, edges, canvasWidth, canvasHeight);
      const allNodes = cls.flatMap((c) => c.nodes);
      return { clusters: cls, simNodes: allNodes };
    } else {
      // Mind-map radial layout
      const initial: SimNode[] = nodes.map((n) => ({
        ...n,
        x: 0,
        y: 0,
        vx: 0,
        vy: 0,
        degree: 0,
        w: nodeWidth(n.name),
      }));
      mindMapLayout(initial, edges, canvasWidth, canvasHeight);
      return { clusters: [], simNodes: initial };
    }
  }, [nodes, edges, canvasWidth, canvasHeight, isLargeGraph]);

  const nodeMap = useMemo(
    () => new Map(simNodes.map((n) => [n.id, n])),
    [simNodes]
  );

  const visibleNodes = useMemo(() => {
    if (!isLargeGraph) return simNodes;
    if (!expandedCluster) return [];
    return simNodes.filter((n) => n.cluster === expandedCluster);
  }, [isLargeGraph, expandedCluster, simNodes]);

  const visibleEdges = useMemo(() => {
    if (!isLargeGraph) return edges;
    if (!expandedCluster) return [];
    const visibleIds = new Set(visibleNodes.map((n) => n.id));
    return edges.filter(
      (e) =>
        visibleIds.has(e.source_concept_id) &&
        visibleIds.has(e.target_concept_id)
    );
  }, [isLargeGraph, expandedCluster, edges, visibleNodes]);

  const interClusterEdges = useMemo(() => {
    if (!isLargeGraph || expandedCluster) return [];
    const nodeToCluster = new Map<number, string>();
    simNodes.forEach((n) => {
      if (n.cluster) nodeToCluster.set(n.id, n.cluster);
    });
    const countMap = new Map<string, number>();
    edges.forEach((e) => {
      const srcC = nodeToCluster.get(e.source_concept_id);
      const tgtC = nodeToCluster.get(e.target_concept_id);
      if (srcC && tgtC && srcC !== tgtC) {
        const key = [srcC, tgtC].sort().join("||");
        countMap.set(key, (countMap.get(key) || 0) + 1);
      }
    });
    const result: { from: string; to: string; count: number }[] = [];
    countMap.forEach((count, key) => {
      const [from, to] = key.split("||");
      result.push({ from, to, count });
    });
    return result;
  }, [isLargeGraph, expandedCluster, edges, simNodes]);

  // --- Interaction handlers ---

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.92 : 1.08;
    setZoom((z) => Math.max(0.15, Math.min(4, z * delta)));
  }, []);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      // Only start panning if not dragging a node
      if (dragNodeId !== null) return;
      if (e.button === 0 || e.button === 1) {
        setIsPanning(true);
        panStartRef.current = { x: e.clientX, y: e.clientY, panX, panY };
        e.preventDefault();
      }
    },
    [panX, panY, dragNodeId]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (dragNodeId !== null) {
        handleNodeDrag(e);
        return;
      }
      if (!isPanning) return;
      const dx = e.clientX - panStartRef.current.x;
      const dy = e.clientY - panStartRef.current.y;
      setPanX(panStartRef.current.panX + dx);
      setPanY(panStartRef.current.panY + dy);
    },
    [isPanning, dragNodeId, handleNodeDrag]
  );

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
    setDragNodeId(null);
  }, []);

  // Node drag handlers
  const handleNodeDragStart = useCallback(
    (e: React.MouseEvent, nodeId: number) => {
      e.stopPropagation();
      const n = nodeMap.get(nodeId);
      if (!n) return;
      const pos = nodePositions.get(nodeId);
      setDragNodeId(nodeId);
      dragStartRef.current = {
        x: e.clientX,
        y: e.clientY,
        nodeX: pos?.x ?? n.x,
        nodeY: pos?.y ?? n.y,
      };
    },
    [nodeMap, nodePositions]
  );

  const handleNodeDrag = useCallback(
    (e: React.MouseEvent) => {
      if (dragNodeId === null) return;
      const dx = (e.clientX - dragStartRef.current.x) / zoom;
      const dy = (e.clientY - dragStartRef.current.y) / zoom;
      setNodePositions((prev) => {
        const next = new Map(prev);
        next.set(dragNodeId, {
          x: dragStartRef.current.nodeX + dx,
          y: dragStartRef.current.nodeY + dy,
        });
        return next;
      });
    },
    [dragNodeId, zoom]
  );

  const resetView = useCallback(() => {
    setZoom(1);
    setPanX(0);
    setPanY(0);
    setExpandedCluster(null);
    setHoveredNodeId(null);
  }, []);

  // --- Edge path with node radius offset ---

  function getEdgePath(e: GraphEdge): string {
    const srcBase = nodeMap.get(e.source_concept_id);
    const tgtBase = nodeMap.get(e.target_concept_id);
    if (!srcBase || !tgtBase) return "";
    const srcPos = nodePositions.get(e.source_concept_id);
    const tgtPos = nodePositions.get(e.target_concept_id);
    const src = { ...srcBase, x: srcPos?.x ?? srcBase.x, y: srcPos?.y ?? srcBase.y };
    const tgt = { ...tgtBase, x: tgtPos?.x ?? tgtBase.x, y: tgtPos?.y ?? tgtBase.y };
    const dx = tgt.x - src.x;
    const dy = tgt.y - src.y;
    const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
    const srcR = src.w / 2 + 4;
    const tgtR = tgt.w / 2 + 4;
    const sx = src.x + (dx / dist) * srcR;
    const sy = src.y + (dy / dist) * (NODE_HEIGHT / 2 + 4);
    const tx = tgt.x - (dx / dist) * tgtR;
    const ty = tgt.y - (dy / dist) * (NODE_HEIGHT / 2 + 4);
    return curvedEdgePath(sx, sy, tx, ty);
  }

  // --- Type legend ---

  const typesUsed = useMemo(() => {
    const types = new Set<string>();
    nodes.forEach((n) => types.add(n.concept_type || "Default"));
    return Array.from(types).sort();
  }, [nodes]);

  // --- Empty state ---

  if (nodes.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center text-gray-400">
        <svg
          className="mb-3 h-16 w-16"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1}
        >
          <circle cx="12" cy="5" r="3" />
          <circle cx="5" cy="19" r="3" />
          <circle cx="19" cy="19" r="3" />
          <path d="M12 8v3m-5.5 5.5L9 14m5.5 2.5L15 14" />
        </svg>
        <p className="text-sm font-medium">No concepts yet</p>
        <p className="mt-1 text-xs">
          Upload and analyze documents to build your knowledge graph
        </p>
      </div>
    );
  }

  return (
    <div
      className="relative rounded-lg border bg-white"
      style={{ maxHeight: "75vh", overflow: "hidden" }}
    >
      {/* Controls overlay */}
      <div className="absolute top-3 right-3 z-20 flex items-center gap-2">
        <div className="flex items-center gap-1 rounded-full bg-white/95 border shadow-sm px-3 py-1.5 backdrop-blur-sm">
          <button
            onClick={() => setZoom((z) => Math.min(4, z * 1.25))}
            className="w-7 h-7 flex items-center justify-center text-sm font-bold text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full"
          >
            +
          </button>
          <span className="text-xs font-mono text-gray-500 min-w-[3rem] text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={() => setZoom((z) => Math.max(0.15, z * 0.8))}
            className="w-7 h-7 flex items-center justify-center text-sm font-bold text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full"
          >
            -
          </button>
        </div>
        <button
          onClick={resetView}
          className="rounded-full bg-white/95 border shadow-sm px-3 py-1.5 text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-100 backdrop-blur-sm"
        >
          Reset
        </button>
        {isLargeGraph && expandedCluster && (
          <button
            onClick={() => {
              setExpandedCluster(null);
              setZoom(1);
              setPanX(0);
              setPanY(0);
            }}
            className="rounded-full bg-blue-50 border border-blue-200 shadow-sm px-3 py-1.5 text-xs text-blue-700 hover:bg-blue-100 backdrop-blur-sm"
          >
            ← All Clusters
          </button>
        )}
      </div>

      {/* Info overlay */}
      <div className="absolute top-3 left-3 z-20 rounded-full bg-white/95 border shadow-sm px-4 py-1.5 backdrop-blur-sm">
        <div className="flex items-center gap-3 text-xs">
          <span className="font-semibold text-gray-700">
            {nodes.length} concepts
          </span>
          <span className="text-gray-400">|</span>
          <span className="text-gray-500">{edges.length} relationships</span>
          {isLargeGraph && (
            <>
              <span className="text-gray-400">|</span>
              <span className="text-blue-600 font-medium">
                {expandedCluster
                  ? `${expandedCluster}`
                  : `${clusters.length} clusters`}
              </span>
            </>
          )}
          <span className="text-gray-300 text-[10px]">
            Drag node=move · Drag bg=pan · Scroll=zoom
          </span>
        </div>
      </div>

      {/* Type legend */}
      <div className="absolute bottom-3 left-3 z-20 flex flex-wrap gap-1.5 rounded-lg bg-white/95 border shadow-sm px-3 py-2 backdrop-blur-sm max-w-[60%]">
        {typesUsed.map((type) => {
          const c = getTypeColor(type);
          return (
            <div
              key={type}
              className="flex items-center gap-1.5 text-[10px]"
            >
              <div
                className="w-3 h-3 rounded-sm border"
                style={{ backgroundColor: c.bg, borderColor: c.border }}
              />
              <span style={{ color: c.text }} className="font-medium">
                {type}
              </span>
            </div>
          );
        })}
      </div>

      {/* Hover tooltip */}
      {hoveredNodeId !== null && (() => {
        const n = nodeMap.get(hoveredNodeId);
        if (!n) return null;
        const color = getTypeColor(n.concept_type);
        return (
          <div
            className="absolute z-30 rounded-lg border bg-white shadow-lg px-4 py-3 pointer-events-none"
            style={{
              bottom: 52,
              right: 12,
              maxWidth: 280,
            }}
          >
            <div className="text-sm font-semibold text-gray-900">{n.name}</div>
            <div className="mt-1 flex items-center gap-2 text-xs">
              <span
                className="rounded-full px-2 py-0.5 font-medium"
                style={{
                  backgroundColor: color.bg,
                  color: color.text,
                  border: `1px solid ${color.border}`,
                }}
              >
                {n.concept_type}
              </span>
              {n.source_type && (
                <span className="text-gray-400">
                  from {n.source_type}
                </span>
              )}
            </div>
            {n.description && (
              <p className="mt-1.5 text-xs text-gray-600 leading-tight line-clamp-3">
                {n.description}
              </p>
            )}
            <div className="mt-1 flex items-center gap-1 text-[10px] text-gray-400">
              <span>
                Confidence:{" "}
                <span
                  className="font-semibold"
                  style={{
                    color:
                      n.confidence_score >= 0.8
                        ? "#16a34a"
                        : n.confidence_score >= 0.5
                          ? "#d97706"
                          : "#dc2626",
                  }}
                >
                  {Math.round(n.confidence_score * 100)}%
                </span>
              </span>
              <span>· {n.degree} connections</span>
            </div>
          </div>
        );
      })()}

      {/* SVG Canvas */}
      <div
        ref={containerRef}
        style={{
          width: "100%",
          height: "70vh",
          cursor: isPanning ? "grabbing" : "grab",
        }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <svg
          width="100%"
          height="100%"
          viewBox={`${-panX / zoom} ${-panY / zoom} ${(containerRef.current?.clientWidth || 1200) / zoom} ${(containerRef.current?.clientHeight || 800) / zoom}`}
        >
          <defs>
            {/* Gradient definitions for each type */}
            {Object.entries(TYPE_COLORS).map(([type, c]) => (
              <linearGradient
                key={`grad-${type}`}
                id={`grad-${type}`}
                x1="0%"
                y1="0%"
                x2="0%"
                y2="100%"
              >
                <stop offset="0%" stopColor={c.bg} />
                <stop offset="100%" stopColor={c.gradient} />
              </linearGradient>
            ))}
            {/* Arrow markers */}
            <marker
              id="arrow-mind"
              viewBox="0 0 10 6"
              refX="9"
              refY="3"
              markerWidth="7"
              markerHeight="5"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 3 L 0 6 z" fill="#94a3b8" opacity={0.6} />
            </marker>
            <marker
              id="arrow-active"
              viewBox="0 0 10 6"
              refX="9"
              refY="3"
              markerWidth="7"
              markerHeight="5"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 3 L 0 6 z" fill="#3b82f6" />
            </marker>
            {/* Drop shadow filter */}
            <filter id="node-shadow" x="-10%" y="-10%" width="120%" height="130%">
              <feDropShadow
                dx="0"
                dy="2"
                stdDeviation="3"
                floodColor="#00000012"
              />
            </filter>
            <filter id="node-shadow-hover" x="-10%" y="-10%" width="120%" height="130%">
              <feDropShadow
                dx="0"
                dy="4"
                stdDeviation="6"
                floodColor="#00000018"
              />
            </filter>
            {/* Glow for selected */}
            <filter id="selected-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feFlood floodColor="#3b82f6" floodOpacity="0.3" result="color" />
              <feComposite in="color" in2="blur" operator="in" result="glow" />
              <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background — clean white with subtle radial gradient */}
          <rect
            x={-panX / zoom - 500}
            y={-panY / zoom - 500}
            width={(containerRef.current?.clientWidth || 2000) / zoom + 1000}
            height={(containerRef.current?.clientHeight || 1500) / zoom + 1000}
            fill="#fcfcfd"
            onClick={() => {
              onSelectNode(null);
              setExpandedCluster(null);
            }}
          />

          {/* Subtle dot pattern */}
          <g opacity={0.08}>
            {Array.from({
              length: Math.ceil(canvasWidth / 60) + 1,
            }).map((_, i) =>
              Array.from({
                length: Math.ceil(canvasHeight / 60) + 1,
              }).map((_, j) => (
                <circle
                  key={`dot-${i}-${j}`}
                  cx={i * 60}
                  cy={j * 60}
                  r={1}
                  fill="#94a3b8"
                />
              ))
            )}
          </g>

          {/* === CLUSTER VIEW (Large Graphs) === */}
          {isLargeGraph && !expandedCluster && (
            <>
              {interClusterEdges.map((ice, idx) => {
                const srcC = clusters.find((c) => c.key === ice.from);
                const tgtC = clusters.find((c) => c.key === ice.to);
                if (!srcC || !tgtC) return null;
                return (
                  <g key={`ice-${idx}`}>
                    <path
                      d={curvedEdgePath(srcC.cx, srcC.cy, tgtC.cx, tgtC.cy)}
                      stroke="#94a3b8"
                      strokeWidth={Math.min(4, 1 + ice.count * 0.4)}
                      strokeDasharray="6,4"
                      opacity={0.4}
                      fill="none"
                    />
                    <g
                      transform={`translate(${(srcC.cx + tgtC.cx) / 2}, ${(srcC.cy + tgtC.cy) / 2})`}
                    >
                      <rect
                        x={-14}
                        y={-10}
                        width={28}
                        height={20}
                        rx={10}
                        fill="white"
                        stroke="#94a3b8"
                        strokeWidth={1}
                      />
                      <text
                        textAnchor="middle"
                        dy="4"
                        fontSize={10}
                        fontWeight={600}
                        fill="#64748b"
                        className="pointer-events-none"
                      >
                        {ice.count}
                      </text>
                    </g>
                  </g>
                );
              })}

              {clusters.map((cluster) => (
                <g
                  key={`cluster-${cluster.key}`}
                  className="cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation();
                    setExpandedCluster(cluster.key);
                    setZoom(1.3);
                    const cW = containerRef.current?.clientWidth || 1200;
                    const cH = containerRef.current?.clientHeight || 800;
                    setPanX((cW / 2 - cluster.cx) * 1.3);
                    setPanY((cH / 2 - cluster.cy) * 1.3);
                  }}
                >
                  <circle
                    cx={cluster.cx}
                    cy={cluster.cy}
                    r={cluster.radius}
                    fill={cluster.color.bg}
                    stroke={cluster.color.border}
                    strokeWidth={2}
                    opacity={0.5}
                  />
                  <circle
                    cx={cluster.cx}
                    cy={cluster.cy}
                    r={cluster.radius}
                    fill="transparent"
                    stroke={cluster.color.border}
                    strokeWidth={0}
                    opacity={0}
                    className="hover:opacity-100 hover:stroke-[3px]"
                    style={{ transition: "all 0.2s" }}
                  />
                  {cluster.nodes.slice(0, 30).map((n) => (
                    <circle
                      key={`dot-${n.id}`}
                      cx={n.x}
                      cy={n.y}
                      r={4}
                      fill={cluster.color.border}
                      opacity={0.35}
                    />
                  ))}
                  <text
                    x={cluster.cx}
                    y={cluster.cy - 10}
                    textAnchor="middle"
                    fontSize={15}
                    fontWeight={700}
                    fill={cluster.color.text}
                    className="pointer-events-none"
                  >
                    {cluster.key}
                  </text>
                  <text
                    x={cluster.cx}
                    y={cluster.cy + 10}
                    textAnchor="middle"
                    fontSize={12}
                    fill={cluster.color.text}
                    opacity={0.6}
                    className="pointer-events-none"
                  >
                    {cluster.nodes.length} concepts
                  </text>
                  <text
                    x={cluster.cx}
                    y={cluster.cy + 26}
                    textAnchor="middle"
                    fontSize={10}
                    fill={cluster.color.border}
                    opacity={0.8}
                    className="pointer-events-none"
                  >
                    Click to explore
                  </text>
                </g>
              ))}
            </>
          )}

          {/* === DETAIL VIEW (Mind-map or expanded cluster) === */}
          {(!isLargeGraph || expandedCluster) && (
            <>
              {/* Edges — curved bezier with gradient colors */}
              {visibleEdges.map((e) => {
                const srcBase = nodeMap.get(e.source_concept_id);
                const tgtBase = nodeMap.get(e.target_concept_id);
                if (!srcBase || !tgtBase) return null;
                const srcPos = nodePositions.get(e.source_concept_id);
                const tgtPos = nodePositions.get(e.target_concept_id);
                const src = { x: srcPos?.x ?? srcBase.x, y: srcPos?.y ?? srcBase.y };
                const tgt = { x: tgtPos?.x ?? tgtBase.x, y: tgtPos?.y ?? tgtBase.y };
                const isConnected =
                  selectedId === e.source_concept_id ||
                  selectedId === e.target_concept_id;
                const isHoverConnected =
                  hoveredNodeId === e.source_concept_id ||
                  hoveredNodeId === e.target_concept_id;
                const path = getEdgePath(e);
                if (!path) return null;

                const midX = (src.x + tgt.x) / 2;
                const midY = (src.y + tgt.y) / 2;
                const relColor = getRelColor(e.relationship_type);
                const active = isConnected || isHoverConnected;

                return (
                  <g key={`edge-${e.id}`}>
                    <path
                      d={path}
                      stroke={
                        isConnected ? "#3b82f6" : active ? relColor : "#e2e8f0"
                      }
                      strokeWidth={active ? 2.5 : 1.5}
                      fill="none"
                      opacity={active ? 1 : 0.6}
                      markerEnd={`url(#arrow-${isConnected ? "active" : "mind"})`}
                      className="cursor-pointer"
                      style={{ transition: "all 0.15s" }}
                      onClick={(ev) => {
                        ev.stopPropagation();
                        onSelectEdge?.(e);
                      }}
                    />
                    {/* Relationship label — only show when connected or hovered */}
                    {active && (
                      <g transform={`translate(${midX}, ${midY})`}>
                        <rect
                          x={-(e.relationship_type.length * 3.2 + 10)}
                          y={-10}
                          width={e.relationship_type.length * 6.4 + 20}
                          height={20}
                          rx={10}
                          fill="white"
                          stroke={isConnected ? "#93c5fd" : relColor}
                          strokeWidth={1}
                          opacity={0.95}
                        />
                        <text
                          textAnchor="middle"
                          dy="4"
                          className="pointer-events-none select-none"
                          fontSize={10}
                          fontWeight={500}
                          fill={isConnected ? "#2563eb" : "#475569"}
                        >
                          {e.relationship_type}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}

              {/* Nodes — Mind-map style pill cards */}
              {visibleNodes.map((n) => {
                const color = getTypeColor(n.concept_type);
                const isSelected = n.id === selectedId;
                const isHovered = n.id === hoveredNodeId;
                const isDragging = n.id === dragNodeId;
                const pos = nodePositions.get(n.id);
                const nx = pos?.x ?? n.x;
                const ny = pos?.y ?? n.y;
                const w = n.w;
                const h = NODE_HEIGHT;
                const displayName =
                  n.name.length > 26
                    ? n.name.substring(0, 24) + "..."
                    : n.name;

                return (
                  <g
                    key={`node-${n.id}`}
                    transform={`translate(${nx}, ${ny})`}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!isDragging) onSelectNode(n.id);
                    }}
                    onMouseDown={(e) => handleNodeDragStart(e, n.id)}
                    onMouseEnter={() => setHoveredNodeId(n.id)}
                    onMouseLeave={() => setHoveredNodeId(null)}
                    className={isDragging ? "cursor-grabbing" : "cursor-grab"}
                    style={{ transition: isDragging ? "none" : "transform 0.1s" }}
                  >
                    {/* Node card */}
                    <rect
                      x={-w / 2}
                      y={-h / 2}
                      width={w}
                      height={h}
                      rx={NODE_RX}
                      fill={`url(#grad-${color === TYPE_COLORS.Default ? "Default" : n.concept_type})`}
                      stroke={isSelected ? "#3b82f6" : color.border}
                      strokeWidth={isSelected ? 2.5 : isHovered ? 2 : 1.2}
                      filter={
                        isSelected
                          ? "url(#selected-glow)"
                          : isHovered
                            ? "url(#node-shadow-hover)"
                            : "url(#node-shadow)"
                      }
                    />

                    {/* Left color accent bar */}
                    <rect
                      x={-w / 2}
                      y={-h / 2 + 6}
                      width={4}
                      height={h - 12}
                      rx={2}
                      fill={color.border}
                      opacity={0.8}
                    />

                    {/* Source type badge */}
                    {n.source_type && (
                      <g
                        transform={`translate(${w / 2 - 14}, ${-h / 2 + 12})`}
                      >
                        <circle
                          r={7}
                          fill={
                            n.source_type === "code"
                              ? "#dcfce7"
                              : n.source_type === "document"
                                ? "#dbeafe"
                                : "#e0e7ff"
                          }
                          stroke={
                            n.source_type === "code"
                              ? "#22c55e"
                              : n.source_type === "document"
                                ? "#3b82f6"
                                : "#6366f1"
                          }
                          strokeWidth={1}
                        />
                        <text
                          textAnchor="middle"
                          dy="3.5"
                          fontSize={8}
                          fontWeight={700}
                          fill={
                            n.source_type === "code"
                              ? "#166534"
                              : n.source_type === "document"
                                ? "#1e40af"
                                : "#3730a3"
                          }
                          className="pointer-events-none"
                        >
                          {n.source_type === "code"
                            ? "C"
                            : n.source_type === "document"
                              ? "D"
                              : "B"}
                        </text>
                      </g>
                    )}

                    {/* Confidence indicator */}
                    <circle
                      cx={-w / 2 + 14}
                      cy={-h / 2 + 12}
                      r={5}
                      fill={
                        n.confidence_score >= 0.8
                          ? "#22c55e"
                          : n.confidence_score >= 0.5
                            ? "#fbbf24"
                            : "#f87171"
                      }
                      opacity={0.8}
                    />

                    {/* Name label */}
                    <text
                      textAnchor="middle"
                      dy={n.source_type ? "1" : "-1"}
                      fontSize={13}
                      fontWeight={600}
                      fill={color.text}
                      className="pointer-events-none select-none"
                    >
                      {displayName}
                    </text>

                    {/* Type sub-label */}
                    <text
                      textAnchor="middle"
                      dy={n.source_type ? "15" : "13"}
                      fontSize={10}
                      fill={color.text}
                      opacity={0.55}
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
