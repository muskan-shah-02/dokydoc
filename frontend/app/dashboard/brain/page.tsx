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
  CheckCircle2,
  XCircle,
  HelpCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { MetaGraphView } from "@/components/ontology/MetaGraphView";
import { OntologyGraph } from "@/components/ontology/OntologyGraph";
import {
  BrainBreadcrumb,
  BreadcrumbSegment,
} from "@/components/ontology/BrainBreadcrumb";
import { SystemArchitectureView } from "@/components/ontology/SystemArchitectureView";
import { CrossProjectMappingPanel } from "@/components/ontology/CrossProjectMappingPanel";
import SemanticSearch from "@/components/ontology/SemanticSearch";
import { MermaidDiagram } from "@/components/ontology/MermaidDiagram";

// --- Types ---

interface BrainStats {
  total_projects: number;
  total_concepts: number;
  total_mappings: number;
  coverage_pct: number;
}

interface MappingQuality {
  total_mappings: number;
  confirmed_mappings: number;
  candidate_mappings: number;
  contradictions: number;
  document_concepts: number;
  code_concepts: number;
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
  const [mappingQuality, setMappingQuality] = useState<MappingQuality | null>(null);
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

  // L3 diagram view
  type DiagramType = "graph" | "architecture" | "dataflow" | "er";
  const [l3View, setL3View] = useState<DiagramType>("graph");
  const [mermaidData, setMermaidData] = useState<{ syntax: string; diagram_type: string } | null>(null);
  const [mermaidLoading, setMermaidLoading] = useState(false);

  // L2 concept filter + detail panel
  const [l2TypeFilter, setL2TypeFilter] = useState<string>("ALL");
  const [selectedConceptId, setSelectedConceptId] = useState<number | null>(null);
  const [conceptDetail, setConceptDetail] = useState<any>(null);
  const [conceptDetailLoading, setConceptDetailLoading] = useState(false);

