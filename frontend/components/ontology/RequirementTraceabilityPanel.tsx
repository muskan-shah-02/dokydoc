"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  Shield,
  Loader2,
  RefreshCw,
  Link2,
  Filter,
  AlertTriangle,
} from "lucide-react";
import { api } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Trace {
  id: number;
  document_id: number;
  requirement_key: string;
  requirement_text: string;
  code_concept_ids: number[];
  coverage_status: "covered" | "partial" | "uncovered" | "not_applicable";
  validation_status: "validated" | "pending" | "failed";
}

interface TraceabilityResponse {
  traces: Trace[];
  total: number;
}

export interface RequirementTraceabilityPanelProps {
  initiativeId: number;
  documentIds: number[];
}

/* ------------------------------------------------------------------ */
/*  Coverage badge colors                                              */
/* ------------------------------------------------------------------ */

const COVERAGE_COLORS: Record<string, string> = {
  covered: "bg-green-100 text-green-700",
  partial: "bg-yellow-100 text-yellow-700",
  uncovered: "bg-red-100 text-red-700",
  not_applicable: "bg-gray-100 text-gray-500",
};

const COVERAGE_LABELS: Record<string, string> = {
  covered: "Covered",
  partial: "Partial",
  uncovered: "Uncovered",
  not_applicable: "N/A",
};

const VALIDATION_COLORS: Record<string, string> = {
  validated: "bg-green-100 text-green-700",
  pending: "bg-blue-100 text-blue-700",
  failed: "bg-red-100 text-red-700",
};

