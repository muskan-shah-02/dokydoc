"use client";

import { useCallback, useEffect, useRef, useState } from "react";

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
  { bg: "#dbeafe", border: "#3b82f6", text: "#1d4ed8" },  // blue
  { bg: "#dcfce7", border: "#22c55e", text: "#15803d" },  // green
  { bg: "#fef3c7", border: "#f59e0b", text: "#b45309" },  // amber
  { bg: "#fce7f3", border: "#ec4899", text: "#be185d" },  // pink
  { bg: "#e0e7ff", border: "#6366f1", text: "#4338ca" },  // indigo
  { bg: "#f3e8ff", border: "#a855f7", text: "#7c3aed" },  // purple
  { bg: "#ccfbf1", border: "#14b8a6", text: "#0f766e" },  // teal
  { bg: "#ffedd5", border: "#f97316", text: "#c2410c" },  // orange
];

function getProjectColor(index: number) {
  return PROJECT_COLORS[index % PROJECT_COLORS.length];
}

// --- Force Simulation Node ---

interface SimNode extends MetaNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

// --- Component ---

export function MetaGraphView({
  data,
  onSelectMapping,
}: {
  data: MetaGraphData;
  onSelectMapping?: (mappingId: number) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [nodes, setNodes] = useState<SimNode[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);

  const allEdges = [...data.intra_edges, ...data.cross_edges];

  // Project color map
  const projectColorMap = new Map<number, { bg: string; border: string; text: string }>();
  data.projects.forEach((p, i) => {
    projectColorMap.set(p.id, getProjectColor(i));
  });

  // Unscoped gets grey
  const unscopedColor = { bg: "#f3f4f6", border: "#9ca3af", text: "#4b5563" };

  // Canvas sizing
  const nodeCount = data.nodes.length;
  const width = Math.min(2400, Math.max(1000, nodeCount * 60));
  const height = Math.min(1600, Math.max(600, nodeCount * 40));

  // Force simulation
  useEffect(() => {
    if (data.nodes.length === 0) return;

    // Group nodes by project for clustered initial placement
    const projectGroups = new Map<number | null, MetaNode[]>();
    data.nodes.forEach((n) => {
      const key = n.initiative_id;
      if (!projectGroups.has(key)) projectGroups.set(key, []);
      projectGroups.get(key)!.push(n);
    });

    const groupKeys = Array.from(projectGroups.keys());
    const clusterRadius = Math.min(width, height) * 0.3;
    const centerX = width / 2;
    const centerY = height / 2;

    const simNodes: SimNode[] = [];
    groupKeys.forEach((key, gi) => {
      const group = projectGroups.get(key)!;
      // Cluster center angle
      const angle = (gi / groupKeys.length) * 2 * Math.PI;
      const cx = centerX + Math.cos(angle) * clusterRadius;
      const cy = centerY + Math.sin(angle) * clusterRadius;

      group.forEach((n, ni) => {
        // Spread within cluster
        const innerAngle = (ni / group.length) * 2 * Math.PI;
        const spread = Math.min(150, group.length * 15);
        simNodes.push({
          ...n,
          x: cx + Math.cos(innerAngle) * spread + (Math.random() - 0.5) * 20,
          y: cy + Math.sin(innerAngle) * spread + (Math.random() - 0.5) * 20,
          vx: 0,
          vy: 0,
        });
      });
    });

    // Run simulation
    const nodeMap = new Map(simNodes.map((n) => [n.id, n]));
    const iterations = 80;

    for (let iter = 0; iter < iterations; iter++) {
      const alpha = 1 - iter / iterations;

      // Repulsion
      for (let i = 0; i < simNodes.length; i++) {
        for (let j = i + 1; j < simNodes.length; j++) {
          const a = simNodes[i];
          const b = simNodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = (800 * alpha) / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          a.vx -= fx;
          a.vy -= fy;
          b.vx += fx;
          b.vy += fy;
        }
      }

      // Attraction (edges)
      allEdges.forEach((e) => {
        const source = nodeMap.get(e.source_concept_id);
        const target = nodeMap.get(e.target_concept_id);
        if (!source || !target) return;
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const strength = e.edge_type === "cross_project" ? 0.02 : 0.05;
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
        n.vx += (centerX - n.x) * 0.005 * alpha;
        n.vy += (centerY - n.y) * 0.005 * alpha;
      });

      // Apply velocity
      simNodes.forEach((n) => {
        n.x += n.vx * 0.3;
        n.y += n.vy * 0.3;
        n.vx *= 0.85;
        n.vy *= 0.85;
        n.x = Math.max(60, Math.min(width - 60, n.x));
        n.y = Math.max(40, Math.min(height - 40, n.y));
      });
    }

    setNodes([...simNodes]);
  }, [data, width, height]);

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  if (data.nodes.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border bg-white text-sm text-gray-400">
        No concepts available for meta-graph. Create projects and extract ontology first.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 rounded-lg border bg-white px-4 py-2.5">
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
        <div className="ml-auto flex items-center gap-3 text-xs text-gray-400">
          <span className="flex items-center gap-1">
            <span className="h-px w-5 bg-gray-400" /> Intra-project
          </span>
          <span className="flex items-center gap-1">
            <span className="h-px w-5 border-t-2 border-dashed border-orange-400" /> Cross-project
          </span>
        </div>
      </div>

      {/* Graph */}
      <div className="overflow-auto rounded-lg border bg-white">
        <svg
          ref={svgRef}
          width={width}
          height={height}
          className="bg-gray-50/50"
        >
          {/* Grid */}
          <defs>
            <pattern id="metaGrid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#f0f0f0" strokeWidth="1" />
            </pattern>
            <marker id="metaArrow" viewBox="0 0 10 10" refX="30" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
            </marker>
            <marker id="metaCrossArrow" viewBox="0 0 10 10" refX="30" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#f97316" />
            </marker>
          </defs>
          <rect width={width} height={height} fill="url(#metaGrid)" />

          {/* Project cluster backgrounds */}
          {data.projects.map((p, i) => {
            const color = getProjectColor(i);
            const projectNodes = nodes.filter((n) => n.initiative_id === p.id);
            if (projectNodes.length === 0) return null;

            const minX = Math.min(...projectNodes.map((n) => n.x)) - 40;
            const minY = Math.min(...projectNodes.map((n) => n.y)) - 30;
            const maxX = Math.max(...projectNodes.map((n) => n.x)) + 40;
            const maxY = Math.max(...projectNodes.map((n) => n.y)) + 30;

            return (
              <g key={`cluster-${p.id}`}>
                <rect
                  x={minX} y={minY}
                  width={maxX - minX} height={maxY - minY}
                  rx={12}
                  fill={color.bg} fillOpacity={0.3}
                  stroke={color.border} strokeWidth={1.5}
                  strokeDasharray="6 3"
                />
                <text x={minX + 8} y={minY + 16} fontSize={11} fontWeight={600} fill={color.text}>
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
            return (
              <line
                key={`intra-${e.id}`}
                x1={source.x} y1={source.y}
                x2={target.x} y2={target.y}
                stroke="#cbd5e1" strokeWidth={1}
                markerEnd="url(#metaArrow)"
              />
            );
          })}

          {/* Cross-project edges (dashed, orange) */}
          {data.cross_edges.map((e) => {
            const source = nodeMap.get(e.source_concept_id);
            const target = nodeMap.get(e.target_concept_id);
            if (!source || !target) return null;
            const color = e.status === "confirmed" ? "#22c55e"
              : e.status === "candidate" ? "#f59e0b" : "#ef4444";
            return (
              <g key={`cross-${e.id}`}>
                <line
                  x1={source.x} y1={source.y}
                  x2={target.x} y2={target.y}
                  stroke={color} strokeWidth={2}
                  strokeDasharray="8 4"
                  markerEnd="url(#metaCrossArrow)"
                  className="cursor-pointer"
                  onClick={() => onSelectMapping?.(e.id)}
                />
                {/* Method badge at midpoint */}
                <text
                  x={(source.x + target.x) / 2}
                  y={(source.y + target.y) / 2 - 6}
                  fontSize={9} fill={color} textAnchor="middle"
                  fontWeight={600}
                >
                  {e.relationship_type?.replace(/_/g, " ")}
                </text>
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const color = node.initiative_id
              ? (projectColorMap.get(node.initiative_id) || unscopedColor)
              : unscopedColor;
            const isSelected = selectedNodeId === node.id;

            return (
              <g
                key={node.id}
                className="cursor-pointer"
                onClick={() => setSelectedNodeId(isSelected ? null : node.id)}
              >
                <circle
                  cx={node.x} cy={node.y} r={isSelected ? 18 : 14}
                  fill={color.bg}
                  stroke={isSelected ? "#2563eb" : color.border}
                  strokeWidth={isSelected ? 2.5 : 1.5}
                />
                <text
                  x={node.x} y={node.y + 26}
                  textAnchor="middle" fontSize={9} fill="#374151"
                  fontWeight={isSelected ? 600 : 400}
                >
                  {node.name.length > 18 ? node.name.slice(0, 16) + "..." : node.name}
                </text>
                {/* Type initial */}
                <text
                  x={node.x} y={node.y + 4}
                  textAnchor="middle" fontSize={10} fontWeight={700}
                  fill={color.text}
                >
                  {node.concept_type.charAt(0)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-4 rounded-lg border bg-white px-4 py-2 text-xs text-gray-500">
        <span>{data.total_nodes} concepts</span>
        <span>{data.total_intra_edges} intra-project edges</span>
        <span className="font-medium text-orange-600">{data.total_cross_edges} cross-project edges</span>
        <span>{data.projects.length} projects</span>
      </div>
    </div>
  );
}