  // Fetch top-level meta-graph (Level 5)
  const fetchMetaGraph = useCallback(async () => {
    setLoading(true);
    try {
      // Auto-backfill initiative_ids for any unscoped concepts (fire-and-forget)
      api.post("/ontology/backfill-initiative-ids", {}).catch(() => {});

      const [meta, brainRes, qualityRes] = await Promise.all([
        api.get<MetaGraphData>("/ontology/graph/meta"),
        api.get<any>("/ontology/graph/brain"),
        api.get<MappingQuality>("/ontology/mappings/stats").catch(() => null),
      ]);
      setMappingQuality(qualityRes);
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

  // Fetch Mermaid diagram when L3 diagram type changes
  const loadMermaid = useCallback(async (repoId: number, type: string) => {
    setMermaidLoading(true);
    setMermaidData(null);
    try {
      const data = await api.get<any>(`/ontology/graph/system/${repoId}/mermaid?diagram_type=${type}`);
      setMermaidData(data);
    } catch {
      setMermaidData({ syntax: "graph TD\n    A[Failed to generate diagram]", diagram_type: type });
    } finally {
      setMermaidLoading(false);
    }
  }, []);

  useEffect(() => {
    if (drill.level === 3 && drill.repoId && l3View !== "graph") {
      loadMermaid(drill.repoId, l3View === "architecture" ? "architecture" : l3View === "dataflow" ? "dataflow" : "er");
    }
  }, [l3View, drill.level, drill.repoId, loadMermaid]);

  const loadConceptDetail = useCallback(async (conceptId: number) => {
    setConceptDetailLoading(true);
    setConceptDetail(null);
    try {
      const data = await api.get<any>(`/ontology/concepts/${conceptId}`);
      setConceptDetail(data);
    } catch {
      setConceptDetail(null);
    } finally {
      setConceptDetailLoading(false);
    }
  }, []);

  // Reset L2 state when drilling changes
  useEffect(() => {
    setL2TypeFilter("ALL");
    setSelectedConceptId(null);
    setConceptDetail(null);
  }, [drill.domainName]);

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
        let data: any = null;

        if (next.level === 3) {
          if (next.repoId) {
            data = await api.get<any>(`/ontology/graph/system/${next.repoId}`);
          } else if (next.projectId) {
            // Project has no repo yet — fetch assets to check
            const assets = await api.get<any[]>(`/initiatives/${next.projectId}/assets`).catch(() => []);
            const repoAsset = (Array.isArray(assets) ? assets : []).find(
              (a: any) => a.asset_type === "REPOSITORY" && a.is_active
            );
            if (repoAsset) {
              setDrill({ ...next, repoId: repoAsset.asset_id });
              data = await api.get<any>(`/ontology/graph/system/${repoAsset.asset_id}`);
            } else {
              data = { system_nodes: [], _no_repo: true };
            }
          }
        } else if (next.level === 2 && next.repoId) {
          data = await api.get<any>(`/ontology/graph/domain/${next.repoId}`);
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
          {/* Semantic Search */}
          <SemanticSearch
            className="w-80"
            onSelectConcept={(concept) => {
              // Navigate to concept's graph context
              if (concept.source_type === "code" || concept.source_type === "both") {
                // Could drill into code graph - for now show alert
                console.log("Selected concept:", concept);
              }
            }}
          />
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

      {/* Mapping Quality Summary (Level 5 only) */}
      {drill.level === 5 && mappingQuality && mappingQuality.total_mappings > 0 && (
        <div className="mb-6 rounded-lg border bg-white p-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Mapping Quality</h3>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              <div>
                <p className="text-xs text-gray-500">Confirmed</p>
                <p className="text-sm font-bold text-green-700">{mappingQuality.confirmed_mappings}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <HelpCircle className="h-4 w-4 text-amber-500" />
              <div>
                <p className="text-xs text-gray-500">Candidates</p>
                <p className="text-sm font-bold text-amber-700">{mappingQuality.candidate_mappings}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-500" />
              <div>
                <p className="text-xs text-gray-500">Contradictions</p>
                <p className="text-sm font-bold text-red-700">{mappingQuality.contradictions}</p>
              </div>
            </div>
            <div>
              <p className="text-xs text-gray-500">Confirmation Rate</p>
              <div className="mt-1 flex items-center gap-2">
                <div className="h-2 flex-1 rounded-full bg-gray-200">
                  <div
                    className="h-full rounded-full bg-green-500"
                    style={{ width: `${mappingQuality.total_mappings > 0 ? (mappingQuality.confirmed_mappings / mappingQuality.total_mappings) * 100 : 0}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-gray-600">
                  {mappingQuality.total_mappings > 0 ? Math.round((mappingQuality.confirmed_mappings / mappingQuality.total_mappings) * 100) : 0}%
                </span>
              </div>
            </div>
            <div>
              <p className="text-xs text-gray-500">Doc / Code Concepts</p>
              <p className="text-sm font-medium text-gray-700">
                {mappingQuality.document_concepts} / {mappingQuality.code_concepts}
              </p>
            </div>
          </div>
        </div>
      )}

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
            <div className="border-b px-5 py-3 flex items-start justify-between gap-4">
              <div>
                <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                  <Layers className="h-4 w-4 text-blue-500" />
                  Level 3 — System Architecture: {drill.projectName}
                </h2>
                <p className="mt-0.5 text-xs text-gray-400">
                  Domain modules and their relationships. Click a domain to drill into file-level view.
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* View type selector */}
                <div className="flex rounded-lg border bg-gray-50 p-0.5 gap-0.5">
                  {([
                    { key: "graph", label: "Graph" },
                    { key: "architecture", label: "Architecture" },
                    { key: "dataflow", label: "Data Flow" },
                    { key: "er", label: "ER Diagram" },
                  ] as { key: DiagramType; label: string }[]).map((v) => (
                    <button
                      key={v.key}
                      onClick={() => setL3View(v.key)}
                      className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                        l3View === v.key
                          ? "bg-white text-blue-700 shadow-sm"
                          : "text-gray-500 hover:text-gray-700"
                      }`}
                    >
                      {v.label}
                    </button>
                  ))}
                </div>
                {drill.projectId && drill.projectId > 0 && (
                  <button
                    onClick={() => router.push(`/dashboard/projects/${drill.projectId}`)}
                    className="rounded-md bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                  >
                    View Alignment (L4)
                  </button>
                )}
              </div>
            </div>
            {drillData?.system_nodes?.length > 0 ? (
              l3View === "graph" ? (
                <div style={{ height: "550px" }}>
                  <SystemArchitectureView
                    data={drillData}
                    onSelectDomain={(domainName) =>
                      drillInto({ ...drill, level: 2, domainName })
                    }
                  />
                </div>
              ) : (
                <div className="p-4">
                  {mermaidLoading ? (
                    <div className="flex h-48 items-center justify-center gap-2 text-gray-400">
                      <Loader2 className="h-5 w-5 animate-spin" />
                      <span className="text-sm">Generating diagram...</span>
                    </div>
                  ) : mermaidData ? (
                    <MermaidDiagram
                      syntax={mermaidData.mermaid_syntax}
                      title={`${drill.projectName} — ${l3View === "architecture" ? "Architecture" : l3View === "dataflow" ? "Data Flow" : "ER"} Diagram`}
                    />
                  ) : (
                    <div className="flex h-48 items-center justify-center text-gray-400 text-sm">
                      Select a diagram type above
                    </div>
                  )}
                </div>
              )
            ) : drillData?._no_repo ? (
              <div className="flex h-60 flex-col items-center justify-center text-gray-400 gap-3">
                <Network className="h-8 w-8" />
                <p className="text-sm font-medium text-gray-600">No repositories connected to this project</p>
                <p className="text-xs text-gray-400">Go to the project page and link a repository to build the system architecture</p>
                {drill.projectId && (
                  <button
                    onClick={() => router.push(`/dashboard/projects/${drill.projectId}`)}
                    className="rounded-md bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
                  >
                    Connect a Repository
                  </button>
                )}
              </div>
            ) : (
              <div className="flex h-60 flex-col items-center justify-center text-gray-400">
                <Network className="mb-2 h-8 w-8" />
                <p className="text-sm">No system data available</p>
                <p className="text-xs mt-1">Analyze a connected repository to build the architecture graph</p>
              </div>
            )}
          </div>
        ) : drill.level === 2 ? (
          /* Level 2: Domain Cluster — filtered by domain name */
          (() => {
            // Nodes for this domain (drillData.nodes has a "domain" field)
            const allDomainNodes: any[] = (drillData?.nodes ?? []).filter(
              (n: any) => n.domain === drill.domainName
            );
            const domainNodeIds = new Set(allDomainNodes.map((n: any) => n.id));

            // Edges between these nodes only
            const domainEdges: any[] = (drillData?.edges ?? []).filter(
              (e: any) => domainNodeIds.has(e.source_concept_id) && domainNodeIds.has(e.target_concept_id)
            );

            // Available concept types for tabs
            const typeSet = new Set(allDomainNodes.map((n: any) => n.concept_type).filter(Boolean));
            const types = ["ALL", ...Array.from(typeSet).sort()];

            // Filtered nodes by type
            const visibleNodes = l2TypeFilter === "ALL"
              ? allDomainNodes
              : allDomainNodes.filter((n: any) => n.concept_type === l2TypeFilter);
            const visibleNodeIds = new Set(visibleNodes.map((n: any) => n.id));
            const visibleEdges = domainEdges.filter(
              (e: any) => visibleNodeIds.has(e.source_concept_id) && visibleNodeIds.has(e.target_concept_id)
            );

            const selectedNode = allDomainNodes.find((n: any) => n.id === selectedConceptId);

            return (
              <div>
                <div className="border-b px-5 py-3 flex items-center justify-between">
                  <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                    <Network className="h-4 w-4 text-green-500" />
                    Level 2 — Domain: {drill.domainName}
                    <span className="ml-1 rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-semibold text-green-700">
                      {allDomainNodes.length} concepts
                    </span>
                  </h2>
                  {/* Type filter tabs */}
                  {types.length > 1 && (
                    <div className="flex gap-1 flex-wrap">
                      {types.map((t) => (
                        <button
                          key={t}
                          onClick={() => setL2TypeFilter(t)}
                          className={`rounded-full px-2.5 py-0.5 text-[10px] font-medium transition-all ${
                            l2TypeFilter === t
                              ? "bg-green-600 text-white"
                              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                          }`}
                        >
                          {t === "ALL" ? `All (${allDomainNodes.length})` : t}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {allDomainNodes.length > 0 ? (
                  <div className="flex" style={{ height: "520px" }}>
                    {/* Graph */}
                    <div className={selectedConceptId ? "flex-1" : "w-full"} style={{ minWidth: 0 }}>
                      <OntologyGraph
                        nodes={visibleNodes.map((n: any) => ({
                          id: n.id,
                          name: n.name,
                          concept_type: n.concept_type,
                          confidence_score: n.confidence_score,
                          description: n.description,
                          source_component_id: n.source_component_id,
                        }))}
                        edges={visibleEdges.map((e: any) => ({
                          id: e.id,
                          source_concept_id: e.source_concept_id,
                          target_concept_id: e.target_concept_id,
                          relationship_type: e.relationship_type,
                          confidence_score: e.confidence_score,
                        }))}
                        selectedId={selectedConceptId}
                        onSelectNode={(id) => {
                          if (!id) {
                            setSelectedConceptId(null);
                            setConceptDetail(null);
                            return;
                          }
                          const node = allDomainNodes.find((n: any) => n.id === id);
                          setSelectedConceptId(id as number);
                          loadConceptDetail(id as number);
                          // Double-click or source_component_id → L1
                          if (node?.source_component_id && id === selectedConceptId) {
                            drillInto({ ...drill, level: 1, componentId: node.source_component_id, componentName: node.name });
                          }
                        }}
                      />
                    </div>

                    {/* Concept Detail Panel */}
                    {selectedConceptId && (
                      <div className="w-72 border-l bg-gray-50 flex flex-col overflow-y-auto flex-shrink-0">
                        <div className="border-b bg-white px-4 py-3 flex items-center justify-between">
                          <p className="text-xs font-semibold text-gray-700">Concept Detail</p>
                          <button
                            onClick={() => { setSelectedConceptId(null); setConceptDetail(null); }}
                            className="text-gray-400 hover:text-gray-600 text-lg leading-none"
                          >×</button>
                        </div>
                        {conceptDetailLoading ? (
                          <div className="flex flex-1 items-center justify-center gap-2 text-gray-400">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span className="text-xs">Loading...</span>
                          </div>
                        ) : conceptDetail ? (
                          <div className="p-4 space-y-4 text-xs">
                            <div>
                              <p className="font-bold text-gray-900 text-sm">{conceptDetail.name}</p>
                              <span className="mt-1 inline-block rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-medium text-green-700">
                                {conceptDetail.concept_type}
                              </span>
                              {conceptDetail.source_type && (
                                <span className="ml-1 inline-block rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                                  {conceptDetail.source_type}
                                </span>
                              )}
                            </div>
                            {conceptDetail.description && (
                              <div>
                                <p className="font-semibold text-gray-500 uppercase tracking-wide text-[9px] mb-1">Description</p>
                                <p className="text-gray-700 leading-relaxed">{conceptDetail.description}</p>
                              </div>
                            )}
                            {conceptDetail.confidence_score != null && (
                              <div>
                                <p className="font-semibold text-gray-500 uppercase tracking-wide text-[9px] mb-1">Confidence</p>
                                <div className="flex items-center gap-2">
                                  <div className="flex-1 h-1.5 rounded-full bg-gray-200">
                                    <div className="h-full rounded-full bg-green-500" style={{ width: `${(conceptDetail.confidence_score * 100).toFixed(0)}%` }} />
                                  </div>
                                  <span className="text-gray-600">{(conceptDetail.confidence_score * 100).toFixed(0)}%</span>
                                </div>
                              </div>
                            )}
                            {/* Outgoing relationships */}
                            {conceptDetail.outgoing_relationships?.length > 0 && (
                              <div>
                                <p className="font-semibold text-gray-500 uppercase tracking-wide text-[9px] mb-2">
                                  Relationships ({conceptDetail.outgoing_relationships.length})
                                </p>
                                <div className="space-y-1">
                                  {conceptDetail.outgoing_relationships.slice(0, 8).map((r: any) => (
                                    <div key={r.id} className="flex items-center gap-1.5 rounded bg-white border px-2 py-1">
                                      <span className="text-gray-400">→</span>
                                      <span className="text-[10px] text-indigo-600 font-medium">{r.relationship_type}</span>
                                      <span className="text-gray-600 truncate">{r.target_concept?.name ?? `#${r.target_concept_id}`}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {/* Source file drill-down */}
                            {selectedNode?.source_component_id && (
                              <div className="pt-2 border-t">
                                <button
                                  onClick={() => drillInto({ ...drill, level: 1, componentId: selectedNode.source_component_id, componentName: selectedNode.name })}
                                  className="w-full rounded-md bg-orange-50 px-3 py-2 text-xs font-medium text-orange-700 hover:bg-orange-100"
                                >
                                  Drill into File (L1) →
                                </button>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="flex flex-1 items-center justify-center text-gray-400 text-xs">
                            Select a concept node
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex h-60 items-center justify-center text-gray-400">
                    <p className="text-sm">No concepts in this domain yet</p>
                  </div>
                )}
              </div>
            );
          })()
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
          ].map((l) => {
            const isActive = drill.level === l.level;
            // Determine if this level is navigable
            const canNavigate =
              l.level === 5 ||
              (l.level === 4 && !!drill.projectId) ||
              (l.level === 3 && !!drill.projectId) ||
              (l.level === 2 && !!drill.repoId && !!drill.projectId) ||
              (l.level === 1 && !!drill.componentId);

            const hint =
              l.level === 5
                ? null
                : l.level === 4
                ? !drill.projectId ? "Click a project node first" : null
                : l.level === 3
                ? !drill.projectId ? "Click a project node first" : null
                : l.level === 2
                ? !drill.repoId ? "Drill into L3 first" : null
                : !drill.componentId ? "Drill into L2 first" : null;

            return (
              <button
                key={l.level}
                title={hint ?? undefined}
                disabled={!canNavigate}
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
                    drillInto({ ...drill, level: 2, domainName: drill.domainName });
                  }
                }}
                className={`rounded-lg p-3 text-left transition-all ${l.color} ${
                  isActive
                    ? "ring-2 ring-offset-1 font-semibold"
                    : canNavigate
                    ? "opacity-80 hover:opacity-100 hover:ring-2 hover:ring-offset-1 cursor-pointer"
                    : "opacity-40 cursor-not-allowed"
                }`}
              >
                <p className="text-xs font-semibold">L{l.level}</p>
                <p className="text-sm font-medium">{l.label}</p>
                <p className="mt-0.5 text-[10px] opacity-70">{l.desc}</p>
                {isActive && (
                  <p className="mt-1 text-[10px] font-semibold opacity-90">← Current</p>
                )}
                {!canNavigate && hint && (
                  <p className="mt-1 text-[10px] opacity-60 italic">{hint}</p>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Cross-Project Mappings */}
      {metaData && metaData.projects.length >= 2 && (
        <div className="mt-6">
          <CrossProjectMappingPanel
            projects={metaData.projects}
          />
        </div>
      )}
    </div>
  );
}
