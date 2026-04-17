"use client";

/**
 * P5C-05: TestSuiteDownload
 * Triggers Gemini test suite generation and downloads the zip.
 * QA can drop the generated pytest files into their CI pipeline.
 */

import { useState } from "react";
import { Download, Loader2, FileCode } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

interface Props {
  documentId: number;
}

export function TestSuiteDownload({ documentId }: Props) {
  const [status, setStatus] = useState<"idle" | "generating">("idle");
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setStatus("generating");
    setError(null);
    try {
      // Trigger generation
      const triggerRes = await fetch(
        `${API_BASE_URL}/validation/${documentId}/generate-tests`,
        { method: "POST", credentials: "include" }
      );
      if (!triggerRes.ok) throw new Error(`Trigger failed: HTTP ${triggerRes.status}`);

      // Poll until ready (max 2 minutes)
      const startTime = Date.now();
      const poll = async () => {
        if (Date.now() - startTime > 120_000) {
          setError("Test suite generation timed out. Please try again.");
          setStatus("idle");
          return;
        }
        const resp = await fetch(
          `${API_BASE_URL}/validation/${documentId}/download-tests`,
          { credentials: "include" }
        );
        if (resp.status === 200) {
          const blob = await resp.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `dokydoc_tests_doc${documentId}.zip`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          setStatus("idle");
        } else {
          setTimeout(poll, 5000);
        }
      };
      await poll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to generate test suite");
      setStatus("idle");
    }
  };

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border border-dashed border-border bg-muted/20">
      <FileCode className="h-5 w-5 text-muted-foreground shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">Auto-generated Test Suite</p>
        <p className="text-xs text-muted-foreground">
          Pytest files from BRD atoms · Drop into CI pipeline
        </p>
        {error && <p className="text-xs text-destructive mt-0.5">{error}</p>}
      </div>
      <button
        onClick={handleGenerate}
        disabled={status === "generating"}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors shrink-0"
      >
        {status === "generating" ? (
          <>
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Generating…
          </>
        ) : (
          <>
            <Download className="h-3.5 w-3.5" />
            Download Tests
          </>
        )}
      </button>
    </div>
  );
}
