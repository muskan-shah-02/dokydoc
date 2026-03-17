"use client";

import { useState, useEffect, useCallback } from "react";
import { History, GitCompare, RotateCcw, Loader2, User, Calendar, HardDrive } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

interface DocumentVersion {
  id: number;
  document_id: number;
  version_number: number;
  content_hash: string;
  file_size: number | null;
  original_filename: string | null;
  uploaded_by_id: number;
  uploaded_by_email: string | null;
  created_at: string;
}

interface VersionHistoryPanelProps {
  documentId: number;
  onCompare: (versionA: number, versionB: number) => void;
  onRestored?: () => void;
}

export function VersionHistoryPanel({
  documentId,
  onCompare,
  onRestored,
}: VersionHistoryPanelProps) {
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedA, setSelectedA] = useState<number | null>(null);
  const [selectedB, setSelectedB] = useState<number | null>(null);
  const [restoring, setRestoring] = useState<number | null>(null);

  const fetchVersions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get(`/documents/${documentId}/versions`) as { versions: DocumentVersion[] };
      setVersions(data.versions || []);
    } catch {
      setError("Failed to load version history.");
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    fetchVersions();
  }, [fetchVersions]);

  const handleRestore = async (versionNumber: number) => {
    if (!confirm(`Restore to version ${versionNumber}? This will create a new version with the restored content.`)) return;
    setRestoring(versionNumber);
    try {
      await api.post(`/documents/${documentId}/versions/${versionNumber}/restore`, {});
      await fetchVersions();
      onRestored?.();
    } catch {
      alert("Failed to restore version.");
    } finally {
      setRestoring(null);
    }
  };

  const handleSelectForCompare = (versionNumber: number) => {
    if (selectedA === null) {
      setSelectedA(versionNumber);
    } else if (selectedB === null && versionNumber !== selectedA) {
      setSelectedB(versionNumber);
    } else {
      setSelectedA(versionNumber);
      setSelectedB(null);
    }
  };

  const handleCompare = () => {
    if (selectedA !== null && selectedB !== null) {
      const a = Math.min(selectedA, selectedB);
      const b = Math.max(selectedA, selectedB);
      onCompare(a, b);
    }
  };

  const formatSize = (bytes: number | null) => {
    if (!bytes) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-blue-600 mr-2" />
        <span className="text-sm text-gray-500">Loading version history...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 text-red-500 text-sm">{error}</div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-400">
        <History className="w-10 h-10 mb-3" />
        <p className="text-sm font-medium">No version history yet</p>
        <p className="text-xs mt-1">Upload a new version to start tracking changes</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Compare action bar */}
      {(selectedA !== null || selectedB !== null) && (
        <div className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <GitCompare className="w-4 h-4 text-blue-600 flex-shrink-0" />
          <span className="text-sm text-blue-700 flex-1">
            {selectedA !== null && selectedB !== null
              ? `Comparing v${Math.min(selectedA, selectedB)} → v${Math.max(selectedA, selectedB)}`
              : `v${selectedA} selected — click another version to compare`}
          </span>
          {selectedA !== null && selectedB !== null && (
            <Button size="sm" onClick={handleCompare} className="bg-blue-600 hover:bg-blue-700 h-7 text-xs">
              Compare
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-xs text-blue-600"
            onClick={() => { setSelectedA(null); setSelectedB(null); }}
          >
            Clear
          </Button>
        </div>
      )}

      {/* Version list */}
      <div className="space-y-2">
        {versions.map((v, idx) => {
          const isLatest = idx === 0;
          const isSelectedA = selectedA === v.version_number;
          const isSelectedB = selectedB === v.version_number;
          const isSelected = isSelectedA || isSelectedB;

          return (
            <div
              key={v.id}
              className={`border rounded-lg p-4 transition-colors ${
                isSelected
                  ? "border-blue-400 bg-blue-50"
                  : "border-gray-200 bg-white hover:border-gray-300"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                    isLatest ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"
                  }`}>
                    v{v.version_number}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900">
                        {v.original_filename || `Version ${v.version_number}`}
                      </span>
                      {isLatest && (
                        <Badge className="bg-blue-100 text-blue-700 text-xs px-1.5 py-0 h-4">
                          Latest
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                      <span className="flex items-center gap-1">
                        <User className="w-3 h-3" />
                        {v.uploaded_by_email || `User ${v.uploaded_by_id}`}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {new Date(v.created_at).toLocaleString()}
                      </span>
                      <span className="flex items-center gap-1">
                        <HardDrive className="w-3 h-3" />
                        {formatSize(v.file_size)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant={isSelected ? "default" : "outline"}
                    className={`h-7 text-xs ${isSelected ? "bg-blue-600 hover:bg-blue-700" : ""}`}
                    onClick={() => handleSelectForCompare(v.version_number)}
                  >
                    <GitCompare className="w-3 h-3 mr-1" />
                    {isSelectedA ? "A" : isSelectedB ? "B" : "Compare"}
                  </Button>
                  {!isLatest && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => handleRestore(v.version_number)}
                      disabled={restoring === v.version_number}
                    >
                      {restoring === v.version_number ? (
                        <Loader2 className="w-3 h-3 animate-spin mr-1" />
                      ) : (
                        <RotateCcw className="w-3 h-3 mr-1" />
                      )}
                      Restore
                    </Button>
                  )}
                </div>
              </div>

              {/* Hash preview */}
              <div className="mt-2 text-xs text-gray-400 font-mono">
                SHA256: {v.content_hash.slice(0, 16)}…
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
