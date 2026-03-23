"use client";

import { useCallback, useEffect, useState } from "react";
import {
  GitBranch,
  FileText,
  Code,
  Link as LinkIcon,
  RefreshCw,
  Loader2,
  AlertCircle,
  Play,
  BarChart3,
  Network,
} from "lucide-react";
import { api } from "@/lib/api";
import { CrossGraphView } from "@/components/ontology/CrossGraphView";
import { MappingReviewPanel } from "@/components/ontology/MappingReviewPanel";
import { GapAnalysis } from "@/components/ontology/GapAnalysis";

// --- Types ---

interface ConceptNode {
  id: number;
  name: string;
  concept_type: string;
  source_type: string;
  confidence_score: number;
}

interface GraphData {
  nodes: ConceptNode[];
  edges: any[];
  total_nodes: number;
  total_edges: number;
}

interface MappingItem {
  id: number;
  document_concept_id: number;
  code_concept_id: number;
  document_concept_name: string;
  document_concept_type: string;
  code_concept_name: string;
  code_concept_type: string;
  mapping_method: string;
  confidence_score: number;
  status: string;
  relationship_type: string;
  ai_reasoning: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface MappingStats {
  document_concepts: number;
  code_concepts: number;
  total_mappings: number;
  confirmed_mappings: number;
  candidate_mappings: number;
  contradictions: number;
}

interface MismatchData {
  gaps: Array<{ id: number; name: string; concept_type: string }>;
  undocumented: Array<{ id: number; name: string; concept_type: string }>;
  contradictions: Array<{
    id: number;
    document_concept_name: string;
    code_concept_name: string;
    relationship_type: string;
  }>;
  total_gaps: number;
  total_undocumented: number;
  total_contradictions: number;
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

// --- Tab options ---

type TabKey = "mappings" | "gap-analysis";

// --- Main Page ---

export default function VisualArchitecturePage() {
  // Data
  const [docGraph, setDocGraph] = useState<GraphData>({ nodes: [], edges: [], total_nodes: 0, total_edges: 0 });
  const [codeGraph, setCodeGraph] = useState<GraphData>({ nodes: [], edges: [], total_nodes: 0, total_edges: 0 });
  const [mappings, setMappings] = useState<MappingItem[]>([]);
  const [mappingStats, setMappingStats] = useState<MappingStats | null>(null);
  const [mismatches, setMismatches] = useState<MismatchData | null>(null);

  // UI
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<TabKey>("mappings");
  const [selectedMappingId, setSelectedMappingId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [refreshing, setRefreshing] = useState(false);
  const [runningPipeline, setRunningPipeline] = useState(false);
  const [mismatchLoading, setMismatchLoading] = useState(false);

  // --- Data Fetching ---

  const fetchGraphs = useCallback(async () => {
    try {
      const [docRes, codeRes] = await Promise.all([
        api.get<GraphData>("/ontology/graph/document"),
        api.get<GraphData>("/ontology/graph/code"),
      ]);
      setDocGraph(docRes);
      setCodeGraph(codeRes);
    } catch (err: any) {
      console.error("Failed to fetch graphs:", err);
    }
  }, []);

  const fetchMappings = useCallback(async () => {
    try {
      const params: Record<string, string> = {};
      if (statusFilter !== "all") params.status = statusFilter;
      const res = await api.get<MappingItem[]>("/ontology/mappings", params);
      setMappings(res);
    } catch (err: any) {
      console.error("Failed to fetch mappings:", err);
    }
  }, [statusFilter]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get<MappingStats>("/ontology/mappings/stats");
      setMappingStats(res);
    } catch (err: any) {
      console.error("Failed to fetch mapping stats:", err);
    }
  }, []);

  const fetchMismatches = useCallback(async () => {
    setMismatchLoading(true);
    try {
      const res = await api.get<MismatchData>("/ontology/mappings/mismatches");
      setMismatches(res);
    } catch (err: any) {
      console.error("Failed to fetch mismatches:", err);
    } finally {
      setMismatchLoading(false);
    }
  }, []);

  const fetchAll = useCallback(async () => {
    try {
      await Promise.all([fetchGraphs(), fetchMappings(), fetchStats()]);
      setError("");
    } catch (err: any) {
      setError(err.detail || "Failed to load data");
    }
  }, [fetchGraphs, fetchMappings, fetchStats]);

  // Initial load
  useEffect(() => {
    setLoading(true);
    fetchAll().finally(() => setLoading(false));
  }, [fetchAll]);

  // Refetch mappings when filter changes
  useEffect(() => {
    fetchMappings();
  }, [fetchMappings]);

  // Fetch mismatches when gap analysis tab is selected
  useEffect(() => {
    if (activeTab === "gap-analysis" && !mismatches) {
      fetchMismatches();
    }
  }, [activeTab, mismatches, fetchMismatches]);

