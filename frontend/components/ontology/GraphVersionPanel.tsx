"use client";

import { useState, useEffect, useCallback } from "react";
import { X, History, GitCompare, Check, ChevronRight, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

/**
 * GraphVersionPanel — Slide-over panel showing graph version history
 * and visual diff comparison for code files and documents.
 */

interface GraphVersion {
  id: number;
  version: number;
  is_current: boolean;
  graph_hash: string;
  graph_delta: Record<string, unknown> | null;
  created_at: string;
}

interface GraphDiffDelta {
  summary: string;
  added_nodes: string[];
  removed_nodes: string[];
  added_edges: string[];
  removed_edges: string[];
}

interface GraphDiffResponse {
  version_a: number;
  version_b: number;
  delta: GraphDiffDelta;
}

interface GraphVersionPanelProps {
  sourceType: "component" | "document";
  sourceId: number;
  isOpen: boolean;
  onClose: () => void;
}

type PanelView = "history" | "compare";

export function GraphVersionPanel({
  sourceType,
  sourceId,
  isOpen,
  onClose,
}: GraphVersionPanelProps) {
  const [view, setView] = useState<PanelView>("history");
  const [versions, setVersions] = useState<GraphVersion[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [versionsError, setVersionsError] = useState<string | null>(null);

  const [selectedV1, setSelectedV1] = useState<number | null>(null);
  const [selectedV2, setSelectedV2] = useState<number | null>(null);
  const [diff, setDiff] = useState<GraphDiffResponse | null>(null);
  const [loadingDiff, setLoadingDiff] = useState(false);
  const [diffError, setDiffError] = useState<string | null>(null);

  const fetchVersions = useCallback(async () => {
    setLoadingVersions(true);
    setVersionsError(null);
    try {
      const data = await api.get<GraphVersion[]>(
        `/ontology/graph/${sourceType}/${sourceId}/versions`
      );
      setVersions(data);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : typeof err === "object" && err !== null && "detail" in err
            ? (err as { detail: string }).detail
            : "Failed to load versions";
      setVersionsError(message);
    } finally {
      setLoadingVersions(false);
    }
  }, [sourceType, sourceId]);

  useEffect(() => {
    if (isOpen) {
      fetchVersions();
      setView("history");
      setSelectedV1(null);
      setSelectedV2(null);
      setDiff(null);
      setDiffError(null);
    }
  }, [isOpen, fetchVersions]);

  const handleShowDiff = async () => {
    if (selectedV1 === null || selectedV2 === null) return;

    setLoadingDiff(true);
    setDiffError(null);
    setDiff(null);
    try {
      const data = await api.get<GraphDiffResponse>(
        `/ontology/graph/${sourceType}/${sourceId}/diff`,
        { v1: selectedV1, v2: selectedV2 }
      );
      setDiff(data);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : typeof err === "object" && err !== null && "detail" in err
            ? (err as { detail: string }).detail
            : "Failed to load diff";
      setDiffError(message);
    } finally {
      setLoadingDiff(false);
    }
  };

  const formatTimestamp = (iso: string): string => {
    const date = new Date(iso);
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const handleVersionSelect = (version: number) => {
    if (selectedV1 === version) {
      setSelectedV1(null);
      return;
    }
    if (selectedV2 === version) {
      setSelectedV2(null);
      return;
    }
    if (selectedV1 === null) {
      setSelectedV1(version);
    } else if (selectedV2 === null) {
      setSelectedV2(version);
    } else {
      // Replace the older selection
      setSelectedV1(selectedV2);
      setSelectedV2(version);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/20 transition-opacity"
        onClick={onClose}
      />

      {/* Slide-over panel */}
      <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div className="flex items-center gap-2">
            <History className="h-4 w-4 text-gray-500" />
            <h2 className="text-sm font-semibold text-gray-900">
              Graph Versions
            </h2>
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
              {sourceType}
            </span>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* View tabs */}
        <div className="flex border-b px-2">
          <button
            onClick={() => {
              setView("history");
              setDiff(null);
              setDiffError(null);
            }}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors ${
              view === "history"
                ? "border-b-2 border-blue-600 text-blue-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            <History className="h-3 w-3" />
            History
          </button>
          <button
            onClick={() => {
              setView("compare");
              setDiff(null);
              setDiffError(null);
            }}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors ${
              view === "compare"
                ? "border-b-2 border-blue-600 text-blue-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            <GitCompare className="h-3 w-3" />
            Compare
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {loadingVersions ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400">
              <Loader2 className="h-5 w-5 animate-spin" />
              <p className="mt-2 text-sm">Loading versions...</p>
            </div>
          ) : versionsError ? (
            <div className="px-4 py-8 text-center">
              <p className="text-sm text-red-600">{versionsError}</p>
              <button
                onClick={fetchVersions}
                className="mt-3 rounded-md bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-200"
              >
                Retry
              </button>
            </div>
          ) : versions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400">
              <History className="h-6 w-6" />
              <p className="mt-2 text-sm">No versions found</p>
            </div>
          ) : view === "history" ? (
            <VersionTimeline
              versions={versions}
              formatTimestamp={formatTimestamp}
            />
          ) : (
            <CompareView
              versions={versions}
              selectedV1={selectedV1}
              selectedV2={selectedV2}
              onVersionSelect={handleVersionSelect}
              onShowDiff={handleShowDiff}
              loadingDiff={loadingDiff}
              diff={diff}
              diffError={diffError}
              formatTimestamp={formatTimestamp}
            />
          )}
        </div>
      </div>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/*  Version Timeline                                                          */
/* -------------------------------------------------------------------------- */

function VersionTimeline({
  versions,
  formatTimestamp,
}: {
  versions: GraphVersion[];
  formatTimestamp: (iso: string) => string;
}) {
  return (
    <div className="px-4 py-3">
      <div className="relative">
        {/* Vertical timeline line */}
        <div className="absolute left-[7px] top-2 bottom-2 w-px bg-gray-200" />

        <div className="space-y-0">
          {versions.map((v, idx) => (
            <div key={v.id} className="relative flex gap-3 pb-4">
              {/* Timeline dot */}
              <div
                className={`relative z-10 mt-1 h-[15px] w-[15px] flex-shrink-0 rounded-full border-2 ${
                  v.is_current
                    ? "border-blue-500 bg-blue-500"
                    : "border-gray-300 bg-white"
                }`}
              >
                {v.is_current && (
                  <Check className="absolute inset-0 m-auto h-2 w-2 text-white" />
                )}
              </div>

              {/* Version info */}
              <div className="min-w-0 flex-1 rounded-lg border bg-gray-50 px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">
                    v{v.version}
                  </span>
                  {v.is_current && (
                    <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                      Current
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-gray-500">
                  {formatTimestamp(v.created_at)}
                </p>
                <p className="mt-1 truncate text-[10px] font-mono text-gray-400">
                  {v.graph_hash}
                </p>
              </div>

              {/* Connector arrow for non-last items */}
              {idx < versions.length - 1 && (
                <ChevronRight className="absolute -bottom-1 left-[3px] h-3 w-3 rotate-90 text-gray-300" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Compare View                                                              */
/* -------------------------------------------------------------------------- */

function CompareView({
  versions,
  selectedV1,
  selectedV2,
  onVersionSelect,
  onShowDiff,
  loadingDiff,
  diff,
  diffError,
  formatTimestamp,
}: {
  versions: GraphVersion[];
  selectedV1: number | null;
  selectedV2: number | null;
  onVersionSelect: (version: number) => void;
  onShowDiff: () => void;
  loadingDiff: boolean;
  diff: GraphDiffResponse | null;
  diffError: string | null;
  formatTimestamp: (iso: string) => string;
}) {
  const canCompare = selectedV1 !== null && selectedV2 !== null;

  return (
    <div className="flex flex-col">
      {/* Selection hint */}
      <div className="border-b bg-gray-50 px-4 py-2.5">
        <p className="text-xs text-gray-500">
          Select two versions to compare. Click a version to select or deselect
          it.
        </p>
        <div className="mt-2 flex items-center gap-2 text-xs">
          <span
            className={`rounded px-2 py-0.5 font-medium ${
              selectedV1 !== null
                ? "bg-blue-100 text-blue-700"
                : "bg-gray-100 text-gray-400"
            }`}
          >
            {selectedV1 !== null ? `v${selectedV1}` : "v?"}
          </span>
          <span className="text-gray-400">vs</span>
          <span
            className={`rounded px-2 py-0.5 font-medium ${
              selectedV2 !== null
                ? "bg-blue-100 text-blue-700"
                : "bg-gray-100 text-gray-400"
            }`}
          >
            {selectedV2 !== null ? `v${selectedV2}` : "v?"}
          </span>
        </div>
      </div>

      {/* Version list for selection */}
      <div className="divide-y">
        {versions.map((v) => {
          const isSelected =
            v.version === selectedV1 || v.version === selectedV2;
          const selectionLabel =
            v.version === selectedV1
              ? "A"
              : v.version === selectedV2
                ? "B"
                : null;

          return (
            <button
              key={v.id}
              onClick={() => onVersionSelect(v.version)}
              className={`flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                isSelected
                  ? "bg-blue-50 border-l-2 border-l-blue-500"
                  : "hover:bg-gray-50 border-l-2 border-l-transparent"
              }`}
            >
              {/* Selection indicator */}
              <div
                className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                  isSelected
                    ? "bg-blue-600 text-white"
                    : "border border-gray-300 text-gray-400"
                }`}
              >
                {selectionLabel}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">
                    v{v.version}
                  </span>
                  {v.is_current && (
                    <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                      Current
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-gray-500">
                  {formatTimestamp(v.created_at)}
                </p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Compare button */}
      <div className="border-t px-4 py-3">
        <button
          onClick={onShowDiff}
          disabled={!canCompare || loadingDiff}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loadingDiff ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <GitCompare className="h-4 w-4" />
          )}
          Show Diff
        </button>
      </div>

      {/* Diff error */}
      {diffError && (
        <div className="px-4 pb-3">
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
            {diffError}
          </p>
        </div>
      )}

      {/* Diff results */}
      {diff && <DiffResults diff={diff} />}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Diff Results                                                              */
/* -------------------------------------------------------------------------- */

function DiffResults({ diff }: { diff: GraphDiffResponse }) {
  const { delta } = diff;
  const hasChanges =
    delta.added_nodes.length > 0 ||
    delta.removed_nodes.length > 0 ||
    delta.added_edges.length > 0 ||
    delta.removed_edges.length > 0;

  return (
    <div className="border-t px-4 py-3">
      {/* Header */}
      <div className="mb-3 flex items-center gap-2">
        <GitCompare className="h-4 w-4 text-gray-500" />
        <h3 className="text-sm font-semibold text-gray-900">
          v{diff.version_a} vs v{diff.version_b}
        </h3>
      </div>

      {/* Summary */}
      <div className="mb-3 rounded-lg border bg-gray-50 px-3 py-2">
        <p className="text-xs text-gray-700">{delta.summary}</p>
      </div>

      {!hasChanges ? (
        <p className="py-4 text-center text-xs text-gray-400">
          No differences found between these versions.
        </p>
      ) : (
        <div className="space-y-3">
          {/* Added Nodes */}
          {delta.added_nodes.length > 0 && (
            <DiffSection
              label="Added Nodes"
              items={delta.added_nodes}
              variant="added"
            />
          )}

          {/* Removed Nodes */}
          {delta.removed_nodes.length > 0 && (
            <DiffSection
              label="Removed Nodes"
              items={delta.removed_nodes}
              variant="removed"
            />
          )}

          {/* Added Edges */}
          {delta.added_edges.length > 0 && (
            <DiffSection
              label="Added Edges"
              items={delta.added_edges}
              variant="added"
            />
          )}

          {/* Removed Edges */}
          {delta.removed_edges.length > 0 && (
            <DiffSection
              label="Removed Edges"
              items={delta.removed_edges}
              variant="removed"
            />
          )}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Diff Section                                                              */
/* -------------------------------------------------------------------------- */

function DiffSection({
  label,
  items,
  variant,
}: {
  label: string;
  items: string[];
  variant: "added" | "removed";
}) {
  const isAdded = variant === "added";

  return (
    <div>
      <div className="mb-1.5 flex items-center gap-1.5">
        <span
          className={`inline-block h-2 w-2 rounded-full ${
            isAdded ? "bg-green-500" : "bg-red-500"
          }`}
        />
        <span className="text-xs font-medium text-gray-700">{label}</span>
        <span className="text-[10px] text-gray-400">({items.length})</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item}
            className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
              isAdded
                ? "bg-green-50 text-green-700 border border-green-200"
                : "bg-red-50 text-red-700 border border-red-200"
            }`}
          >
            {isAdded ? "+" : "\u2212"} {item}
          </span>
        ))}
      </div>
    </div>
  );
}
