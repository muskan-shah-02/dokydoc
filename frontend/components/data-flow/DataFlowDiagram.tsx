"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Loader2, GitMerge, List, Network, AlertCircle,
  RefreshCw, Eye, Clock,
} from "lucide-react";
import { PremiumGateCard } from "./PremiumGateCard";
import { EdgeListPanel } from "./EdgeListPanel";
import {
  useEgocentricFlow, useRequestTrace, useTaskStatus,
} from "@/hooks/useDataFlow";
import { API_BASE_URL } from "@/lib/api";

declare global {
  interface Window {
    dokydocClick?: (nodeId: string) => void;
  }
}

// GAP-13: userRole as string; auto-detect default mode
const BUSINESS_ROLES = new Set(["ba", "business_analyst", "pm", "product_manager", "cxo", "vp"]);
const PREMIUM_TIERS = new Set(["professional", "pro", "enterprise"]);

function detectDefaultMode(userRole?: string): "technical" | "simple" {
  if (!userRole) return "technical";
  return BUSINESS_ROLES.has(userRole.toLowerCase().replace(/\s/g, "_"))
    ? "simple" : "technical";
}

function formatRelativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

interface DataFlowDiagramProps {
  componentId: number;
  fileRole?: string | null;
  /** GAP-13: singular string role */
  userRole?: string;
  tenantTier?: string | null;
}

