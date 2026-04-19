"use client";

import { useState, useEffect, useRef } from "react";
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from "@/components/ui/tabs";
import { Loader2, GitMerge, List, Network, AlertCircle, RefreshCw, Eye } from "lucide-react";
import { PremiumGateCard } from "./PremiumGateCard";
import { EdgeListPanel } from "./EdgeListPanel";
import { useEgocentricFlow, useRequestTrace } from "@/hooks/useDataFlow";

declare global {
  interface Window {
    dokydocClick?: (nodeId: string) => void;
  }
}

interface DataFlowDiagramProps {
  componentId: number;
  /** file_role from structured_analysis — controls which views are available */
  fileRole?: string | null;
  /** tenant_tier from /users/me — gates premium features */
  tenantTier?: string | null;
}

const PREMIUM_TIERS = new Set(["professional", "pro", "enterprise"]);

function isPremium(tier: string | null | undefined): boolean {
  return PREMIUM_TIERS.has((tier ?? "free").toLowerCase());
}

/**
 * P3.8: Main data flow diagram panel. Renders:
 *   - Mermaid flowchart (egocentric or request-trace)
 *   - Edge list (Calls / Called By)
 *   - PremiumGateCard for free-tier tenants
 */
export function DataFlowDiagram({ componentId, fileRole, tenantTier }: DataFlowDiagramProps) {
  const [mode, setMode] = useState<"technical" | "simple">("technical");
  const [view, setView] = useState<"egocentric" | "trace">("egocentric");
  const [focusedId, setFocusedId] = useState<number>(componentId);
  const mermaidRef = useRef<HTMLDivElement>(null);

  const ego = useEgocentricFlow(focusedId, mode);
  const trace = useRequestTrace(
    view === "trace" ? focusedId : null,
    mode,
  );

  const activeData = view === "trace" ? trace : ego;
  const { data, loading, error } = activeData;

  // Wire Mermaid click callbacks → focusedId navigation.
  useEffect(() => {
    window.dokydocClick = (nodeId: string) => {
      const id = parseInt(nodeId, 10);
      if (!isNaN(id)) setFocusedId(id);
    };
    return () => { delete window.dokydocClick; };
  }, []);

  // Render Mermaid markup whenever it changes.
  useEffect(() => {
    if (!data?.mermaid || !mermaidRef.current) return;
    const el = mermaidRef.current;
    el.removeAttribute("data-processed");
    el.innerHTML = data.mermaid;
    import("mermaid").then((m) => {
      m.default.initialize({ startOnLoad: false, securityLevel: "loose" });
      m.default.init(undefined, el);
    });
  }, [data?.mermaid]);

  // Premium gate
  if (!isPremium(tenantTier)) {
    return <PremiumGateCard currentTier={tenantTier} />;
  }

  const isPremiumError = (error as any)?.type === "PREMIUM_REQUIRED";

  return (
    <Card className="border border-violet-100">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Network className="w-5 h-5 text-violet-600" />
              Request Data Flow
            </CardTitle>
            <CardDescription className="text-xs mt-0.5">
              Deterministic — derived from code analysis, no extra AI cost.
            </CardDescription>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Mode toggle */}
            <div className="flex rounded-md border overflow-hidden text-xs">
              {(["technical", "simple"] as const).map((m) => (
                <button
                  key={m}
                  className={`px-3 py-1.5 capitalize ${mode === m ? "bg-violet-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
                  onClick={() => setMode(m)}
                >
                  {m}
                </button>
              ))}
            </div>

            {/* View toggle — trace only for ENDPOINT role */}
            {fileRole === "ENDPOINT" && (
              <div className="flex rounded-md border overflow-hidden text-xs">
                <button
                  className={`px-3 py-1.5 ${view === "egocentric" ? "bg-violet-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
                  onClick={() => setView("egocentric")}
                >
                  <Eye className="w-3 h-3 inline mr-1" />1-hop
                </button>
                <button
                  className={`px-3 py-1.5 ${view === "trace" ? "bg-violet-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
                  onClick={() => setView("trace")}
                >
                  <GitMerge className="w-3 h-3 inline mr-1" />Full Trace
                </button>
              </div>
            )}

            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2"
              onClick={() => activeData.reload?.()}
              disabled={loading}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {/* Breadcrumb when focused node differs from root */}
        {focusedId !== componentId && (
          <div className="flex items-center gap-2 mt-2">
            <Badge variant="outline" className="text-xs">
              Viewing: #{focusedId}
            </Badge>
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
            <Loader2 className="w-6 h-6 animate-spin mr-2" />
            Building diagram…
          </div>
        )}

        {!loading && isPremiumError && (
          <PremiumGateCard currentTier={tenantTier} />
        )}

        {!loading && error && !isPremiumError && (
          <div className="flex items-center gap-2 text-red-600 text-sm py-6 justify-center">
            <AlertCircle className="w-4 h-4" />
            Failed to load data flow. {error?.message ?? ""}
          </div>
        )}

        {!loading && !error && data && (
          <Tabs defaultValue="diagram" className="space-y-3">
            <TabsList className="h-8 text-xs">
              <TabsTrigger value="diagram" className="h-7 px-3">
                <Network className="w-3 h-3 mr-1" /> Diagram
              </TabsTrigger>
              <TabsTrigger value="edges" className="h-7 px-3">
                <List className="w-3 h-3 mr-1" /> Edge List
              </TabsTrigger>
            </TabsList>

            {/* Mermaid diagram */}
            <TabsContent value="diagram">
              {data.nodes.length === 0 ? (
                <div className="text-sm text-gray-400 italic text-center py-10">
                  No edges found. Re-analyze the component to generate flow data.
                </div>
              ) : (
                <div className="overflow-x-auto rounded-lg border bg-gray-50 p-4 min-h-[200px]">
                  <div
                    ref={mermaidRef}
                    className="mermaid text-sm"
                    style={{ minHeight: "160px" }}
                  />
                </div>
              )}

              {/* Node legend */}
              {data.nodes.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {data.nodes.map((n) => (
                    <button
                      key={n.id}
                      className="text-xs px-2 py-1 rounded border hover:bg-violet-50 text-gray-600 truncate max-w-[160px]"
                      title={n.location}
                      onClick={() => setFocusedId(n.id)}
                    >
                      {n.name}
                    </button>
                  ))}
                </div>
              )}
            </TabsContent>

            {/* Edge list */}
            <TabsContent value="edges">
              <EdgeListPanel
                edges={data.edges}
                nodes={data.nodes}
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
