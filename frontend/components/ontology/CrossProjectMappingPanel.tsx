"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  Filter,
  Loader2,
  Play,
  RefreshCw,
  X,
  BarChart3,
  GitCompare,
  Brain,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";

/* -------------------------------------------------------------------------- */
/*  Types                                                                      */
/* -------------------------------------------------------------------------- */

interface CrossProjectMapping {
  id: number;
  concept_a_id: number;
  concept_b_id: number;
  initiative_a_id: number;
  initiative_b_id: number;
  mapping_method: string;
  confidence_score: number;
  status: string;
  relationship_type: string;
  ai_reasoning: string | null;
  concept_a_name: string;
  concept_a_type: string;
  concept_b_name: string;
  concept_b_type: string;
  initiative_a_name: string;
  initiative_b_name: string;
  created_at: string;
}

interface CrossProjectStats {
  total_mappings: number;
  confirmed: number;
  candidate: number;
  rejected: number;
  by_method: Record<string, number>;
  by_relationship: Record<string, number>;
}

export interface CrossProjectMappingPanelProps {
  projects: { id: number; name: string }[];
}

/* -------------------------------------------------------------------------- */
/*  Constants                                                                  */
/* -------------------------------------------------------------------------- */

const METHOD_BADGES: Record<string, { bg: string; text: string; label: string }> = {
  exact: { bg: "bg-green-100", text: "text-green-700", label: "Exact" },
  fuzzy: { bg: "bg-amber-100", text: "text-amber-700", label: "Fuzzy" },
  ai_validated: { bg: "bg-purple-100", text: "text-purple-700", label: "AI" },
};

const STATUS_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  confirmed: { bg: "bg-green-100", text: "text-green-700", dot: "bg-green-500" },
  candidate: { bg: "bg-amber-100", text: "text-amber-700", dot: "bg-amber-500" },
  rejected: { bg: "bg-red-100", text: "text-red-700", dot: "bg-red-500" },
};

const RELATIONSHIP_LABELS: Record<string, string> = {
  same_as: "Same as",
  extends: "Extends",
  similar_to: "Similar to",
  related_to: "Related to",
  part_of: "Part of",
  implements: "Implements",
  contradicts: "Contradicts",
};

const STATUS_FILTERS = ["all", "confirmed", "candidate", "rejected"] as const;

/* -------------------------------------------------------------------------- */
/*  Component                                                                  */
/* -------------------------------------------------------------------------- */