export function DataFlowDiagram({
  componentId, fileRole, userRole, tenantTier,
}: DataFlowDiagramProps) {
  // GAP-13: auto-detect mode from userRole
  const [mode, setMode] = useState<"technical" | "simple">(
    () => detectDefaultMode(userRole),
  );
  const [view, setView] = useState<"egocentric" | "trace">("egocentric");
  // GAP-6: trace depth selector
  const [traceDepth, setTraceDepth] = useState<number>(5);
  const [focusedId, setFocusedId] = useState<number>(componentId);
  const [rebuildTaskId, setRebuildTaskId] = useState<string | null>(null);
  const [rebuildError, setRebuildError] = useState<string | null>(null);
  const mermaidRef = useRef<HTMLDivElement>(null);

  const ego = useEgocentricFlow(focusedId, mode);
  const trace = useRequestTrace(
    view === "trace" ? focusedId : null,
    mode,
    traceDepth,
  );
  // GAP-6: smart rebuild polling
  const { status: rebuildStatus } = useTaskStatus(rebuildTaskId);

  const activeData = view === "trace" ? trace : ego;
  const { data, loading, error } = activeData;

  // When rebuild succeeds, reload diagrams
  useEffect(() => {
    if (rebuildStatus?.state === "SUCCESS") {
      setRebuildTaskId(null);
      ego.reload();
      if (view === "trace") trace.reload?.();
    } else if (rebuildStatus?.state === "FAILURE") {
      setRebuildError(rebuildStatus.meta?.error ?? "Rebuild failed");
      setRebuildTaskId(null);
    }
  }, [rebuildStatus?.state]);

  const handleRebuild = useCallback(async () => {
    setRebuildError(null);
    try {
      const res = await fetch(
        `${API_BASE_URL}/code-components/${componentId}/data-flow/rebuild`,
        { method: "POST", credentials: "include" },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setRebuildTaskId(json.task_id);
    } catch (e: any) {
      setRebuildError(e?.message ?? "Failed to start rebuild");
    }
  }, [componentId]);

  // Wire Mermaid click → node navigation
  useEffect(() => {
    window.dokydocClick = (nodeId: string) => {
      const id = parseInt(nodeId, 10);
      if (!isNaN(id)) setFocusedId(id);
    };
    return () => { delete window.dokydocClick; };
  }, []);

  // Render Mermaid markup
  useEffect(() => {
    if (!mermaidRef.current) return;
    const mermaidSrc =
      view === "trace"
        ? (mode === "technical" ? data?.mermaid_technical : data?.mermaid_simple)
        : (mode === "technical" ? data?.mermaid_technical : data?.mermaid_simple);
    if (!mermaidSrc) return;
    const el = mermaidRef.current;
    el.removeAttribute("data-processed");
    el.innerHTML = mermaidSrc;
    import("mermaid").then((m) => {
      m.default.initialize({ startOnLoad: false, securityLevel: "loose" });
      m.default.init(undefined, el);
    });
  }, [data?.mermaid_technical, data?.mermaid_simple, mode, view]);

  if (!PREMIUM_TIERS.has((tenantTier ?? "free").toLowerCase())) {
    return <PremiumGateCard currentTier={tenantTier} />;
  }

  const isRebuilding = rebuildTaskId != null;
  const rebuildProgress = rebuildStatus?.state === "PROGRESS"
    ? rebuildStatus.meta : null;
  const isPremiumError = (error as any)?.type === "PREMIUM_REQUIRED";

  // GAP-6: edges_built_at from response
  const edgesBuiltAt: string | null =
    (data as any)?.edges_built_at ?? null;

  // GAP-6: distinguish "never built" vs "0 edges"
  const neverBuilt = !loading && !error && data && !edgesBuiltAt &&
    (data.edges?.length === 0 || (data as any).total_edges === 0);
  const zeroEdges = !loading && !error && data && edgesBuiltAt &&
    (data.edges?.length === 0 || (data as any).total_edges === 0);

  return (
    <Card className="border border-violet-100">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Network className="w-5 h-5 text-violet-600" />
              Request Data Flow
            </CardTitle>
            <CardDescription className="text-xs mt-0.5 flex items-center gap-2">
              Deterministic — derived from code analysis, zero extra AI cost.
              {/* GAP-6: edges_built_at */}
              {edgesBuiltAt && (
                <span className="flex items-center gap-1 text-gray-400">
                  <Clock className="w-3 h-3" />
                  Built {formatRelativeTime(edgesBuiltAt)}
                </span>
              )}
            </CardDescription>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* Mode toggle */}
            <div className="flex rounded-md border overflow-hidden text-xs">
              {(["technical", "simple"] as const).map((m) => (
                <button
                  key={m}
                  className={`px-3 py-1.5 capitalize ${mode === m
                    ? "bg-violet-600 text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"}`}
                  onClick={() => setMode(m)}
                >
                  {m}
                </button>
              ))}
            </div>

            {/* View toggle */}
            <div className="flex rounded-md border overflow-hidden text-xs">
              <button
                className={`px-3 py-1.5 ${view === "egocentric"
                  ? "bg-violet-600 text-white"
                  : "bg-white text-gray-600 hover:bg-gray-50"}`}
                onClick={() => setView("egocentric")}
              >
                <Eye className="w-3 h-3 inline mr-1" />1-hop
              </button>
              <button
                className={`px-3 py-1.5 ${view === "trace"
                  ? "bg-violet-600 text-white"
                  : "bg-white text-gray-600 hover:bg-gray-50"}`}
                onClick={() => setView("trace")}
              >
                <GitMerge className="w-3 h-3 inline mr-1" />Full Trace
              </button>
            </div>

            {/* GAP-6: Trace depth selector */}
            {view === "trace" && (
              <Select
                value={String(traceDepth)}
                onValueChange={(v) => setTraceDepth(Number(v))}
              >
                <SelectTrigger className="h-7 w-24 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="3">Depth 3</SelectItem>
                  <SelectItem value="5">Depth 5</SelectItem>
                  <SelectItem value="8">Depth 8</SelectItem>
                </SelectContent>
              </Select>
            )}

            {/* Rebuild button with smart polling */}
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 gap-1"
              onClick={handleRebuild}
              disabled={isRebuilding || loading}
              title="Re-derive edges from latest analysis"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRebuilding ? "animate-spin text-violet-600" : ""}`} />
              {isRebuilding ? "Rebuilding…" : "Rebuild"}
            </Button>
          </div>
        </div>

        {/* Rebuild progress bar */}
        {isRebuilding && rebuildProgress && (
          <div className="mt-2 space-y-1">
            <div className="flex justify-between text-xs text-gray-500">
              <span>Processing: {rebuildProgress.current_component ?? "…"}</span>
              <span>{rebuildProgress.edges_written ?? 0} edges written</span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-1.5">
              <div
                className="bg-violet-500 h-1.5 rounded-full transition-all"
                style={{
                  width: `${rebuildProgress.total > 0
                    ? Math.round((rebuildProgress.processed / rebuildProgress.total) * 100)
                    : 0}%`,
                }}
              />
            </div>
          </div>
        )}

        {rebuildError && (
          <p className="text-xs text-red-500 mt-1 flex items-center gap-1">
            <AlertCircle className="w-3 h-3" /> {rebuildError}
          </p>
        )}

        {focusedId !== componentId && (
          <div className="flex items-center gap-2 mt-2">
            <Badge variant="outline" className="text-xs">Viewing: #{focusedId}</Badge>
            <button
              className="text-xs text-violet-600 hover:underline"
              onClick={() => setFocusedId(componentId)}
            >
              ← Back to root
            </button>
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-4">
        {loading && (
          <div className="flex items-center justify-center py-12 text-gray-400">
            <Loader2 className="w-6 h-6 animate-spin mr-2" /> Building diagram…
          </div>
        )}

        {!loading && isPremiumError && <PremiumGateCard currentTier={tenantTier} />}

        {!loading && error && !isPremiumError && (
          <div className="flex items-center gap-2 text-red-600 text-sm py-6 justify-center">
            <AlertCircle className="w-4 h-4" />
            Failed to load data flow: {(error as any)?.message ?? "unknown error"}
          </div>
        )}

        {/* GAP-6: Never built state */}
        {neverBuilt && (
          <div className="text-center py-10 space-y-3">
            <Network className="w-12 h-12 text-gray-300 mx-auto" />
            <p className="text-sm text-gray-500 font-medium">No data flow diagram yet</p>
            <p className="text-xs text-gray-400">
              Click &quot;Rebuild&quot; to derive edges from this component&apos;s analysis.
            </p>
            <Button size="sm" variant="outline" onClick={handleRebuild} disabled={isRebuilding}>
              <RefreshCw className="w-3 h-3 mr-1" /> Build Diagram
            </Button>
          </div>
        )}

        {/* GAP-6: Zero edges but previously built */}
        {zeroEdges && (
          <div className="text-center py-10 space-y-2">
            <p className="text-sm text-gray-500">No connections found in this component.</p>
            <p className="text-xs text-gray-400">
              This may be a config/test file with no cross-file calls.
              Re-analyze the component to pick up new connections.
            </p>
          </div>
        )}

        {!loading && !error && data && !neverBuilt && !zeroEdges && (
          <Tabs defaultValue="diagram" className="space-y-3">
            <TabsList className="h-8 text-xs">
              <TabsTrigger value="diagram" className="h-7 px-3">
                <Network className="w-3 h-3 mr-1" /> Diagram
              </TabsTrigger>
              <TabsTrigger value="edges" className="h-7 px-3">
                <List className="w-3 h-3 mr-1" /> Edge List
              </TabsTrigger>
            </TabsList>

            <TabsContent value="diagram">
              <div className="overflow-x-auto rounded-lg border bg-gray-50 p-4 min-h-[200px]">
                <div
                  ref={mermaidRef}
                  className="mermaid text-sm"
                  style={{ minHeight: "160px" }}
                />
              </div>
              {data.nodes && data.nodes.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {data.nodes.map((n: any) => (
                    <button
                      key={n.component_id || n.id}
                      className="text-xs px-2 py-1 rounded border hover:bg-violet-50 text-gray-600 truncate max-w-[160px]"
                      title={n.location}
                      onClick={() => n.component_id && setFocusedId(n.component_id)}
                    >
                      {n.name}
                    </button>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="edges">
              <EdgeListPanel
                edges={
                  view === "trace"
                    ? (data as any).edges ?? []
                    : [...((data as any).edges_in ?? []), ...((data as any).edges_out ?? [])]
                }
                nodes={data.nodes ?? []}
                focusedComponentId={focusedId}
                onNodeClick={setFocusedId}
              />
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