const VALIDATION_LABELS: Record<string, string> = {
  validated: "Validated",
  pending: "Pending",
  failed: "Failed",
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function RequirementTraceabilityPanel({
  initiativeId,
  documentIds,
}: RequirementTraceabilityPanelProps) {
  const [open, setOpen] = useState(false);
  const [traces, setTraces] = useState<Trace[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [building, setBuilding] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("all");

  /* ---- Fetch traces ---- */

  const fetchTraces = useCallback(
    async (force = false) => {
      if (traces.length > 0 && !force) return;
      setLoading(true);
      setError("");
      try {
        const data = await api.get<TraceabilityResponse>(
          `/ontology/traceability/initiative/${initiativeId}`
        );
        setTraces(data.traces);
        setTotal(data.total);
      } catch {
        setError("Failed to load traceability data");
        setTraces([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    },
    [initiativeId, traces.length]
  );

  /* ---- Build traces ---- */

  const handleBuild = async () => {
    if (documentIds.length === 0) return;
    setBuilding(true);
    try {
      await Promise.all(
        documentIds.map((docId) =>
          api.post(`/ontology/traceability/build/${docId}`)
        )
      );
      await fetchTraces(true);
    } catch {
      setError("Build traces failed for one or more documents");
    } finally {
      setBuilding(false);
    }
  };

  /* ---- Auto-fetch on expand ---- */

  useEffect(() => {
    if (open) fetchTraces();
  }, [open, fetchTraces]);

  /* ---- Derived data ---- */

  const filtered = useMemo(() => {
    if (filterStatus === "all") return traces;
    return traces.filter((t) => t.coverage_status === filterStatus);
  }, [traces, filterStatus]);

  const coveredCount = useMemo(
    () => traces.filter((t) => t.coverage_status === "covered").length,
    [traces]
  );

  const coveragePct = total > 0 ? Math.round((coveredCount / total) * 100) : 0;

  /* ---- Render ---- */

  return (
    <div className="mt-6 rounded-lg border bg-white">
      {/* Header / toggle */}
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between border-b px-5 py-3 text-left"
      >
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
          <Shield className="h-4 w-4 text-indigo-500" />
          Requirement Traceability
        </h2>
        <span className="flex items-center gap-1 text-xs text-gray-400">
          {open ? (
            <>
              Collapse <ChevronDown className="h-3.5 w-3.5" />
            </>
          ) : (
            <>
              Expand <ChevronRight className="h-3.5 w-3.5" />
            </>
          )}
        </span>
      </button>

      {open && (
        <div className="p-5">
          {loading ? (
            <div className="flex h-40 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
              <p className="ml-2 text-sm text-gray-500">
                Loading traceability data...
              </p>
            </div>
          ) : error && traces.length === 0 ? (
            <div className="flex h-40 flex-col items-center justify-center text-gray-400">
              <AlertTriangle className="mb-2 h-8 w-8" />
              <p className="text-sm">{error}</p>
            </div>
          ) : (
            <>
              {/* Coverage summary bar */}
              <div className="mb-4 rounded-lg border bg-gray-50 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-gray-700">
                    {coveredCount} covered / {total} total requirements
                  </p>
                  <span className="text-sm font-bold text-gray-900">
                    {coveragePct}%
                  </span>
                </div>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-gray-200">
                  <div
                    className="h-full rounded-full bg-green-500 transition-all"
                    style={{ width: `${coveragePct}%` }}
                  />
                </div>
              </div>

              {/* Actions row */}
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <button
                  onClick={handleBuild}
                  disabled={building || documentIds.length === 0}
                  className="flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {building ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Link2 className="h-3.5 w-3.5" />
                  )}
                  {building ? "Building..." : "Build Traces"}
                </button>

                <button
                  onClick={() => fetchTraces(true)}
                  disabled={loading}
                  className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                >
                  <RefreshCw
                    className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`}
                  />
                  Refresh
                </button>

                {/* Filter dropdown */}
                <div className="ml-auto flex items-center gap-1.5">
                  <Filter className="h-3.5 w-3.5 text-gray-400" />
                  <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="rounded-md border bg-white px-2 py-1.5 text-xs text-gray-700 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                    <option value="all">All statuses</option>
                    <option value="covered">Covered</option>
                    <option value="partial">Partial</option>
                    <option value="uncovered">Uncovered</option>
                    <option value="not_applicable">N/A</option>
                  </select>
                </div>
              </div>

              {/* Error banner (non-blocking) */}
              {error && (
                <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-2 text-xs text-red-600">
                  {error}
                </div>
              )}

              {/* Requirements table */}
              {filtered.length === 0 ? (
                <div className="flex h-32 flex-col items-center justify-center text-gray-400">
                  <Shield className="mb-2 h-8 w-8" />
                  <p className="text-sm">
                    {traces.length === 0
                      ? "No traceability data yet. Build traces to get started."
                      : "No requirements match the selected filter."}
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto rounded-lg border">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b bg-gray-50 text-xs font-medium uppercase tracking-wider text-gray-500">
                        <th className="px-4 py-2.5">Requirement</th>
                        <th className="px-4 py-2.5">Text</th>
                        <th className="px-4 py-2.5">Coverage</th>
                        <th className="px-4 py-2.5">Validation</th>
                        <th className="px-4 py-2.5 text-right">
                          Code Concepts
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {filtered.map((trace) => (
                        <tr
                          key={trace.id}
                          className="hover:bg-gray-50/60"
                        >
                          <td className="whitespace-nowrap px-4 py-2.5 font-medium text-gray-900">
                            {trace.requirement_key}
                          </td>
                          <td
                            className="max-w-xs truncate px-4 py-2.5 text-gray-600"
                            title={trace.requirement_text}
                          >
                            {trace.requirement_text}
                          </td>
                          <td className="px-4 py-2.5">
                            <span
                              className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${
                                COVERAGE_COLORS[trace.coverage_status] ??
                                "bg-gray-100 text-gray-500"
                              }`}
                            >
                              {COVERAGE_LABELS[trace.coverage_status] ??
                                trace.coverage_status}
                            </span>
                          </td>
                          <td className="px-4 py-2.5">
                            <span
                              className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${
                                VALIDATION_COLORS[trace.validation_status] ??
                                "bg-gray-100 text-gray-500"
                              }`}
                            >
                              {VALIDATION_LABELS[trace.validation_status] ??
                                trace.validation_status}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-right text-gray-600">
                            {trace.code_concept_ids.length}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
