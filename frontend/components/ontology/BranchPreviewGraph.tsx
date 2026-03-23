"use client";

import { useEffect, useRef, useState, useMemo } from "react";

// --- Types ---

interface PreviewNode {
  id: number;
  name: string;
  concept_type: string;
  source_type?: string;
  confidence_score: number;
  diff_status: string; // "unchanged" | "added" | "modified" | "removed"
}

interface PreviewEdge {
  id: number;
  source_concept_id: number;
  target_concept_id: number;
  relationship_type: string;
  confidence_score: number;
  diff_status: string;
}

interface SimNode extends PreviewNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface BranchPreviewGraphProps {
  nodes: PreviewNode[];
  edges: PreviewEdge[];
  branch: string;
  commitHash: string;
  changedFiles: string[];
  selectedId: number | null;
  onSelectNode: (id: number | null) => void;
}

// --- Color Maps ---

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

// Diff status overrides (take priority over TYPE_COLORS for border)
const DIFF_COLORS: Record<string, { border: string; badge: string; opacity: number; glow: boolean }> = {
  unchanged: { border: "#9ca3af", badge: "",  opacity: 0.6, glow: false },
  added:     { border: "#22c55e", badge: "+", opacity: 1.0, glow: true },
  modified:  { border: "#eab308", badge: "~", opacity: 1.0, glow: false },
  removed:   { border: "#ef4444", badge: "-", opacity: 0.4, glow: false },
};

function getNodeColors(node: PreviewNode) {
  const typeColor = TYPE_COLORS[node.concept_type] || TYPE_COLORS.Default;
  const diffColor = DIFF_COLORS[node.diff_status] || DIFF_COLORS.unchanged;
  return { ...typeColor, borderOverride: diffColor.border, ...diffColor };
}

// --- Force-Directed Layout ---

function forceLayout(nodes: SimNode[], edges: PreviewEdge[], iterations: number = 200) {
  const W = 900, H = 600;
  const k = Math.sqrt((W * H) / Math.max(nodes.length, 1)) * 0.8;

  for (let iter = 0; iter < iterations; iter++) {
    const temp = 1 - iter / iterations;

    // Repulsion
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const force = (k * k) / dist * temp * 0.5;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        nodes[i].vx += fx; nodes[i].vy += fy;
        nodes[j].vx -= fx; nodes[j].vy -= fy;
      }
    }

    // Attraction (edges)
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    for (const edge of edges) {
      const s = nodeMap.get(edge.source_concept_id);
      const t = nodeMap.get(edge.target_concept_id);
      if (!s || !t) continue;
      const dx = t.x - s.x;
      const dy = t.y - s.y;
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const force = (dist / k) * temp * 0.3;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      s.vx += fx; s.vy += fy;
      t.vx -= fx; t.vy -= fy;
    }

    // Center gravity
    for (const node of nodes) {
      const dx = W / 2 - node.x;
      const dy = H / 2 - node.y;
      node.vx += dx * 0.001;
      node.vy += dy * 0.001;
    }

    // Apply velocities with damping
    for (const node of nodes) {
      node.x += node.vx * 0.5;
      node.y += node.vy * 0.5;
      node.vx *= 0.8;
      node.vy *= 0.8;
      // Keep in bounds
      node.x = Math.max(60, Math.min(W - 60, node.x));
      node.y = Math.max(40, Math.min(H - 40, node.y));
    }
  }

  return nodes;
}

// --- Component ---

