"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Network,
  GitFork,
  Layers,
  Activity,
  PlusCircle,
  RefreshCw,
  Sparkles,
  Loader2,
  AlertCircle,
  Download,
} from "lucide-react";
import { api } from "@/lib/api";
import { OntologyGraph } from "@/components/ontology/OntologyGraph";
import { ConceptPanel } from "@/components/ontology/ConceptPanel";
import { ConceptDetail } from "@/components/ontology/ConceptDetail";
import { ConceptDialog } from "@/components/ontology/ConceptDialog";
import { RelationshipDialog } from "@/components/ontology/RelationshipDialog";

// --- Types ---

interface Concept {
  id: number;
  name: string;
  concept_type: string;
  description: string | null;
  confidence_score: number;
  is_active: boolean;
  created_at: string;
}

interface ConceptWithRelationships extends Concept {
  outgoing_relationships: Relationship[];
  incoming_relationships: Relationship[];
}

interface Relationship {
  id: number;
  source_concept_id: number;
  target_concept_id: number;
  relationship_type: string;
  description: string | null;
  confidence_score: number;
}

interface GraphNode {
  id: number;
  name: string;
  concept_type: string;
  confidence_score: number;
}

interface GraphEdge {
  id: number;
  source_concept_id: number;
  target_concept_id: number;
  relationship_type: string;
  confidence_score: number;
}

interface OntologyStats {
  total_concepts: number;
  total_relationships: number;
  concept_types: string[];
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
}

// --- Stat Card ---

