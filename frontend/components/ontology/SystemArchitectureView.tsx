"use client";

import { useEffect, useRef, useState, useMemo, useCallback } from "react";

// --- Types ---

interface DomainNode {
  domain_name: string;
  file_count: number;
  concept_count: number;
  key_concepts: string[];
}

interface DomainEdge {
  source_domain: string;
  target_domain: string;
  relationship_count: number;
  relationship_types: string[];
}

interface SystemArchitectureData {
  system_nodes: DomainNode[];
  system_edges: DomainEdge[];
  synthesis_summary?: string | null;
  total_domains: number;
  repo_id: number;
  repo_name: string;
}

interface SystemArchitectureViewProps {
  data: SystemArchitectureData;
  onSelectDomain: (domainName: string) => void;
}

// --- Layout Node ---

interface LayoutNode extends DomainNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  borderColor: string;
  textColor: string;
}

// --- Color Palette ---

const DOMAIN_COLORS = [
  { bg: "#eff6ff", border: "#3b82f6", text: "#1e40af" },
  { bg: "#f0fdf4", border: "#22c55e", text: "#166534" },
  { bg: "#faf5ff", border: "#a855f7", text: "#6b21a8" },
  { bg: "#fff7ed", border: "#f97316", text: "#9a3412" },
  { bg: "#fef2f2", border: "#ef4444", text: "#991b1b" },
  { bg: "#f0fdfa", border: "#14b8a6", text: "#134e4a" },
  { bg: "#fffbeb", border: "#eab308", text: "#854d0e" },
  { bg: "#fdf2f8", border: "#ec4899", text: "#9d174d" },
  { bg: "#f8fafc", border: "#64748b", text: "#334155" },
  { bg: "#ecfeff", border: "#06b6d4", text: "#155e75" },
];