export function BranchPreviewGraph({
  nodes,
  edges,
  branch,
  commitHash,
  changedFiles,
  selectedId,
  onSelectNode,
}: BranchPreviewGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const W = 900, H = 600;

  const simNodes = useMemo(() => {
    if (!nodes.length) return [];
    const initial: SimNode[] = nodes.map((n, i) => ({
      ...n,
      x: W / 2 + (Math.random() - 0.5) * 400,
      y: H / 2 + (Math.random() - 0.5) * 300,
      vx: 0, vy: 0,
    }));
    return forceLayout(initial, edges, 250);
  }, [nodes, edges]);

  const nodeMap = useMemo(() => new Map(simNodes.map((n) => [n.id, n])), [simNodes]);

  // Count by diff status
  const diffCounts = useMemo(() => {
    const counts = { unchanged: 0, added: 0, modified: 0, removed: 0 };
    for (const n of nodes) {
      const key = n.diff_status as keyof typeof counts;
      if (key in counts) counts[key]++;
    }
    return counts;
  }, [nodes]);

  if (!nodes.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border bg-white text-sm text-gray-400">
        No preview data for this branch
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-white shadow-sm">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b px-4 py-2.5">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-gray-900">Branch Preview</span>
          <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700">
            {branch}
          </span>
          {commitHash && (
            <span className="font-mono text-xs text-gray-400">{commitHash}</span>
          )}
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-gray-300" /> Unchanged ({diffCounts.unchanged})
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-green-500" /> Added ({diffCounts.added})
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-yellow-500" /> Modified ({diffCounts.modified})
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-red-500" /> Removed ({diffCounts.removed})
          </span>
        </div>
      </div>

      {/* SVG Graph */}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ minHeight: 500 }}
        onClick={() => onSelectNode(null)}
      >
        <defs>
          {/* Glow filter for added nodes */}
          <filter id="glow-added">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feFlood floodColor="#22c55e" floodOpacity="0.4" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="shadow" />
            <feMerge>
              <feMergeNode in="shadow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <marker id="arrow-preview" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <path d="M0,0 L8,3 L0,6" fill="#9ca3af" />
          </marker>
          <marker id="arrow-added" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <path d="M0,0 L8,3 L0,6" fill="#22c55e" />
          </marker>
        </defs>

        {/* Edges */}
        {edges.map((edge) => {
          const s = nodeMap.get(edge.source_concept_id);
          const t = nodeMap.get(edge.target_concept_id);
          if (!s || !t) return null;
          const isAdded = edge.diff_status === "added";
          return (
            <g key={`edge-${edge.id}`}>
              <line
                x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                stroke={isAdded ? "#22c55e" : "#d1d5db"}
                strokeWidth={isAdded ? 2 : 1}
                strokeDasharray={isAdded ? "6,3" : "none"}
                markerEnd={isAdded ? "url(#arrow-added)" : "url(#arrow-preview)"}
                opacity={isAdded ? 0.9 : 0.5}
              />
              {/* Edge label */}
              <text
                x={(s.x + t.x) / 2}
                y={(s.y + t.y) / 2 - 4}
                fontSize={8}
                fill={isAdded ? "#22c55e" : "#9ca3af"}
                textAnchor="middle"
              >
                {edge.relationship_type}
              </text>
            </g>
          );
        })}

        {/* Nodes */}
        {simNodes.map((node) => {
          const colors = getNodeColors(node);
          const isSelected = selectedId === node.id;
          const radius = isSelected ? 32 : 26;
          const isRemoved = node.diff_status === "removed";

          return (
            <g
              key={`node-${node.id}`}
              transform={`translate(${node.x}, ${node.y})`}
              onClick={(e) => {
                e.stopPropagation();
                onSelectNode(node.id);
              }}
              style={{ cursor: "pointer" }}
              opacity={colors.opacity}
              filter={colors.glow ? "url(#glow-added)" : undefined}
            >
              {/* Node circle */}
              <circle
                r={radius}
                fill={colors.bg}
                stroke={colors.borderOverride}
                strokeWidth={isSelected ? 3 : 2}
              />

              {/* Node name */}
              <text
                y={1}
                fontSize={10}
                fill={colors.text}
                textAnchor="middle"
                dominantBaseline="middle"
                style={{
                  textDecoration: isRemoved ? "line-through" : "none",
                  fontWeight: isSelected ? 600 : 400,
                }}
              >
                {node.name.length > 12 ? node.name.slice(0, 11) + "..." : node.name}
              </text>

              {/* Diff badge */}
              {colors.badge && (
                <g transform={`translate(${radius - 6}, ${-radius + 6})`}>
                  <circle r={8} fill={colors.borderOverride} />
                  <text
                    fontSize={11}
                    fill="white"
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontWeight={700}
                  >
                    {colors.badge}
                  </text>
                </g>
              )}

              {/* Type label below */}
              <text
                y={radius + 12}
                fontSize={8}
                fill="#9ca3af"
                textAnchor="middle"
              >
                {node.concept_type}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Changed files footer */}
      {changedFiles.length > 0 && (
        <div className="border-t px-4 py-2.5">
          <p className="mb-1 text-xs font-medium text-gray-500">
            Changed files ({changedFiles.length}):
          </p>
          <div className="flex flex-wrap gap-1.5">
            {changedFiles.map((file) => (
              <span
                key={file}
                className="rounded bg-gray-100 px-2 py-0.5 font-mono text-[10px] text-gray-600"
              >
                {file}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
