"use client";

export const dynamic = "force-dynamic";

import { useCallback, useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  GitBranch,
  Loader2,
  AlertCircle,
  Plus,
  Minus,
  RefreshCw,
  ArrowRight,
  ArrowLeftRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { OntologyGraph } from "@/components/ontology/OntologyGraph";

// --- Types ---

interface GraphVersion {
  id: number;
  entity_type: string;
  entity_id: number;
  version_number: number;
  graph_data: any;
  metadata: any;
  created_at: string;
}

interface DiffResult {
  added_nodes: any[];
  removed_nodes: any[];
  changed_nodes: any[];
  added_edges: any[];
  removed_edges: any[];
  summary: {
    total_added: number;
    total_removed: number;
    total_changed: number;
  };
}

// --- Component ---

function BranchComparisonContent() {
  const searchParams = useSearchParams();
  const componentId = searchParams.get("component_id");

  const [versions, setVersions] = useState<GraphVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Selected versions for comparison
  const [versionA, setVersionA] = useState<number | "">("");
  const [versionB, setVersionB] = useState<number | "">("");

  // Diff state
  const [diff, setDiff] = useState<DiffResult | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [graphA, setGraphA] = useState<any>(null);
  const [graphB, setGraphB] = useState<any>(null);

  // Fetch available versions
  const fetchVersions = useCallback(async () => {
    if (!componentId) return;
    setLoading(true);
    try {
      const res = await api.get<GraphVersion[]>(
        `/ontology/graph/component/${componentId}/versions`
      );
      setVersions(res);
      // Auto-select latest two
      if (res.length >= 2) {
        setVersionA(res[1].version_number);
        setVersionB(res[0].version_number);
      }
    } catch (err: any) {
      setError(err.detail || "Failed to load graph versions");
    } finally {
      setLoading(false);
    }
  }, [componentId]);

  useEffect(() => {
    fetchVersions();
  }, [fetchVersions]);

  // Run diff comparison
  const runComparison = useCallback(async () => {
    if (!componentId || versionA === "" || versionB === "") return;
    setDiffLoading(true);
    setDiff(null);

    try {
      const [diffRes, verAData, verBData] = await Promise.all([
        api.get<DiffResult>(
          `/ontology/graph/component/${componentId}/diff?v1=${versionA}&v2=${versionB}`
        ),
        api.get<any>(
          `/ontology/graph/component/${componentId}/versions`
        ).then((versions: GraphVersion[]) =>
          versions.find((v) => v.version_number === Number(versionA))
        ),
        api.get<any>(
          `/ontology/graph/component/${componentId}/versions`
        ).then((versions: GraphVersion[]) =>
          versions.find((v) => v.version_number === Number(versionB))
        ),
      ]);
      setDiff(diffRes);
      setGraphA(verAData?.graph_data || null);
      setGraphB(verBData?.graph_data || null);
    } catch (err: any) {
      setError(err.detail || "Failed to compute diff");
    } finally {
      setDiffLoading(false);
    }
  }, [componentId, versionA, versionB]);

  // Auto-run comparison when both versions selected
  useEffect(() => {
    if (versionA !== "" && versionB !== "" && versionA !== versionB) {
      runComparison();
    }
  }, [versionA, versionB, runComparison]);

  if (!componentId) {
    return (
      <div className="flex h-96 flex-col items-center justify-center text-gray-400">
        <GitBranch className="h-10 w-10 mb-3" />
        <p className="text-sm font-medium">No component selected</p>
        <p className="mt-1 text-xs">
          Navigate here from a code component page to compare graph versions.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
        <p className="ml-2 text-sm text-gray-500">Loading versions...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50/50 p-4 lg:p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-indigo-50 p-3">
            <ArrowLeftRight className="h-6 w-6 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Branch Comparison
            </h1>
            <p className="mt-0.5 text-sm text-gray-500">
              Compare knowledge graph versions to see what changed between
              branches or commits
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {/* Version Selector */}
      <div className="mb-6 rounded-lg border bg-white p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">
          Select Versions to Compare
        </h3>
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Version A (Before)
            </label>
            <select
              value={versionA}
              onChange={(e) =>
                setVersionA(e.target.value ? Number(e.target.value) : "")
              }
              className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">Select version...</option>
              {versions.map((v) => (
                <option key={v.id} value={v.version_number}>
                  v{v.version_number} —{" "}
                  {new Date(v.created_at).toLocaleDateString()}{" "}
                  {v.metadata?.commit_hash
                    ? `(${v.metadata.commit_hash.slice(0, 8)})`
                    : ""}
                </option>
              ))}
            </select>
          </div>

          <ArrowRight className="mb-2 h-5 w-5 flex-shrink-0 text-gray-400" />

          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Version B (After)
            </label>
            <select
              value={versionB}
              onChange={(e) =>
                setVersionB(e.target.value ? Number(e.target.value) : "")
              }
              className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">Select version...</option>
              {versions
                .filter((v) => v.version_number !== Number(versionA))
                .map((v) => (
                  <option key={v.id} value={v.version_number}>
                    v{v.version_number} —{" "}
                    {new Date(v.created_at).toLocaleDateString()}{" "}
                    {v.metadata?.commit_hash
                      ? `(${v.metadata.commit_hash.slice(0, 8)})`
                      : ""}
                  </option>
                ))}
            </select>
          </div>

          <button
            onClick={runComparison}
            disabled={
              diffLoading || versionA === "" || versionB === "" || versionA === versionB
            }
            className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {diffLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Compare
          </button>
        </div>

        {versions.length < 2 && (
          <p className="mt-3 text-xs text-amber-600">
            At least 2 graph versions are needed for comparison. Analyze more
            commits to generate additional versions.
          </p>
        )}
      </div>

      {/* Diff Summary */}
      {diff && (
        <div className="mb-6 grid grid-cols-3 gap-4">
          <div className="rounded-lg border bg-white p-4">
            <div className="flex items-center gap-2">
              <Plus className="h-5 w-5 text-green-500" />
              <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Added
              </span>
            </div>
            <p className="mt-2 text-2xl font-bold text-green-600">
              {diff.summary.total_added}
            </p>
            <p className="text-xs text-gray-400">
              {diff.added_nodes.length} nodes, {diff.added_edges.length} edges
            </p>
          </div>
          <div className="rounded-lg border bg-white p-4">
            <div className="flex items-center gap-2">
              <Minus className="h-5 w-5 text-red-500" />
              <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Removed
              </span>
            </div>
            <p className="mt-2 text-2xl font-bold text-red-600">
              {diff.summary.total_removed}
            </p>
            <p className="text-xs text-gray-400">
              {diff.removed_nodes.length} nodes, {diff.removed_edges.length}{" "}
              edges
            </p>
          </div>
          <div className="rounded-lg border bg-white p-4">
            <div className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5 text-amber-500" />
              <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Changed
              </span>
            </div>
            <p className="mt-2 text-2xl font-bold text-amber-600">
              {diff.summary.total_changed}
            </p>
            <p className="text-xs text-gray-400">
              {diff.changed_nodes.length} modified nodes
            </p>
          </div>
        </div>
      )}

      {/* Two-Column Graph Comparison */}
      {diff && (
        <div className="grid grid-cols-2 gap-4">
          {/* Version A (Before) */}
          <div className="rounded-lg border bg-white">
            <div className="border-b px-4 py-3">
              <h3 className="text-sm font-semibold text-gray-900">
                <GitBranch className="mr-1.5 inline h-4 w-4 text-gray-400" />
                Version {versionA} (Before)
              </h3>
            </div>
            <div style={{ height: "450px" }}>
              {graphA?.nodes?.length > 0 ? (
                <OntologyGraph
                  nodes={(graphA.nodes || []).map((n: any) => {
                    const isRemoved = diff.removed_nodes.some(
                      (r: any) => r.name === n.name || r.id === n.id
                    );
                    return {
                      id: n.id ?? n.name,
                      name: n.name,
                      concept_type: n.type ?? n.concept_type,
                      confidence_score: isRemoved
                        ? 0.2
                        : n.confidence ?? n.confidence_score ?? 0.7,
                      description: isRemoved
                        ? `[REMOVED] ${n.description || ""}`
                        : n.description,
                      source_type: n.source_type,
                    };
                  })}
                  edges={(graphA.edges || []).map((e: any) => ({
                    id: e.id ?? `${e.source}-${e.target}`,
                    source_concept_id: e.source ?? e.source_concept_id,
                    target_concept_id: e.target ?? e.target_concept_id,
                    relationship_type: e.type ?? e.relationship_type,
                    confidence_score: e.confidence ?? e.confidence_score ?? 0.7,
                  }))}
                  selectedId={null}
                  onSelectNode={() => {}}
                />
              ) : (
                <div className="flex h-full items-center justify-center text-gray-400 text-sm">
                  No graph data for this version
                </div>
              )}
            </div>
          </div>

          {/* Version B (After) */}
          <div className="rounded-lg border bg-white">
            <div className="border-b px-4 py-3">
              <h3 className="text-sm font-semibold text-gray-900">
                <GitBranch className="mr-1.5 inline h-4 w-4 text-green-500" />
                Version {versionB} (After)
              </h3>
            </div>
            <div style={{ height: "450px" }}>
              {graphB?.nodes?.length > 0 ? (
                <OntologyGraph
                  nodes={(graphB.nodes || []).map((n: any) => {
                    const isAdded = diff.added_nodes.some(
                      (a: any) => a.name === n.name || a.id === n.id
                    );
                    const isChanged = diff.changed_nodes.some(
                      (c: any) => c.name === n.name || c.id === n.id
                    );
                    return {
                      id: n.id ?? n.name,
                      name: n.name,
                      concept_type: n.type ?? n.concept_type,
                      confidence_score: n.confidence ?? n.confidence_score ?? 0.7,
                      description: isAdded
                        ? `[NEW] ${n.description || ""}`
                        : isChanged
                          ? `[CHANGED] ${n.description || ""}`
                          : n.description,
                      source_type: n.source_type,
                    };
                  })}
                  edges={(graphB.edges || []).map((e: any) => ({
                    id: e.id ?? `${e.source}-${e.target}`,
                    source_concept_id: e.source ?? e.source_concept_id,
                    target_concept_id: e.target ?? e.target_concept_id,
                    relationship_type: e.type ?? e.relationship_type,
                    confidence_score: e.confidence ?? e.confidence_score ?? 0.7,
                  }))}
                  selectedId={null}
                  onSelectNode={() => {}}
                />
              ) : (
                <div className="flex h-full items-center justify-center text-gray-400 text-sm">
                  No graph data for this version
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Diff Detail Tables */}
      {diff && (diff.added_nodes.length > 0 || diff.removed_nodes.length > 0 || diff.changed_nodes.length > 0) && (
        <div className="mt-6 rounded-lg border bg-white">
          <div className="border-b px-5 py-3">
            <h3 className="text-sm font-semibold text-gray-900">
              Change Details
            </h3>
          </div>
          <div className="divide-y">
            {/* Added */}
            {diff.added_nodes.length > 0 && (
              <div className="px-5 py-3">
                <h4 className="text-xs font-semibold text-green-700 uppercase tracking-wide mb-2">
                  <Plus className="mr-1 inline h-3 w-3" />
                  Added ({diff.added_nodes.length})
                </h4>
                <div className="flex flex-wrap gap-2">
                  {diff.added_nodes.map((n: any, i: number) => (
                    <span
                      key={i}
                      className="inline-flex items-center rounded-md bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-200"
                    >
                      {n.name || n.id}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Removed */}
            {diff.removed_nodes.length > 0 && (
              <div className="px-5 py-3">
                <h4 className="text-xs font-semibold text-red-700 uppercase tracking-wide mb-2">
                  <Minus className="mr-1 inline h-3 w-3" />
                  Removed ({diff.removed_nodes.length})
                </h4>
                <div className="flex flex-wrap gap-2">
                  {diff.removed_nodes.map((n: any, i: number) => (
                    <span
                      key={i}
                      className="inline-flex items-center rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-200"
                    >
                      {n.name || n.id}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Changed */}
            {diff.changed_nodes.length > 0 && (
              <div className="px-5 py-3">
                <h4 className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-2">
                  <RefreshCw className="mr-1 inline h-3 w-3" />
                  Changed ({diff.changed_nodes.length})
                </h4>
                <div className="flex flex-wrap gap-2">
                  {diff.changed_nodes.map((n: any, i: number) => (
                    <span
                      key={i}
                      className="inline-flex items-center rounded-md bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-200"
                    >
                      {n.name || n.id}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Empty state when no diff yet */}
      {!diff && !diffLoading && versions.length >= 2 && (
        <div className="flex h-60 flex-col items-center justify-center rounded-lg border border-dashed bg-white text-gray-400">
          <ArrowLeftRight className="h-10 w-10 mb-3" />
          <p className="text-sm font-medium">Select two versions to compare</p>
          <p className="mt-1 text-xs">
            See what concepts were added, removed, or changed between graph
            versions
          </p>
        </div>
      )}

      {diffLoading && (
        <div className="flex h-60 items-center justify-center rounded-lg border bg-white">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
          <p className="ml-2 text-sm text-gray-500">Computing diff...</p>
        </div>
      )}
    </div>
  );
}

export default function BranchComparisonPage() {
  return <Suspense fallback={<div className="flex h-screen items-center justify-center"><div className="animate-spin h-8 w-8 border-2 border-indigo-600 rounded-full border-t-transparent" /></div>}><BranchComparisonContent /></Suspense>;
}
