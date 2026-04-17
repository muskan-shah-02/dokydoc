"use client";

/**
 * P5C-01: FileSuggestionBanner
 * Shows AI-generated file upload suggestions after BRD atomization.
 * Displayed on the document detail page so developers know which code files to upload.
 */

import { useState } from "react";
import { FolderCode, CheckCircle2, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { useFileSuggestions, FileSuggestion } from "@/hooks/useFileSuggestions";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface FileSuggestionBannerProps {
  documentId: number;
}

export default function FileSuggestionBanner({ documentId }: FileSuggestionBannerProps) {
  const { suggestions, total, loading, error, requestRefresh } = useFileSuggestions(documentId);
  const [expanded, setExpanded] = useState(false);

  const pending = suggestions.filter(s => !s.fulfilled);
  const fulfilled = suggestions.filter(s => s.fulfilled);

  if (loading && total === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-2 px-4 bg-muted/30 rounded-lg border animate-pulse">
        <FolderCode className="h-4 w-4" />
        Analyzing BRD for file suggestions…
      </div>
    );
  }

  if (error || total === 0) return null;

  return (
    <div className="rounded-lg border bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800 overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer select-none"
        onClick={() => setExpanded(v => !v)}
      >
        <div className="flex items-center gap-2">
          <FolderCode className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
            {pending.length > 0
              ? `${pending.length} file${pending.length > 1 ? "s" : ""} suggested for upload`
              : "All suggested files uploaded"}
          </span>
          {fulfilled.length > 0 && (
            <Badge variant="outline" className="text-xs border-green-500 text-green-700 dark:text-green-400">
              {fulfilled.length} fulfilled
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => { e.stopPropagation(); requestRefresh(); }}
            disabled={loading}
            className="h-7 px-2 text-xs text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900"
          >
            <RefreshCw className={`h-3 w-3 mr-1 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          {expanded ? <ChevronUp className="h-4 w-4 text-blue-600" /> : <ChevronDown className="h-4 w-4 text-blue-600" />}
        </div>
      </div>

      {/* Expanded list */}
      {expanded && (
        <div className="border-t border-blue-200 dark:border-blue-800 divide-y divide-blue-100 dark:divide-blue-900">
          {suggestions.map(s => (
            <SuggestionRow key={s.id} suggestion={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function SuggestionRow({ suggestion: s }: { suggestion: FileSuggestion }) {
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      {s.fulfilled ? (
        <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
      ) : (
        <FolderCode className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-mono font-medium ${s.fulfilled ? "text-muted-foreground line-through" : "text-foreground"}`}>
          {s.suggested_filename}
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">{s.reason}</p>
      </div>
      <Badge variant="secondary" className="text-xs shrink-0">
        {s.atom_count} atom{s.atom_count !== 1 ? "s" : ""}
      </Badge>
    </div>
  );
}
