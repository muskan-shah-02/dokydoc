"use client";

/**
 * P5C-07: MismatchSuggestedFix
 * Shows AI-generated code fix suggestion for a mismatch.
 * Loads lazily when the user expands the panel; caches in backend.
 */

import { useState } from "react";
import { Lightbulb, Copy, RefreshCw, ChevronDown, ChevronUp, AlertTriangle, CheckCircle2 } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

const CONFIDENCE_CONFIG = {
  high: { color: "text-green-600 bg-green-50 dark:bg-green-950/30", label: "High confidence" },
  medium: { color: "text-amber-600 bg-amber-50 dark:bg-amber-950/30", label: "Medium confidence" },
  low: { color: "text-muted-foreground bg-muted", label: "Low confidence" },
} as const;

interface Fix {
  summary?: string;
  code_snippet?: string;
  language?: string;
  confidence?: keyof typeof CONFIDENCE_CONFIG;
  caveat?: string;
  error?: string;
  generated_at?: string;
}

interface Props {
  mismatchId: number;
  existingFix?: Fix;
}

export function MismatchSuggestedFix({ mismatchId, existingFix }: Props) {
  const [open, setOpen] = useState(false);
  const [fix, setFix] = useState<Fix | null>(existingFix || null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadFix = async (forceRegenerate = false) => {
    if (forceRegenerate) {
      try {
        await fetch(`${API_BASE_URL}/validation/mismatches/${mismatchId}/suggest-fix`, {
          method: "DELETE",
          credentials: "include",
        });
        setFix(null);
      } catch {
        // ignore
      }
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/validation/mismatches/${mismatchId}/suggest-fix`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setFix(data.suggested_fix);
      }
    } finally {
      setLoading(false);
    }
  };

  const copySnippet = () => {
    if (fix?.code_snippet) {
      navigator.clipboard.writeText(fix.code_snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="border-t mt-3 pt-3">
      <button
        onClick={() => {
          const next = !open;
          setOpen(next);
          if (next && !fix) loadFix();
        }}
        className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400 hover:text-amber-900 dark:hover:text-amber-300 w-full"
      >
        <Lightbulb className="h-4 w-4 shrink-0" />
        <span>Suggested Fix</span>
        {open ? (
          <ChevronUp className="h-3.5 w-3.5 ml-auto" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 ml-auto" />
        )}
      </button>

      {open && (
        <div className="mt-3 rounded-md border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/20 p-3 space-y-3">
          {loading && (
            <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400">
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              Generating AI fix suggestion…
            </div>
          )}

          {fix && !loading && (
            <>
              {fix.summary && (
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium text-amber-900 dark:text-amber-200">{fix.summary}</p>
                  {fix.confidence && (
                    <span className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${CONFIDENCE_CONFIG[fix.confidence]?.color}`}>
                      {CONFIDENCE_CONFIG[fix.confidence]?.label}
                    </span>
                  )}
                </div>
              )}

              {fix.code_snippet && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono text-amber-600 dark:text-amber-400">{fix.language}</span>
                    <button
                      onClick={copySnippet}
                      className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 hover:text-amber-800"
                    >
                      {copied ? <CheckCircle2 className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
                      {copied ? "Copied" : "Copy"}
                    </button>
                  </div>
                  <pre className="bg-white dark:bg-black border border-amber-200 dark:border-amber-700 rounded p-2 text-xs overflow-x-auto whitespace-pre-wrap">
                    <code>{fix.code_snippet}</code>
                  </pre>
                </div>
              )}

              {fix.caveat && (
                <div className="flex items-start gap-2 text-xs text-amber-700 dark:text-amber-400">
                  <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                  <span>{fix.caveat}</span>
                </div>
              )}

              {fix.error && !fix.summary && (
                <p className="text-xs text-muted-foreground italic">{fix.error}</p>
              )}

              <button
                onClick={() => loadFix(true)}
                className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 hover:text-amber-800"
              >
                <RefreshCw className="h-3 w-3" />
                Regenerate suggestion
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