  // --- Actions ---

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchAll();
    if (activeTab === "gap-analysis") await fetchMismatches();
    setRefreshing(false);
  };

  const handleRunPipeline = async () => {
    setRunningPipeline(true);
    try {
      await api.post("/ontology/mappings/run");
      // Poll for completion after delay
      setTimeout(async () => {
        await fetchAll();
        await fetchMismatches();
        setRunningPipeline(false);
      }, 5000);
    } catch (err: any) {
      console.error("Pipeline run failed:", err);
      setRunningPipeline(false);
    }
  };

  const handleConfirmMapping = async (id: number) => {
    await api.put(`/ontology/mappings/${id}/confirm`);
    await fetchMappings();
    await fetchStats();
  };

  const handleRejectMapping = async (id: number) => {
    await api.put(`/ontology/mappings/${id}/reject`);
    await fetchMappings();
    await fetchStats();
  };

  const filteredMappings = mappings;

  // --- Render ---

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-blue-600" />
          <p className="mt-2 text-sm text-gray-500">Loading cross-graph view...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-purple-100 p-2">
              <GitBranch className="h-6 w-6 text-purple-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Visual Architecture</h1>
              <p className="mt-0.5 text-sm text-gray-500">
                Document &harr; Code concept mapping with gap analysis
              </p>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            onClick={handleRunPipeline}
            disabled={runningPipeline}
            className="flex items-center gap-1.5 rounded-md bg-purple-600 px-3 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
          >
            {runningPipeline ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Run Mapping Pipeline
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
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <StatCard
          title="Doc Concepts"
          value={mappingStats?.document_concepts ?? docGraph.total_nodes}
          icon={FileText}
          color="bg-blue-50 text-blue-600"
        />
        <StatCard
          title="Code Concepts"
          value={mappingStats?.code_concepts ?? codeGraph.total_nodes}
          icon={Code}
          color="bg-green-50 text-green-600"
        />
        <StatCard
          title="Total Mappings"
          value={mappingStats?.total_mappings ?? 0}
          icon={LinkIcon}
          color="bg-purple-50 text-purple-600"
        />
        <StatCard
          title="Confirmed"
          value={mappingStats?.confirmed_mappings ?? 0}
          icon={Network}
          color="bg-emerald-50 text-emerald-600"
        />
        <StatCard
          title="Candidates"
          value={mappingStats?.candidate_mappings ?? 0}
          icon={BarChart3}
          color="bg-amber-50 text-amber-600"
        />
        <StatCard
          title="Contradictions"
          value={mappingStats?.contradictions ?? 0}
          icon={AlertCircle}
          color="bg-red-50 text-red-600"
        />
      </div>

      {/* Tabs */}
      <div className="flex border-b">
        {[
          { key: "mappings" as TabKey, label: "Cross-Graph Mappings", icon: LinkIcon },
          { key: "gap-analysis" as TabKey, label: "Gap Analysis", icon: BarChart3 },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "border-purple-600 text-purple-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "mappings" && (
        <div className="flex min-h-0 flex-1 gap-3">
          {/* Center: Cross-Graph View */}
          <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-lg border bg-white">
            {/* Legend */}
            <div className="flex flex-wrap items-center gap-4 border-b px-4 py-2">
              <span className="text-xs font-medium text-gray-500">Status:</span>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-6 rounded-full bg-green-500" />
                <span className="text-xs text-gray-600">Confirmed</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-6 rounded-full border border-dashed border-amber-500" />
                <span className="text-xs text-gray-600">Candidate</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-6 rounded-full bg-red-500" />
                <span className="text-xs text-gray-600">Rejected</span>
              </div>
              <div className="ml-auto flex items-center gap-3 text-xs text-gray-400">
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-green-500" /> Exact</span>
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-500" /> Fuzzy</span>
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-purple-500" /> AI</span>
              </div>
            </div>

            {/* Graph canvas */}
            <div className="flex-1">
              <CrossGraphView
                documentNodes={docGraph.nodes}
                codeNodes={codeGraph.nodes}
                mappings={filteredMappings}
                selectedMappingId={selectedMappingId}
                onSelectMapping={setSelectedMappingId}
              />
            </div>
          </div>

          {/* Right: Mapping Review Panel */}
          <div className="hidden w-80 flex-shrink-0 overflow-hidden rounded-lg border bg-white lg:block">
            <MappingReviewPanel
              mappings={filteredMappings}
              selectedId={selectedMappingId}
              onSelect={setSelectedMappingId}
              onConfirm={handleConfirmMapping}
              onReject={handleRejectMapping}
              statusFilter={statusFilter}
              onStatusFilterChange={setStatusFilter}
            />
          </div>
        </div>
      )}

      {activeTab === "gap-analysis" && (
        <div className="flex-1 overflow-y-auto">
          <GapAnalysis data={mismatches} loading={mismatchLoading} />
        </div>
      )}
    </div>
  );
}