export function CrossProjectMappingPanel({ projects }: CrossProjectMappingPanelProps) {
  /* ---- State ---- */
  const [mappings, setMappings] = useState<CrossProjectMapping[]>([]);
  const [stats, setStats] = useState<CrossProjectStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  // Run mapping state
  const [showRunForm, setShowRunForm] = useState(false);
  const [projectA, setProjectA] = useState<number | "">("");
  const [projectB, setProjectB] = useState<number | "">("");
  const [runLoading, setRunLoading] = useState(false);

  /* ---- Data fetching ---- */
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [mappingsRes, statsRes] = await Promise.all([
        api.get<CrossProjectMapping[]>("/ontology/cross-project/mappings"),
        api.get<CrossProjectStats>("/ontology/cross-project/stats"),
      ]);
      setMappings(mappingsRes);
      setStats(statsRes);
    } catch (err) {
      console.error("[CrossProjectMappingPanel] Failed to fetch data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  /* ---- Actions ---- */
  const handleConfirm = async (id: number) => {
    setActionLoading(id);
    try {
      await api.put(`/ontology/cross-project/mappings/${id}/confirm`);
      setMappings((prev) =>
        prev.map((m) => (m.id === id ? { ...m, status: "confirmed" } : m)),
      );
      if (stats) {
        setStats({
          ...stats,
          confirmed: stats.confirmed + 1,
          candidate: stats.candidate - 1,
        });
      }
    } catch (err) {
      console.error("[CrossProjectMappingPanel] Failed to confirm mapping:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (id: number) => {
    setActionLoading(id);
    try {
      await api.put(`/ontology/cross-project/mappings/${id}/reject`);
      setMappings((prev) =>
        prev.map((m) => (m.id === id ? { ...m, status: "rejected" } : m)),
      );
      if (stats) {
        setStats({
          ...stats,
          rejected: (stats.rejected ?? 0) + 1,
          candidate: stats.candidate - 1,
        });
      }
    } catch (err) {
      console.error("[CrossProjectMappingPanel] Failed to reject mapping:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRunMapping = async () => {
    if (projectA === "" || projectB === "" || projectA === projectB) return;
    setRunLoading(true);
    try {
      await api.post(
        `/ontology/cross-project/run?initiative_a_id=${projectA}&initiative_b_id=${projectB}`,
      );
      setShowRunForm(false);
      setProjectA("");
      setProjectB("");
      await fetchData();
    } catch (err) {
      console.error("[CrossProjectMappingPanel] Failed to run cross-project mapping:", err);
    } finally {
      setRunLoading(false);
    }
  };

  /* ---- Filtered list ---- */
  const filtered =
    statusFilter === "all"
      ? mappings
      : mappings.filter((m) => m.status === statusFilter);

  /* ---- Confidence bar color ---- */
  const confidenceColor = (score: number) => {
    if (score >= 0.8) return "bg-green-500";
    if (score >= 0.5) return "bg-amber-500";
    return "bg-red-500";
  };

  /* ---- Render ---- */
  return (
    <div className="space-y-6">
      {/* ---------- Header ---------- */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Cross-Project Mappings</h2>
          <p className="mt-0.5 text-sm text-gray-500">
            Concept mappings discovered across different projects
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            onClick={() => setShowRunForm(!showRunForm)}
            className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700"
          >
            <Play className="h-4 w-4" />
            Run Cross-Project Mapping
          </button>
        </div>
      </div>

      {/* ---------- Run Mapping Form ---------- */}
      {showRunForm && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <h3 className="text-sm font-semibold text-blue-900">Run Cross-Project Mapping</h3>
          <p className="mt-1 text-xs text-blue-700">
            Select two projects to discover concept mappings between them.
          </p>
          <div className="mt-3 flex items-end gap-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-blue-800">Project A</label>
              <select
                value={projectA}
                onChange={(e) => setProjectA(e.target.value ? Number(e.target.value) : "")}
                className="mt-1 block w-full rounded-md border border-blue-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">Select project...</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <ArrowRight className="mb-2 h-5 w-5 flex-shrink-0 text-blue-400" />
            <div className="flex-1">
              <label className="block text-xs font-medium text-blue-800">Project B</label>
              <select
                value={projectB}
                onChange={(e) => setProjectB(e.target.value ? Number(e.target.value) : "")}
                className="mt-1 block w-full rounded-md border border-blue-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">Select project...</option>
                {projects
                  .filter((p) => p.id !== projectA)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
              </select>
            </div>
            <button
              onClick={handleRunMapping}
              disabled={runLoading || projectA === "" || projectB === "" || projectA === projectB}
              className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {runLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Run
            </button>
            <button
              onClick={() => {
                setShowRunForm(false);
                setProjectA("");
                setProjectB("");
              }}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* ---------- Stats Cards ---------- */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <GitCompare className="h-5 w-5 text-gray-400" />
              <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Total
              </span>
            </div>
            <p className="mt-2 text-2xl font-bold text-gray-900">{stats.total_mappings}</p>
          </div>
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <Check className="h-5 w-5 text-green-500" />
              <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Confirmed
              </span>
            </div>
            <p className="mt-2 text-2xl font-bold text-green-600">{stats.confirmed}</p>
          </div>
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <Filter className="h-5 w-5 text-amber-500" />
              <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Candidate
              </span>
            </div>
            <p className="mt-2 text-2xl font-bold text-amber-600">{stats.candidate}</p>
          </div>
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-blue-500" />
              <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
                By Method
              </span>
            </div>
            <div className="mt-2 flex items-center gap-2">
              {Object.entries(stats.by_method).map(([method, count]) => {
                const badge = METHOD_BADGES[method] || { bg: "bg-gray-100", text: "text-gray-600", label: method };
                return (
                  <span
                    key={method}
                    className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium ${badge.bg} ${badge.text}`}
                  >
                    {badge.label}: {count}
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ---------- Status Filter Tabs ---------- */}
      <div className="flex border-b">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors ${
              statusFilter === s
                ? "border-b-2 border-blue-600 text-blue-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {s}
            {s !== "all" && stats && (
              <span className="ml-1.5 text-xs text-gray-400">
                ({s === "confirmed" ? stats.confirmed : s === "candidate" ? stats.candidate : stats.rejected ?? 0})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ---------- Mappings List ---------- */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          <span className="ml-2 text-sm text-gray-500">Loading mappings...</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-gray-400">
          <GitCompare className="h-10 w-10" />
          <p className="mt-3 text-sm font-medium">No mappings found</p>
          <p className="mt-1 text-xs">
            {statusFilter !== "all"
              ? `No ${statusFilter} mappings. Try a different filter.`
              : "Run a cross-project mapping to discover concept relationships."}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((m) => {
            const isExpanded = m.id === expandedId;
            const methodBadge = METHOD_BADGES[m.mapping_method] || {
              bg: "bg-gray-100",
              text: "text-gray-600",
              label: m.mapping_method,
            };
            const statusStyle = STATUS_COLORS[m.status] || STATUS_COLORS.candidate;

            return (
              <div
                key={m.id}
                className="rounded-lg border bg-white shadow-sm transition-shadow hover:shadow-md"
              >
                {/* Card header */}
                <div
                  className="cursor-pointer px-4 py-3"
                  onClick={() => setExpandedId(isExpanded ? null : m.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex min-w-0 flex-1 items-center gap-3">
                      {/* Concept A */}
                      <div className="min-w-0 flex-shrink">
                        <p className="truncate text-sm font-medium text-blue-700">
                          {m.concept_a_name}
                        </p>
                        <p className="truncate text-xs text-gray-400">
                          {m.initiative_a_name} &middot;{" "}
                          <span className="capitalize">{m.concept_a_type}</span>
                        </p>
                      </div>

                      {/* Arrow */}
                      <ArrowRight className="h-4 w-4 flex-shrink-0 text-gray-300" />

                      {/* Concept B */}
                      <div className="min-w-0 flex-shrink">
                        <p className="truncate text-sm font-medium text-indigo-700">
                          {m.concept_b_name}
                        </p>
                        <p className="truncate text-xs text-gray-400">
                          {m.initiative_b_name} &middot;{" "}
                          <span className="capitalize">{m.concept_b_type}</span>
                        </p>
                      </div>
                    </div>

                    {/* Right side: badges + expand */}
                    <div className="ml-4 flex flex-shrink-0 items-center gap-2">
                      {/* Method badge */}
                      <span
                        className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${methodBadge.bg} ${methodBadge.text}`}
                      >
                        {methodBadge.label}
                      </span>

                      {/* Confidence */}
                      <div className="flex items-center gap-1.5">
                        <div className="h-2 w-16 rounded-full bg-gray-200">
                          <div
                            className={`h-full rounded-full transition-all ${confidenceColor(m.confidence_score)}`}
                            style={{ width: `${m.confidence_score * 100}%` }}
                          />
                        </div>
                        <span className="text-xs font-medium text-gray-600">
                          {Math.round(m.confidence_score * 100)}%
                        </span>
                      </div>

                      {/* Status */}
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusStyle.bg} ${statusStyle.text}`}
                      >
                        <span className={`inline-block h-1.5 w-1.5 rounded-full ${statusStyle.dot}`} />
                        {m.status}
                      </span>

                      {/* Relationship */}
                      <span className="text-xs text-gray-400">
                        {RELATIONSHIP_LABELS[m.relationship_type] || m.relationship_type}
                      </span>

                      {/* Expand chevron */}
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4 text-gray-400" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-gray-400" />
                      )}
                    </div>
                  </div>
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="border-t bg-gray-50 px-4 py-3">
                    <div className="grid grid-cols-2 gap-4 text-xs sm:grid-cols-4">
                      <div>
                        <span className="text-gray-500">Relationship</span>
                        <p className="mt-0.5 font-medium text-gray-900">
                          {RELATIONSHIP_LABELS[m.relationship_type] || m.relationship_type}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-500">Method</span>
                        <p className="mt-0.5 font-medium text-gray-900 capitalize">
                          {m.mapping_method.replace("_", " ")}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-500">Confidence</span>
                        <p className="mt-0.5 font-medium text-gray-900">
                          {Math.round(m.confidence_score * 100)}%
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-500">Created</span>
                        <p className="mt-0.5 font-medium text-gray-900">
                          {new Date(m.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>

                    {/* AI Reasoning */}
                    {m.ai_reasoning && (
                      <div className="mt-3 rounded-md border border-purple-200 bg-purple-50 p-3">
                        <div className="flex items-center gap-1.5">
                          <Brain className="h-3.5 w-3.5 text-purple-500" />
                          <span className="text-xs font-medium text-purple-700">AI Reasoning</span>
                        </div>
                        <p className="mt-1.5 text-xs leading-relaxed text-purple-900">
                          {m.ai_reasoning}
                        </p>
                      </div>
                    )}

                    {/* Action buttons for candidates */}
                    {m.status === "candidate" && (
                      <div className="mt-3 flex gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleConfirm(m.id);
                          }}
                          disabled={actionLoading === m.id}
                          className="inline-flex items-center gap-1.5 rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
                        >
                          {actionLoading === m.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Check className="h-3.5 w-3.5" />
                          )}
                          Confirm Mapping
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleReject(m.id);
                          }}
                          disabled={actionLoading === m.id}
                          className="inline-flex items-center gap-1.5 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                        >
                          {actionLoading === m.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <X className="h-3.5 w-3.5" />
                          )}
                          Reject Mapping
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
