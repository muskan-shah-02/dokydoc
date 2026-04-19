"use client";

import { useState } from "react";
import { Loader2, CheckCircle, AlertCircle, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useTaskStatus } from "@/hooks/useDataFlow";
import { API_BASE_URL } from "@/lib/api";

interface BackfillProgressCardProps {
  repositoryId: number;
}

/**
 * P3.12: Admin card for triggering + monitoring data-flow edge backfill.
 * Shows a progress bar while the Celery task is running.
 */
export function BackfillProgressCard({ repositoryId }: BackfillProgressCardProps) {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { status } = useTaskStatus(taskId);

  const trigger = async () => {
    setTriggering(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE_URL}/repositories/${repositoryId}/data-flow/backfill`,
        { method: "POST", credentials: "include" }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setTaskId(data.task_id);
    } catch (e: any) {
      setError(e?.message ?? "Failed to trigger backfill");
    } finally {
      setTriggering(false);
    }
  };

  const meta = status?.meta as Record<string, any> | null;
  const processed = meta?.processed ?? 0;
  const total = meta?.total ?? 0;
  const edgesWritten = meta?.edges_written ?? 0;
  const pct = total > 0 ? Math.round((processed / total) * 100) : 0;

  return (
    <Card className="border border-violet-100 bg-violet-50/20">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold flex items-center gap-2 text-violet-800">
          <RefreshCw className="w-4 h-4" /> Data Flow Edge Backfill
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!taskId && (
          <>
            <p className="text-xs text-gray-600">
              Re-derive data flow edges for all analyzed components in this repository.
            </p>
            {error && (
              <p className="text-xs text-red-500 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> {error}
              </p>
            )}
            <Button
              size="sm"
              variant="outline"
              className="border-violet-300 text-violet-700 hover:bg-violet-100"
              onClick={trigger}
              disabled={triggering}
            >
              {triggering ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
              {triggering ? "Starting…" : "Run Backfill"}
            </Button>
          </>
        )}

        {taskId && status && (
          <div className="space-y-2">
            {status.state === "PROGRESS" && (
              <>
                <p className="text-xs text-gray-600">
                  Processing {processed} / {total} components…
                </p>
                <Progress value={pct} className="h-2" />
                <p className="text-xs text-violet-700">{edgesWritten} edges written so far</p>
              </>
            )}
            {status.state === "SUCCESS" && (
              <div className="flex items-center gap-2 text-green-700 text-sm">
                <CheckCircle className="w-4 h-4" />
                Done — {meta?.edges_written ?? 0} edges written across {meta?.processed ?? 0} components.
              </div>
            )}
            {status.state === "FAILURE" && (
              <div className="flex items-center gap-2 text-red-600 text-sm">
                <AlertCircle className="w-4 h-4" />
                Backfill failed: {meta?.error ?? "unknown error"}
              </div>
            )}
            {["PENDING", "STARTED"].includes(status.state) && (
              <div className="flex items-center gap-2 text-gray-500 text-sm">
                <Loader2 className="w-4 h-4 animate-spin" /> Queued…
              </div>
            )}
            {(status.ready) && (
              <Button
                size="sm"
                variant="ghost"
                className="text-xs text-gray-500 mt-1"
                onClick={() => { setTaskId(null); setError(null); }}
              >
                Run again
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
