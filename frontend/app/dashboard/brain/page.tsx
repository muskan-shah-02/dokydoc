"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BrainCircuit,
  Network,
  FileText,
  GitBranch,
  Loader2,
  AlertCircle,
  ArrowLeft,
  Layers,
} from "lucide-react";
import { api } from "@/lib/api";
import { MetaGraphView } from "@/components/ontology/MetaGraphView";
import { OntologyGraph } from "@/components/ontology/OntologyGraph";
import {
  BrainBreadcrumb,
  BreadcrumbSegment,
} from "@/components/ontology/BrainBreadcrumb";
import { SystemArchitectureView } from "@/components/ontology/SystemArchitectureView";

// --- Types ---

interface BrainStats {
  total_projects: number;
  total_concepts: number;
  total_mappings: number;
  coverage_pct: number;
}

interface MetaGraphData {
  nodes: any[];
  cross_edges: any[];
  total_concepts: number;
  total_relationships: number;
  total_cross_edges: number;
  projects: { id: number; name: string }[];
}

interface DrillState {
  level: 5 | 3 | 2 | 1;
  projectId?: number;
  projectName?: string;
  repoId?: number;
  domainName?: string;
  componentId?: number;
  componentName?: string;
}

export default function BrainDashboardPage() {
  const router = useRouter();

  const [metaData, setMetaData] = useState<MetaGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [stats, setStats] = useState<BrainStats>({
    total_projects: 0,
    total_concepts: 0,
    total_mappings: 0,
    coverage_pct: 0,
  });

  // Drill-down state
  const [drill, setDrill] = useState<DrillState>({ level: 5 });
  const [drillData, setDrillData] = useState<any>(null);
  const [drillLoading, setDrillLoading] = useState(false);

  // Fetch top-level meta-graph (Level 5)
  const fetchMetaGraph = useCallback(async () => {
    setLoading(true);
    try {
      // Auto-backfill initiative_ids for any unscoped concepts (fire-and-forget)
      api.post("/ontology/backfill-initiative-ids", {}).catch(() => {});

      const [meta, brainRes] = await Promise.all([
        api.get<MetaGraphData>("/ontology/graph/meta"),
        api.get<any>("/ontology/graph/brain"),
      ]);
      setMetaData(meta);
      setStats({
        total_projects: meta.projects?.length ?? 0,
        total_concepts: meta.total_concepts ?? 0,
        total_mappings: meta.total_relationships ?? 0,
        coverage_pct: brainRes.coverage_pct ?? 0,
      });
      setError("");
    } catch (err: any) {
      setError(err.detail || "Failed to load brain data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetaGraph();
  }, [fetchMetaGraph]);

  // Drill into a level
  const drillInto = useCallback(
    async (next: DrillState) => {
      setDrill(next);
      if (next.level === 5) {
        setDrillData(null);
        return;
      }
      setDrillLoading(true);
      try {
        let data: any;
        if (next.level === 3 && next.repoId) {
          data = await api.get<any>(
            `/ontology/graph/system/${next.repoId}`
          );
        } else if (next.level === 2 && next.repoId) {
          data = await api.get<any>(
            `/ontology/graph/domain/${next.repoId}`
          );
        } else if (next.level === 1 && next.componentId) {
          // Use pre-built graph version (fast) with fallback to live query
          try {
            const versionData = await api.get<any>(
              `/ontology/graph/component/${next.componentId}/current`
            );
            data = versionData.graph_data;
          } catch {
            data = await api.get<any>(
              `/ontology/graph/component/${next.componentId}`
            );
          }
        }
        setDrillData(data);
      } catch {
        setDrillData(null);
      } finally {
        setDrillLoading(false);
      }
    },
    []
  );

  // Build breadcrumb segments
  const buildBreadcrumb = (): BreadcrumbSegment[] => {
    const segs: BreadcrumbSegment[] = [
      {
        label: "Brain",
        level: 5,
        onClick: () => drillInto({ level: 5 }),
      },
    ];
    if (drill.level <= 3 && drill.projectName) {
      segs.push({
        label: drill.projectName,
        level: 3,
        onClick: () =>
          drillInto({
            level: 3,
            projectId: drill.projectId,
            projectName: drill.projectName,
            repoId: drill.repoId,
          }),
      });
    }
    if (drill.level <= 2 && drill.domainName) {
      segs.push({
        label: drill.domainName,
        level: 2,
        onClick: () =>
          drillInto({
            level: 2,
            projectId: drill.projectId,
            projectName: drill.projectName,
            repoId: drill.repoId,
            domainName: drill.domainName,
          }),
      });
    }
    if (drill.level === 1 && drill.componentName) {
      segs.push({ label: drill.componentName, level: 1 });
    }
    return segs;
  };

  // --- Render ---

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
        <p className="ml-2 text-sm text-gray-500">
          Loading organizational brain...
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50/50 p-4 lg:p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-purple-50 p-3">
              <BrainCircuit className="h-6 w-6 text-purple-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Organizational Brain
              </h1>
              <p className="mt-0.5 text-sm text-gray-500">
                5-level knowledge graph hierarchy — drill from organization
                down to individual files
              </p>
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {/* Stats Cards */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500">Projects</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">
                {stats.total_projects}
              </p>
            </div>
            <div className="rounded-lg bg-blue-50 p-2.5">
              <Layers className="h-5 w-5 text-blue-600" />
            </div>
          </div>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500">Concepts</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">
                {stats.total_concepts}
              </p>
            </div>
            <div className="rounded-lg bg-purple-50 p-2.5">
              <Network className="h-5 w-5 text-purple-600" />
            </div>
          </div>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500">
                Relationships
              </p>
              <p className="mt-1 text-2xl font-bold text-gray-900">
                {stats.total_mappings}
              </p>
            </div>
            <div className="rounded-lg bg-amber-50 p-2.5">
              <GitBranch className="h-5 w-5 text-amber-600" />
            </div>
          </div>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500">Coverage</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">
                {stats.coverage_pct}%
              </p>
            </div>
            <div className="rounded-lg bg-green-50 p-2.5">
              <FileText className="h-5 w-5 text-green-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Breadcrumb */}
      {drill.level < 5 && (
        <div className="mb-4 rounded-lg border bg-white px-4 py-2.5">
          <BrainBreadcrumb segments={buildBreadcrumb()} />
        </div>
      )}

      {/* Main Graph Area */}
      <div className="rounded-lg border bg-white">
        {drill.level === 5 ? (
          /* Level 5: Meta Graph — all projects */
          <div>
            <div className="border-b px-5 py-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                <BrainCircuit className="h-4 w-4 text-purple-500" />
                Level 5 — Organizational Overview
              </h2>
              <p className="mt-0.5 text-xs text-gray-400">
                Click a project cluster to drill into its system architecture
              </p>
            </div>
            {metaData && metaData.nodes.length > 0 ? (
              <div style={{ height: "600px" }}>
                <MetaGraphView
                  data={metaData}
                  onSelectMapping={(nodeId) => {
                    // Each node is a project — drill into Level 3 (System Architecture)
                    const node = metaData.nodes.find((n: any) => n.id === nodeId);
                    if (!node || node.id === -1 || !node.initiative_id) return; // Skip unscoped
                    drillInto({
                      level: 3,
                      projectId: node.initiative_id,
                      projectName: node.name || `Project ${node.initiative_id}`,
                      repoId: node.repo_id ?? node.initiative_id,
                    });
                  }}
                />
              </div>
            ) : (
              <div className="flex h-80 flex-col items-center justify-center text-gray-400">
                <BrainCircuit className="mb-2 h-10 w-10" />
                <p className="text-sm">No projects analyzed yet</p>
                <p className="mt-1 text-xs">
                  Create a project, link documents and repositories, then
                  analyze them
                </p>
                <button
                  onClick={() => router.push("/dashboard/projects")}
                  className="mt-3 rounded-md bg-purple-50 px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100"
                >
                  Go to Projects
                </button>
              </div>
            )}
          </div>
        ) : drillLoading ? (
          <div className="flex h-80 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-purple-600" />
            <p className="ml-2 text-sm text-gray-500">Loading level {drill.level} data...</p>
          </div>
        ) : drill.level === 3 ? (
          /* Level 3: System Architecture */
          <div>
            <div className="border-b px-5 py-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                <Layers className="h-4 w-4 text-blue-500" />
                Level 3 — System Architecture: {drill.projectName}
              </h2>
              <p className="mt-0.5 text-xs text-gray-400">
                Domain modules and their relationships. Click a domain to drill
                into file-level view.
              </p>
            </div>
            {drill.projectId && drill.projectId > 0 && (
              <button
                onClick={() => router.push(`/dashboard/projects/${drill.projectId}`)}
                className="mr-5 mt-2 rounded-md bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
              >
                View Alignment (L4)
              </button>
            )}
            {drillData?.system_nodes?.length > 0 ? (
              <div style={{ height: "550px" }}>
                <SystemArchitectureView
                  data={drillData}
                  onSelectDomain={(domainName) =>
                    drillInto({
                      ...drill,
                      level: 2,
                      domainName,
                    })
                  }
                />
              </div>
            ) : (
              <div className="flex h-60 flex-col items-center justify-center text-gray-400">
                <Network className="mb-2 h-8 w-8" />
                <p className="text-sm">No system data available</p>
              </div>
            )}
          </div>
        ) : drill.level === 2 ? (
          /* Level 2: Domain Cluster — OntologyGraph view */
          <div>
            <div className="border-b px-5 py-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                <Network className="h-4 w-4 text-green-500" />
                Level 2 — Domain: {drill.domainName}
              </h2>
            </div>
            {drillData?.domains?.length > 0 ? (
              <div style={{ height: "500px" }}>
                {(() => {
                  const domain = drillData.domains.find(
                    (d: any) => d.name === drill.domainName
                  );
                  if (!domain) return null;
                  return (
                    <OntologyGraph
                      nodes={domain.nodes.map((n: any) => ({
                        id: n.id,
                        name: n.name,
                        concept_type: n.concept_type,
                        confidence_score: n.confidence_score,
                        description: n.description,
                        source_component_id: n.source_component_id,
                      }))}
                      edges={domain.edges.map((e: any) => ({
                        id: e.id,
                        source_concept_id: e.source_concept_id,
                        target_concept_id: e.target_concept_id,
                        relationship_type: e.relationship_type,
                        confidence_score: e.confidence_score,
                      }))}
                      selectedId={null}
                      onSelectNode={(id) => {
                        if (!id) return;
                        // Find the node — if it has a source_component_id, drill to file level
                        const node = domain.nodes.find((n: any) => n.id === id);
                        if (node?.source_component_id) {
                          drillInto({
                            ...drill,
                            level: 1,
                            componentId: node.source_component_id,
                            componentName: node.name,
                          });
                        }
                      }}
                    />
                  );
                })()}
              </div>
            ) : (
              <div className="flex h-60 items-center justify-center text-gray-400">
                <p className="text-sm">No domain data available</p>
              </div>
            )}
          </div>
        ) : (
          /* Level 1: File subgraph */
          <div>
            <div className="border-b px-5 py-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                <FileText className="h-4 w-4 text-orange-500" />
                Level 1 — File: {drill.componentName}
              </h2>
              {drill.componentId && (
                <button
                  onClick={() => router.push(`/dashboard/code/${drill.componentId}`)}
                  className="rounded-md bg-orange-50 px-3 py-1.5 text-xs font-medium text-orange-700 hover:bg-orange-100"
                >
                  View Full Details
                </button>
              )}
            </div>
            {drillData?.nodes?.length > 0 ? (
              <div style={{ height: "500px" }}>
                <OntologyGraph
                  nodes={drillData.nodes.map((n: any) => ({
                    id: n.id ?? n.name,
                    name: n.name,
                    concept_type: n.type ?? n.concept_type,
                    confidence_score: n.confidence ?? n.confidence_score ?? 0.7,
                    description: n.description,
                    source_type: n.source_type,
                  }))}
                  edges={(drillData.edges || []).map((e: any) => ({
                    id: e.id ?? `${e.source}-${e.target}`,
                    source_concept_id: e.source ?? e.source_concept_id,
                    target_concept_id: e.target ?? e.target_concept_id,
                    relationship_type: e.type ?? e.relationship_type,
                    confidence_score: e.confidence ?? e.confidence_score ?? 0.7,
                  }))}
                  selectedId={null}
                  onSelectNode={() => {}}
                />
              </div>
            ) : (
              <div className="flex h-60 items-center justify-center text-gray-400">
                <p className="text-sm">No concepts for this file</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Level guide */}
      <div className="mt-6 rounded-lg border bg-white p-5">
        <h3 className="text-sm font-semibold text-gray-900">
          Brain Hierarchy Levels
        </h3>
        <div className="mt-3 grid gap-2 md:grid-cols-5">
          {[
            {
              level: 5,
              label: "Organization",
              desc: "All projects as clusters",
              color: "bg-purple-50 text-purple-700",
            },
            {
              level: 4,
              label: "Alignment",
              desc: "Doc ↔ Code mapping",
              color: "bg-indigo-50 text-indigo-700",
            },
            {
              level: 3,
              label: "System",
              desc: "Repo architecture",
              color: "bg-blue-50 text-blue-700",
            },
            {
              level: 2,
              label: "Domain",
              desc: "Module clusters",
              color: "bg-green-50 text-green-700",
            },
            {
              level: 1,
              label: "File",
              desc: "Per-file subgraph",
              color: "bg-orange-50 text-orange-700",
            },
          ].map((l) => (
            <button
              key={l.level}
              onClick={() => {
                if (l.level === 5) {
                  drillInto({ level: 5 });
                } else if (l.level === 4 && drill.projectId) {
                  router.push(`/dashboard/projects/${drill.projectId}`);
                } else if (l.level === 3 && drill.projectId) {
                  drillInto({
                    level: 3,
                    projectId: drill.projectId,
                    projectName: drill.projectName,
                    repoId: drill.repoId,
                  });
                } else if (l.level === 2 && drill.repoId) {
                  drillInto({
                    ...drill,
                    level: 2,
                    domainName: drill.domainName,
                  });
                }
                // L1 requires a specific componentId, so no generic click action
              }}
              className={`rounded-lg p-3 text-left transition-all hover:ring-2 hover:ring-offset-1 ${l.color} ${
                drill.level === l.level
                  ? "ring-2 ring-offset-1 font-semibold"
                  : "opacity-80 hover:opacity-100"
              }`}
            >
              <p className="text-xs font-semibold">L{l.level}</p>
              <p className="text-sm font-medium">{l.label}</p>
              <p className="mt-0.5 text-[10px] opacity-70">{l.desc}</p>
              {drill.level === l.level && (
                <p className="mt-1 text-[10px] font-semibold opacity-90">← Current</p>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