export function SystemArchitectureView({
  data,
  onSelectDomain,
}: SystemArchitectureViewProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 900, height: 600 });
  const [hoveredDomain, setHoveredDomain] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  // Pan & zoom state
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, w: 900, h: 600 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0, vbx: 0, vby: 0 });

  // Drag state
  const [dragDomain, setDragDomain] = useState<string | null>(null);
  const [nodePositions, setNodePositions] = useState<
    Map<string, { x: number; y: number }>
  >(new Map());
  const dragStartRef = useRef({ x: 0, y: 0, nodeX: 0, nodeY: 0 });

  // Measure container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) {
        setDimensions({ width, height });
        setViewBox({ x: 0, y: 0, w: width, h: height });
      }
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Force-directed layout
  const layoutNodes = useMemo(() => {
    const { system_nodes } = data;
    if (!system_nodes || system_nodes.length === 0) return [];

    const { width, height } = dimensions;
    const cx = width / 2;
    const cy = height / 2;

    // Compute radius based on concept count
    const maxConcepts = Math.max(
      ...system_nodes.map((n) => n.concept_count),
      1
    );

    const nodes: LayoutNode[] = system_nodes.map((n, i) => {
      const sizeFactor = 0.3 + 0.7 * (n.concept_count / maxConcepts);
      const radius = 40 + sizeFactor * 40; // 40-80px radius
      const angle = (2 * Math.PI * i) / system_nodes.length;
      const spread = Math.min(width, height) * 0.3;
      const color = DOMAIN_COLORS[i % DOMAIN_COLORS.length];
      return {
        ...n,
        x: cx + Math.cos(angle) * spread,
        y: cy + Math.sin(angle) * spread,
        vx: 0,
        vy: 0,
        radius,
        color: color.bg,
        borderColor: color.border,
        textColor: color.text,
      };
    });

    // Build edge lookup for attraction
    const edgeLookup = new Map<string, Set<string>>();
    for (const e of data.system_edges || []) {
      if (!edgeLookup.has(e.source_domain))
        edgeLookup.set(e.source_domain, new Set());
      if (!edgeLookup.has(e.target_domain))
        edgeLookup.set(e.target_domain, new Set());
      edgeLookup.get(e.source_domain)!.add(e.target_domain);
      edgeLookup.get(e.target_domain)!.add(e.source_domain);
    }

    // Run force simulation
    const iterations = 80;
    for (let iter = 0; iter < iterations; iter++) {
      const alpha = 1 - iter / iterations;
      const repulsion = 8000 * alpha;
      const attraction = 0.005 * alpha;
      const centerPull = 0.02 * alpha;

      // Repulsion between all pairs
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x;
          const dy = nodes[j].y - nodes[i].y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const minDist = nodes[i].radius + nodes[j].radius + 30;
          const force = repulsion / (dist * dist);
          const nx = dx / dist;
          const ny = dy / dist;

          nodes[i].vx -= nx * force;
          nodes[i].vy -= ny * force;
          nodes[j].vx += nx * force;
          nodes[j].vy += ny * force;

          // Hard overlap prevention
          if (dist < minDist) {
            const push = (minDist - dist) * 0.5;
            nodes[i].x -= nx * push;
            nodes[i].y -= ny * push;
            nodes[j].x += nx * push;
            nodes[j].y += ny * push;
          }
        }
      }

      // Attraction along edges
      for (const e of data.system_edges || []) {
        const src = nodes.find((n) => n.domain_name === e.source_domain);
        const tgt = nodes.find((n) => n.domain_name === e.target_domain);
        if (!src || !tgt) continue;
        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 1) continue;
        const idealDist = src.radius + tgt.radius + 80;
        const force = (dist - idealDist) * attraction;
        const nx = dx / dist;
        const ny = dy / dist;
        src.vx += nx * force;
        src.vy += ny * force;
        tgt.vx -= nx * force;
        tgt.vy -= ny * force;
      }

      // Center gravity
      for (const n of nodes) {
        n.vx += (cx - n.x) * centerPull;
        n.vy += (cy - n.y) * centerPull;
      }

      // Apply velocities with damping
      for (const n of nodes) {
        n.vx *= 0.6;
        n.vy *= 0.6;
        n.x += n.vx;
        n.y += n.vy;

        // Keep within bounds (with padding)
        const pad = n.radius + 10;
        n.x = Math.max(pad, Math.min(width - pad, n.x));
        n.y = Math.max(pad, Math.min(height - pad, n.y));
      }
    }

    return nodes;
  }, [data, dimensions]);

  // Get node position (with drag override)
  const getNodePos = useCallback(
    (domainName: string): { x: number; y: number } => {
      const override = nodePositions.get(domainName);
      if (override) return override;
      const node = layoutNodes.find((n) => n.domain_name === domainName);
      return node ? { x: node.x, y: node.y } : { x: 0, y: 0 };
    },
    [layoutNodes, nodePositions]
  );

  // Find node by domain name
  const getNode = useCallback(
    (domainName: string) =>
      layoutNodes.find((n) => n.domain_name === domainName),
    [layoutNodes]
  );

  // --- Mouse Handlers ---

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (dragDomain) return;
      setIsPanning(true);
      panStart.current = {
        x: e.clientX,
        y: e.clientY,
        vbx: viewBox.x,
        vby: viewBox.y,
      };
    },
    [dragDomain, viewBox]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      // Node drag takes priority
      if (dragDomain) {
        const svg = svgRef.current;
        if (!svg) return;
        const rect = svg.getBoundingClientRect();
        const scaleX = viewBox.w / rect.width;
        const scaleY = viewBox.h / rect.height;
        const dx = (e.clientX - dragStartRef.current.x) * scaleX;
        const dy = (e.clientY - dragStartRef.current.y) * scaleY;
        setNodePositions((prev) => {
          const next = new Map(prev);
          next.set(dragDomain, {
            x: dragStartRef.current.nodeX + dx,
            y: dragStartRef.current.nodeY + dy,
          });
          return next;
        });
        return;
      }

      if (isPanning) {
        const scaleX = viewBox.w / dimensions.width;
        const scaleY = viewBox.h / dimensions.height;
        const dx = (e.clientX - panStart.current.x) * scaleX;
        const dy = (e.clientY - panStart.current.y) * scaleY;
        setViewBox((v) => ({
          ...v,
          x: panStart.current.vbx - dx,
          y: panStart.current.vby - dy,
        }));
      }
    },
    [dragDomain, isPanning, viewBox, dimensions]
  );

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
    setDragDomain(null);
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
      const nw = viewBox.w * factor;
      const nh = viewBox.h * factor;
      setViewBox({
        x: mx - (mx - viewBox.x) * factor,
        y: my - (my - viewBox.y) * factor,
        w: nw,
        h: nh,
      });
    },
    [viewBox]
  );

  const handleNodeDragStart = useCallback(
    (domainName: string, e: React.MouseEvent) => {
      e.stopPropagation();
      setDragDomain(domainName);
      const pos = getNodePos(domainName);
      dragStartRef.current = {
        x: e.clientX,
        y: e.clientY,
        nodeX: pos.x,
        nodeY: pos.y,
      };
    },
    [getNodePos]
  );

  // --- Edge Path ---

  const getEdgePath = useCallback(
    (edge: DomainEdge) => {
      const srcPos = getNodePos(edge.source_domain);
      const tgtPos = getNodePos(edge.target_domain);
      const srcNode = getNode(edge.source_domain);
      const tgtNode = getNode(edge.target_domain);
      if (!srcNode || !tgtNode) return { path: "", midX: 0, midY: 0 };

      const dx = tgtPos.x - srcPos.x;
      const dy = tgtPos.y - srcPos.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const nx = dx / dist;
      const ny = dy / dist;

      // Start/end at circle border
      const sx = srcPos.x + nx * srcNode.radius;
      const sy = srcPos.y + ny * srcNode.radius;
      const ex = tgtPos.x - nx * tgtNode.radius;
      const ey = tgtPos.y - ny * tgtNode.radius;

      // Slight curve for aesthetics
      const curveMag = dist * 0.1;
      const cpx = (sx + ex) / 2 + ny * curveMag;
      const cpy = (sy + ey) / 2 - nx * curveMag;

      return {
        path: `M ${sx} ${sy} Q ${cpx} ${cpy} ${ex} ${ey}`,
        midX: cpx,
        midY: cpy,
      };
    },
    [getNodePos, getNode]
  );

  // --- Hovered node data ---

  const hoveredNode = useMemo(() => {
    if (!hoveredDomain) return null;
    return layoutNodes.find((n) => n.domain_name === hoveredDomain) ?? null;
  }, [hoveredDomain, layoutNodes]);

  // Edge weight styling
  const maxEdgeWeight = useMemo(() => {
    if (!data.system_edges || data.system_edges.length === 0) return 1;
    return Math.max(...data.system_edges.map((e) => e.relationship_count));
  }, [data.system_edges]);

  if (!data.system_nodes || data.system_nodes.length === 0) {
    return (
      <div className="flex h-60 flex-col items-center justify-center text-gray-400">
        <svg
          className="mb-2 h-10 w-10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <circle cx="12" cy="12" r="3" />
          <circle cx="4" cy="6" r="2" />
          <circle cx="20" cy="6" r="2" />
          <circle cx="4" cy="18" r="2" />
          <circle cx="20" cy="18" r="2" />
          <line x1="6" y1="7" x2="9" y2="10" />
          <line x1="18" y1="7" x2="15" y2="10" />
          <line x1="6" y1="17" x2="9" y2="14" />
          <line x1="18" y1="17" x2="15" y2="14" />
        </svg>
        <p className="text-sm">No system architecture data available</p>
        <p className="mt-1 text-xs">
          Analyze repository code to build the system graph
        </p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative h-full w-full select-none">
      <svg
        ref={svgRef}
        viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`}
        className="h-full w-full"
        style={{ cursor: dragDomain ? "grabbing" : isPanning ? "grabbing" : "grab" }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        <defs>
          {/* Glow filter for hovered nodes */}
          <filter id="sav-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feFlood floodColor="#818cf8" floodOpacity="0.3" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Arrow marker */}
          <marker
            id="sav-arrow"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
          </marker>
        </defs>

        {/* Edges */}
        {(data.system_edges || []).map((edge, i) => {
          const { path, midX, midY } = getEdgePath(edge);
          if (!path) return null;
          const weight = edge.relationship_count;
          const normalizedWeight = weight / maxEdgeWeight;
          const strokeWidth = 1.5 + normalizedWeight * 3;
          const isHighlighted =
            hoveredDomain === edge.source_domain ||
            hoveredDomain === edge.target_domain;

          return (
            <g key={`edge-${i}`}>
              <path
                d={path}
                fill="none"
                stroke={isHighlighted ? "#6366f1" : "#cbd5e1"}
                strokeWidth={strokeWidth}
                strokeOpacity={isHighlighted ? 0.8 : 0.5}
                markerEnd="url(#sav-arrow)"
              />
              {/* Edge weight badge */}
              <g transform={`translate(${midX}, ${midY})`}>
                <rect
                  x={-14}
                  y={-10}
                  width={28}
                  height={20}
                  rx={10}
                  fill={isHighlighted ? "#6366f1" : "#f1f5f9"}
                  stroke={isHighlighted ? "#6366f1" : "#e2e8f0"}
                  strokeWidth={1}
                />
                <text
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill={isHighlighted ? "#ffffff" : "#64748b"}
                  fontSize={10}
                  fontWeight={600}
                >
                  {weight}
                </text>
              </g>
            </g>
          );
        })}

        {/* Domain Bubbles */}
        {layoutNodes.map((node) => {
          const pos = getNodePos(node.domain_name);
          const isHovered = hoveredDomain === node.domain_name;
          const isDragging = dragDomain === node.domain_name;

          // Truncate domain name for display
          const displayName =
            node.domain_name.length > 18
              ? node.domain_name.slice(0, 16) + "..."
              : node.domain_name;

          // Show top 3 key concepts
          const topConcepts = node.key_concepts.slice(0, 3);

          return (
            <g
              key={node.domain_name}
              transform={`translate(${pos.x}, ${pos.y})`}
              style={{
                cursor: isDragging ? "grabbing" : "pointer",
              }}
              filter={isHovered ? "url(#sav-glow)" : undefined}
              onMouseDown={(e) => handleNodeDragStart(node.domain_name, e)}
              onMouseEnter={(e) => {
                setHoveredDomain(node.domain_name);
                setTooltipPos({ x: e.clientX, y: e.clientY });
              }}
              onMouseLeave={() => setHoveredDomain(null)}
              onClick={(e) => {
                // Only trigger click if we haven't dragged
                if (!isDragging) {
                  e.stopPropagation();
                  onSelectDomain(node.domain_name);
                }
              }}
            >
              {/* Outer circle — border */}
              <circle
                r={node.radius + 2}
                fill={node.borderColor}
                opacity={isHovered ? 0.9 : 0.7}
              />
              {/* Inner circle — background */}
              <circle r={node.radius} fill={node.color} />
              {/* Subtle radial gradient overlay */}
              <circle
                r={node.radius}
                fill="url(#sav-grad)"
                opacity={0.3}
              />

              {/* Domain name */}
              <text
                textAnchor="middle"
                dominantBaseline="central"
                y={-node.radius * 0.25}
                fill={node.textColor}
                fontSize={node.radius > 55 ? 12 : 10}
                fontWeight={700}
              >
                {displayName}
              </text>

              {/* File count badge */}
              <text
                textAnchor="middle"
                dominantBaseline="central"
                y={node.radius * 0.05}
                fill={node.textColor}
                fontSize={9}
                opacity={0.7}
              >
                {node.file_count} files · {node.concept_count} concepts
              </text>

              {/* Key concepts (small text) */}
              {topConcepts.map((concept, ci) => {
                const truncated =
                  concept.length > 16
                    ? concept.slice(0, 14) + ".."
                    : concept;
                return (
                  <text
                    key={ci}
                    textAnchor="middle"
                    dominantBaseline="central"
                    y={node.radius * 0.3 + ci * 12}
                    fill={node.textColor}
                    fontSize={8}
                    opacity={0.55}
                  >
                    {truncated}
                  </text>
                );
              })}
            </g>
          );
        })}

        {/* Radial gradient definition (for bubble shine) */}
        <defs>
          <radialGradient id="sav-grad" cx="35%" cy="35%" r="65%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity={0.6} />
            <stop offset="100%" stopColor="#ffffff" stopOpacity={0} />
          </radialGradient>
        </defs>
      </svg>

      {/* Tooltip */}
      {hoveredNode && hoveredDomain && (
        <div
          className="pointer-events-none absolute z-50 w-56 rounded-lg border border-gray-200 bg-white p-3 shadow-lg"
          style={{
            left: Math.min(
              tooltipPos.x - (containerRef.current?.getBoundingClientRect().left ?? 0) + 16,
              dimensions.width - 240
            ),
            top: Math.min(
              tooltipPos.y - (containerRef.current?.getBoundingClientRect().top ?? 0) - 10,
              dimensions.height - 160
            ),
          }}
        >
          <p className="text-sm font-semibold text-gray-900">
            {hoveredNode.domain_name}
          </p>
          <div className="mt-1.5 space-y-1 text-xs text-gray-500">
            <p>
              <span className="font-medium text-gray-700">
                {hoveredNode.file_count}
              </span>{" "}
              files ·{" "}
              <span className="font-medium text-gray-700">
                {hoveredNode.concept_count}
              </span>{" "}
              concepts
            </p>
            {hoveredNode.key_concepts.length > 0 && (
              <div>
                <p className="mt-1 font-medium text-gray-600">Key concepts:</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {hoveredNode.key_concepts.slice(0, 5).map((c, i) => (
                    <span
                      key={i}
                      className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600"
                    >
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {/* Connected domains */}
            {(() => {
              const connections = (data.system_edges || []).filter(
                (e) =>
                  e.source_domain === hoveredDomain ||
                  e.target_domain === hoveredDomain
              );
              if (connections.length === 0) return null;
              return (
                <div className="mt-1">
                  <p className="font-medium text-gray-600">
                    {connections.length} cross-domain connection
                    {connections.length > 1 ? "s" : ""}
                  </p>
                </div>
              );
            })()}
          </div>
          <p className="mt-2 text-[10px] text-gray-400">
            Click to explore · Drag to reposition
          </p>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-3 left-3 rounded-md border bg-white/90 px-3 py-2 text-[10px] text-gray-500 backdrop-blur-sm">
        <p className="font-semibold text-gray-700">System Architecture</p>
        <p className="mt-0.5">Bubble size = concept count</p>
        <p>Edge badge = relationship count</p>
        <p className="mt-1 text-gray-400">
          Scroll to zoom · Drag background to pan · Drag node to reposition
        </p>
      </div>

      {/* Synthesis summary */}
      {data.synthesis_summary && (
        <div className="absolute right-3 top-3 max-w-xs rounded-md border bg-white/90 px-3 py-2 text-xs text-gray-600 backdrop-blur-sm">
          <p className="font-semibold text-gray-700">Repository Summary</p>
          <p className="mt-1 line-clamp-3">{data.synthesis_summary}</p>
        </div>
      )}
    </div>
  );
}