function StatCard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string;
  value: string | number;
  icon: any;
  color: string;
}) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500">{title}</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
        </div>
        <div className={`rounded-lg p-2.5 ${color}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

// --- Main Page ---

type GraphLayer = "all" | "document" | "code";

export default function OntologyDashboard() {
  // Data state
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [], total_nodes: 0, total_edges: 0 });
  const [stats, setStats] = useState<OntologyStats>({ total_concepts: 0, total_relationships: 0, concept_types: [] });
  const [selectedDetail, setSelectedDetail] = useState<ConceptWithRelationships | null>(null);

  // UI state
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [showConceptDialog, setShowConceptDialog] = useState(false);
  const [showRelDialog, setShowRelDialog] = useState(false);
  const [synonymDetecting, setSynonymDetecting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [graphLayer, setGraphLayer] = useState<GraphLayer>("all");

  // --- Data Fetching ---

  const graphEndpoint = graphLayer === "all" ? "/ontology/graph"
    : graphLayer === "document" ? "/ontology/graph/document"
    : "/ontology/graph/code";

  const fetchAll = useCallback(async () => {
    try {
      const [conceptsRes, graphRes, statsRes] = await Promise.all([
        api.get<Concept[]>("/ontology/concepts", { limit: 500 }),
        api.get<GraphData>(graphEndpoint),
        api.get<OntologyStats>("/ontology/stats"),
      ]);
      setConcepts(conceptsRes);
      setGraph(graphRes);
      setStats(statsRes);
      setError("");
    } catch (err: any) {
      console.error("Failed to fetch ontology data:", err);
      setError(err.detail || "Failed to load ontology data");
    }
  }, [graphEndpoint]);

  const fetchConceptDetail = useCallback(async (id: number) => {
    setDetailLoading(true);
    try {
      const detail = await api.get<ConceptWithRelationships>(
        `/ontology/concepts/${id}`
      );
      setSelectedDetail(detail);
    } catch (err: any) {
      console.error("Failed to fetch concept detail:", err);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    setLoading(true);
    fetchAll().finally(() => setLoading(false));
  }, [fetchAll]);

  // Load detail when selection changes
  useEffect(() => {
    if (selectedId) {
      fetchConceptDetail(selectedId);
    } else {
      setSelectedDetail(null);
    }
  }, [selectedId, fetchConceptDetail]);

  // --- Actions ---

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchAll();
    if (selectedId) await fetchConceptDetail(selectedId);
    setRefreshing(false);
  };

  const handleCreateConcept = async (data: {
    name: string;
    concept_type: string;
    description: string;
    confidence_score: number;
  }) => {
    await api.post("/ontology/concepts", data);
    await fetchAll();
  };

  const handleUpdateConcept = async (id: number, data: Partial<Concept>) => {
    await api.put(`/ontology/concepts/${id}`, data);
    await fetchAll();
    await fetchConceptDetail(id);
  };

  const handleDeleteConcept = async (id: number) => {
    await api.delete(`/ontology/concepts/${id}`);
    setSelectedId(null);
    setSelectedDetail(null);
    await fetchAll();
  };

  const handleCreateRelationship = async (data: {
    source_concept_id: number;
    target_concept_id: number;
    relationship_type: string;
    description: string;
    confidence_score: number;
  }) => {
    await api.post("/ontology/relationships", data);
    await fetchAll();
    if (selectedId) await fetchConceptDetail(selectedId);
  };

  const handleDeleteRelationship = async (relId: number) => {
    await api.delete(`/ontology/relationships/${relId}`);
    await fetchAll();
    if (selectedId) await fetchConceptDetail(selectedId);
  };

  const handleDetectSynonyms = async () => {
    setSynonymDetecting(true);
    try {
      await api.post("/ontology/synonyms/detect");
      // Poll for completion after a delay
      setTimeout(async () => {
        await fetchAll();
        if (selectedId) await fetchConceptDetail(selectedId);
        setSynonymDetecting(false);
      }, 5000);
    } catch (err: any) {
      console.error("Synonym detection failed:", err);
      setSynonymDetecting(false);
    }
  };

  const handleExportGraph = () => {
    const data = JSON.stringify(graph, null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ontology-graph-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSelectNode = (id: number | null) => {
    setSelectedId(id);
  };

  // Graph density: edges / max possible edges
  const density =
    stats.total_concepts > 1
      ? (
          (stats.total_relationships /
            (stats.total_concepts * (stats.total_concepts - 1))) *
          100
        ).toFixed(1)
      : "0.0";

  // --- Render ---

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-blue-600" />
          <p className="mt-2 text-sm text-gray-500">Loading knowledge graph...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Business Ontology
          </h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Knowledge graph extracted from your documents — review, curate, and
            connect business concepts
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw
              className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
          <button
            onClick={handleExportGraph}
            disabled={graph.nodes.length === 0}
            className="flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            Export
          </button>
          <button
            onClick={handleDetectSynonyms}
            disabled={synonymDetecting || concepts.length < 2}
            className="flex items-center gap-1.5 rounded-md border border-purple-200 bg-purple-50 px-3 py-2 text-sm font-medium text-purple-700 hover:bg-purple-100 disabled:opacity-50"
          >
            {synonymDetecting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Detect Synonyms
          </button>
          <button
            onClick={() => setShowConceptDialog(true)}
            className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <PlusCircle className="h-4 w-4" />
            Add Concept
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Stats Row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          title="Total Concepts"
          value={stats.total_concepts}
          icon={Network}
          color="bg-blue-50 text-blue-600"
        />
        <StatCard
          title="Relationships"
          value={stats.total_relationships}
          icon={GitFork}
          color="bg-green-50 text-green-600"
        />
        <StatCard
          title="Concept Types"
          value={stats.concept_types.length}
          icon={Layers}
          color="bg-amber-50 text-amber-600"
        />
        <StatCard
          title="Graph Density"
          value={`${density}%`}
          icon={Activity}
          color="bg-purple-50 text-purple-600"
        />
      </div>

      {/* Graph Layer Tabs */}
      <div className="flex items-center gap-1 rounded-lg border bg-gray-50 p-1">
        {[
          { key: "all" as GraphLayer, label: "All Concepts" },
          { key: "document" as GraphLayer, label: "Document Layer" },
          { key: "code" as GraphLayer, label: "Code Layer" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setGraphLayer(tab.key)}
            className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              graphLayer === tab.key
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
            {tab.key !== "all" && (
              <span className="ml-1.5 text-[10px] text-gray-400">
                ({tab.key === "document" ? "BRD" : "Code"})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Main 3-Column Layout */}
      <div className="flex min-h-0 flex-1 gap-3">
        {/* Left: Concept list */}
        <div className="hidden w-72 flex-shrink-0 overflow-hidden rounded-lg border bg-white lg:block">
          <ConceptPanel
            concepts={concepts}
            selectedId={selectedId}
            onSelect={handleSelectNode}
            conceptTypes={stats.concept_types}
          />
        </div>

        {/* Center: Graph */}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-lg border bg-white">
          {/* Graph legend */}
          <div className="flex items-center gap-4 border-b px-4 py-2">
            <span className="text-xs font-medium text-gray-500">Legend:</span>
            {stats.concept_types.map((type) => {
              const colors: Record<string, string> = {
                Entity: "bg-blue-200 border-blue-500",
                Process: "bg-green-200 border-green-500",
                Attribute: "bg-amber-200 border-amber-500",
                Value: "bg-purple-200 border-purple-500",
                Event: "bg-red-200 border-red-500",
                Role: "bg-teal-200 border-teal-500",
                Service: "bg-indigo-200 border-indigo-500",
              };
              return (
                <div key={type} className="flex items-center gap-1.5">
                  <span
                    className={`inline-block h-3 w-3 rounded border ${colors[type] || "bg-gray-200 border-gray-400"}`}
                  />
                  <span className="text-xs text-gray-600">{type}</span>
                </div>
              );
            })}
            {/* Confidence legend */}
            <div className="ml-auto flex items-center gap-3">
              <span className="text-xs text-gray-400">Confidence:</span>
              <div className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-green-500" />
                <span className="text-xs text-gray-500">High</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-amber-500" />
                <span className="text-xs text-gray-500">Med</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-red-500" />
                <span className="text-xs text-gray-500">Low</span>
              </div>
            </div>
          </div>

          {/* Graph canvas */}
          <div className="flex-1">
            <OntologyGraph
              nodes={graph.nodes}
              edges={graph.edges}
              selectedId={selectedId}
              onSelectNode={handleSelectNode}
            />
          </div>
        </div>

        {/* Right: Detail Panel (slides in when concept selected) */}
        {selectedId && (
          <div className="w-80 flex-shrink-0 overflow-hidden rounded-lg border bg-white">
            <ConceptDetail
              concept={selectedDetail}
              allConcepts={concepts}
              onClose={() => {
                setSelectedId(null);
                setSelectedDetail(null);
              }}
              onUpdate={handleUpdateConcept}
              onDelete={handleDeleteConcept}
              onDeleteRelationship={handleDeleteRelationship}
              onAddRelationship={() => setShowRelDialog(true)}
              loading={detailLoading}
            />
          </div>
        )}
      </div>

      {/* Mobile: Concept list as bottom sheet (simplified) */}
      <div className="block lg:hidden">
        <details className="rounded-lg border bg-white">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-gray-700">
            Browse Concepts ({concepts.length})
          </summary>
          <div className="max-h-64 overflow-y-auto border-t">
            <ConceptPanel
              concepts={concepts}
              selectedId={selectedId}
              onSelect={handleSelectNode}
              conceptTypes={stats.concept_types}
            />
          </div>
        </details>
      </div>

      {/* Dialogs */}
      <ConceptDialog
        open={showConceptDialog}
        onClose={() => setShowConceptDialog(false)}
        onCreate={handleCreateConcept}
      />

      <RelationshipDialog
        open={showRelDialog}
        onClose={() => setShowRelDialog(false)}
        concepts={concepts}
        onCreate={handleCreateRelationship}
        preselectedSourceId={selectedId}
      />
    </div>
  );
}
