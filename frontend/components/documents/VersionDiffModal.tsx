"use client";

import { useState, useEffect } from "react";
import { X, Loader2, Plus, Minus, Equal, BarChart2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface DiffLine {
  line_number: number;
  content: string;
  change_type: "added" | "removed" | "unchanged";
}

interface DiffStats {
  added_count: number;
  removed_count: number;
  unchanged_count: number;
  change_pct: number;
}

interface DiffResponse {
  version_a: number;
  version_b: number;
  document_id: number;
  lines_a: DiffLine[];
  lines_b: DiffLine[];
  stats: DiffStats;
}

interface VersionDiffModalProps {
  documentId: number;
  versionA: number;
  versionB: number;
  isOpen: boolean;
  onClose: () => void;
}

const lineStyle = (changeType: string) => {
  if (changeType === "added") return "bg-green-50 border-l-2 border-green-400";
  if (changeType === "removed") return "bg-red-50 border-l-2 border-red-400";
  return "";
};

const lineNumberStyle = (changeType: string) => {
  if (changeType === "added") return "text-green-600";
  if (changeType === "removed") return "text-red-500";
  return "text-gray-400";
};

const linePrefix = (changeType: string) => {
  if (changeType === "added") return "+";
  if (changeType === "removed") return "−";
  return " ";
};

function DiffSide({ lines, label }: { lines: DiffLine[]; label: string }) {
  return (
    <div className="flex-1 overflow-x-auto overflow-y-auto max-h-[60vh] font-mono text-xs border rounded-lg">
      <div className="sticky top-0 bg-gray-100 border-b px-3 py-1.5 text-xs font-semibold text-gray-600">
        {label}
      </div>
      {lines.length === 0 ? (
        <div className="flex items-center justify-center h-32 text-gray-400 text-xs">No content</div>
      ) : (
        lines.map((line, i) => (
          <div
            key={i}
            className={`flex items-start px-2 py-0.5 min-h-[1.4rem] ${lineStyle(line.change_type)}`}
          >
            <span className={`w-8 flex-shrink-0 text-right mr-3 select-none ${lineNumberStyle(line.change_type)}`}>
              {line.line_number}
            </span>
            <span className={`w-4 flex-shrink-0 mr-1 select-none font-bold ${lineNumberStyle(line.change_type)}`}>
              {linePrefix(line.change_type)}
            </span>
            <span className="whitespace-pre-wrap break-all leading-5">{line.content || " "}</span>
          </div>
        ))
      )}
    </div>
  );
}

export function VersionDiffModal({
  documentId,
  versionA,
  versionB,
  isOpen,
  onClose,
}: VersionDiffModalProps) {
  const [diff, setDiff] = useState<DiffResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    setError(null);
    setDiff(null);
    api
      .post(`/documents/${documentId}/versions/diff`, {
        version_a: versionA,
        version_b: versionB,
      })
      .then((data) => setDiff(data as DiffResponse))
      .catch(() => setError("Failed to compute diff."))
      .finally(() => setLoading(false));
  }, [isOpen, documentId, versionA, versionB]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-6xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Version Comparison
            </h2>
            <p className="text-sm text-gray-500">
              v{versionA} → v{versionB}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0">
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Stats bar */}
        {diff && (
          <div className="flex items-center gap-6 px-6 py-3 bg-gray-50 border-b flex-shrink-0">
            <div className="flex items-center gap-1.5 text-sm">
              <BarChart2 className="w-4 h-4 text-gray-400" />
              <span className="font-medium text-gray-600">Changes:</span>
              <span className="font-bold text-gray-600">{diff.stats.change_pct}%</span>
            </div>
            <div className="flex items-center gap-1.5 text-sm text-green-600">
              <Plus className="w-3.5 h-3.5" />
              <span className="font-medium">{diff.stats.added_count} added</span>
            </div>
            <div className="flex items-center gap-1.5 text-sm text-red-500">
              <Minus className="w-3.5 h-3.5" />
              <span className="font-medium">{diff.stats.removed_count} removed</span>
            </div>
            <div className="flex items-center gap-1.5 text-sm text-gray-400">
              <Equal className="w-3.5 h-3.5" />
              <span className="font-medium">{diff.stats.unchanged_count} unchanged</span>
            </div>
          </div>
        )}

        {/* Diff content */}
        <div className="flex-1 overflow-hidden p-4">
          {loading && (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="w-5 h-5 animate-spin text-blue-600 mr-2" />
              <span className="text-sm text-gray-500">Computing diff...</span>
            </div>
          )}
          {error && (
            <div className="text-center text-red-500 text-sm py-12">{error}</div>
          )}
          {diff && !loading && (
            <div className="flex gap-3 h-full">
              <DiffSide lines={diff.lines_a} label={`Version ${versionA} (older)`} />
              <DiffSide lines={diff.lines_b} label={`Version ${versionB} (newer)`} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
