// This is the updated content for your file at:
// frontend/app/dashboard/code/[id]/page.tsx

"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  Trash2,
  IndianRupee,
  Cpu,
  Network,
  History,
  GitBranch,
  Sparkles,
  Play,
  BrainCircuit,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// --- NEW: Import our specialized analysis view components ---
import { RepositoryAnalysisView } from "@/components/analysis/RepositoryAnalysisView";
import { FileAnalysisView } from "@/components/analysis/FileAnalysisView";
import { OntologyGraph } from "@/components/ontology/OntologyGraph";
import { GraphVersionPanel } from "@/components/ontology/GraphVersionPanel";
import { BranchPreviewGraph } from "@/components/ontology/BranchPreviewGraph";
import { api, API_BASE_URL } from "@/lib/api";

interface CodeComponentDetail {
  id: number;
  name: string;
  component_type: string;
  location: string;
  version: string;
  summary: string | null;
  structured_analysis: Record<string, any> | null;
  analysis_status: "pending" | "processing" | "completed" | "failed";
  ai_cost_inr: number | null;
  token_count_input: number | null;
  token_count_output: number | null;
  cost_breakdown: Record<string, any> | null;
}

export default function CodeComponentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id;

  const [component, setComponent] = useState<CodeComponentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [graphData, setGraphData] = useState<{ nodes: any[]; edges: any[] } | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphSelectedId, setGraphSelectedId] = useState<number | null>(null);
  const [domainData, setDomainData] = useState<any>(null);
  const [systemData, setSystemData] = useState<any>(null);
  const [versionPanelOpen, setVersionPanelOpen] = useState(false);
  const [branchData, setBranchData] = useState<any>(null);
  const [branchList, setBranchList] = useState<any[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string | null>(null);
  const [branchLoading, setBranchLoading] = useState(false);
  const [synthesisData, setSynthesisData] = useState<any>(null);
  const [synthesisLoading, setSynthesisLoading] = useState(false);
  const [synthesisTriggering, setSynthesisTriggering] = useState(false);
  const [extracting, setExtracting] = useState(false);

  const fetchSynthesis = async (repoId: string) => {
    setSynthesisLoading(true);
    try {
      const data = await api.get<any>(`/repositories/${repoId}/synthesis`);
      setSynthesisData(data);
    } catch { setSynthesisData(null); }
    finally { setSynthesisLoading(false); }
  };

  const triggerSynthesis = async (repoId: string) => {
    setSynthesisTriggering(true);
    try {
      await api.post(`/repositories/${repoId}/synthesize`, {});
      // Poll for completion
      setTimeout(() => fetchSynthesis(repoId), 3000);
    } catch { /* ignore */ }
    finally { setSynthesisTriggering(false); }
  };

  const triggerExtraction = async (compId: string, compType: string) => {
    setExtracting(true);
    try {
      const endpoint = compType === "Repository"
        ? `/ontology/extract/repository/${compId}`
        : `/ontology/extract/repository/${compId}`;
      await api.post(endpoint, {});
      setTimeout(() => {
        fetchGraph(compId);
        setExtracting(false);
      }, 3000);
    } catch { setExtracting(false); }
  };

  const fetchBranches = async (repoId: string) => {
    try {
      const data = await api.get<any[]>(`/ontology/graph/branches/${repoId}`);
      setBranchList(data);
    } catch { setBranchList([]); }
  };

  const fetchBranchPreview = async (repoId: string, branch: string) => {
    setBranchLoading(true);
    try {
      const data = await api.get<any>(`/ontology/graph/preview/${repoId}/${branch}`);
      setBranchData(data);
    } catch { setBranchData(null); }
    finally { setBranchLoading(false); }
  };

  const fetchGraph = async (compId: string) => {
    setGraphLoading(true);
    try {
      const data = await api.get<any>(`/ontology/graph/component/${compId}`);
      setGraphData(data);
    } catch { setGraphData(null); }
    finally { setGraphLoading(false); }
  };

  const fetchDomainGraph = async (repoId: number) => {
    try {
      const data = await api.get<any>(`/ontology/graph/domain/${repoId}`);
      setDomainData(data);
    } catch { setDomainData(null); }
  };

  const fetchSystemGraph = async (repoId: number) => {
    try {
      const data = await api.get<any>(`/ontology/graph/system/${repoId}`);
      setSystemData(data);
    } catch { setSystemData(null); }
  };

  const getStatusIcon = (status: CodeComponentDetail["analysis_status"]) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case "processing":
        return <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />;
      case "failed":
        return <XCircle className="w-5 h-5 text-red-600" />;
      default:
        return <Clock className="w-5 h-5 text-gray-500" />;
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setError("Authentication token not found.");
      setIsDeleting(false);
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE_URL}/code-components/${id}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to delete component.");
      }
      router.push("/dashboard/code");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsDeleting(false);
    }
  };

  useEffect(() => {
    if (!id) return;
    const fetchComponentDetail = async () => {
      const token = localStorage.getItem("accessToken");
      if (!token) {
        setError("Authentication token not found. Please log in again.");
        setLoading(false);
        return;
      }
      try {
        const res = await fetch(
          `${API_BASE_URL}/code-components/${id}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        if (!res.ok) {
          const errorData = await res.json();
          throw new Error(
            errorData.detail ||
              `Failed to fetch component details: ${res.statusText}`
          );
        }
        const data = await res.json();
        setComponent(data);
        setError(null);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchComponentDetail();
    const interval = setInterval(() => {
      if (
        component &&
        (component.analysis_status === "pending" ||
          component.analysis_status === "processing")
      ) {
        fetchComponentDetail();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [id, component?.analysis_status]);

  // --- NEW: Component to intelligently render the correct analysis view ---
  const AnalysisResult = () => {
    if (
      component?.analysis_status !== "completed" ||
      !component?.structured_analysis
    ) {
      return (
        <Card>
          <CardHeader>
            <CardTitle>Analysis In Progress</CardTitle>
            <CardDescription>
              The AI analysis for this component is not yet complete. The status
              is currently: {component?.analysis_status}. This page will
              automatically refresh when the analysis is done.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center p-8">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          </CardContent>
        </Card>
      );
    }

    switch (component.component_type) {
      case "Repository":
        return (
          <RepositoryAnalysisView analysis={component.structured_analysis} />
        );
      case "File":
      case "Class":
      case "Function":
        return (
          <FileAnalysisView
            analysis={component.structured_analysis}
            fileName={component.name}
          />
        );
      default:
        return (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Unsupported Component Type</AlertTitle>
            <AlertDescription>
              A detailed view for component type "{component.component_type}"
              has not been implemented yet.
            </AlertDescription>
          </Alert>
        );
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!component) {
    return <div className="p-6">Component not found.</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">{component.name}</h1>
          <p className="text-lg text-muted-foreground">
            {component.component_type}
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 p-2 bg-muted rounded-lg">
            {getStatusIcon(component.analysis_status)}
            <span className="font-semibold capitalize">
              {component.analysis_status}
            </span>
          </div>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="icon">
                <Trash2 className="w-4 h-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                <AlertDialogDescription>
                  This action cannot be undone. This will permanently delete the
                  code component and all of its associated data.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleDelete} disabled={isDeleting}>
                  {isDeleting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Continue
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>AI-Generated Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground italic">
            {component.summary ||
              "No summary available. Analysis may be pending or failed."}
          </p>
        </CardContent>
      </Card>

      <Tabs defaultValue="analysis" className="space-y-4" onValueChange={(v) => {
        if (v === "graph" && !graphData && id) fetchGraph(String(id));
        if (v === "domains" && !domainData && component?.component_type === "Repository")
          fetchDomainGraph(Number(id));
        if (v === "system" && !systemData && component?.component_type === "Repository")
          fetchSystemGraph(Number(id));
        if (v === "branches" && branchList.length === 0 && component?.component_type === "Repository")
          fetchBranches(String(id));
        if (v === "synthesis" && !synthesisData && component?.component_type === "Repository")
          fetchSynthesis(String(id));
      }}>
        <TabsList className="bg-white border shadow-sm p-1 h-12 w-full justify-start">
          <TabsTrigger value="analysis" className="data-[state=active]:bg-blue-50 data-[state=active]:text-blue-700 h-10 px-6">
            <Cpu className="w-4 h-4 mr-2" /> Analysis
          </TabsTrigger>
          <TabsTrigger value="graph" className="data-[state=active]:bg-purple-50 data-[state=active]:text-purple-700 h-10 px-6">
            <Network className="w-4 h-4 mr-2" /> Knowledge Graph
          </TabsTrigger>
          {component.component_type === "Repository" && (
            <>
              <TabsTrigger value="domains" className="data-[state=active]:bg-green-50 data-[state=active]:text-green-700 h-10 px-6">
                <Network className="w-4 h-4 mr-2" /> Domain Map
              </TabsTrigger>
              <TabsTrigger value="system" className="data-[state=active]:bg-amber-50 data-[state=active]:text-amber-700 h-10 px-6">
                <Cpu className="w-4 h-4 mr-2" /> System Architecture
              </TabsTrigger>
              <TabsTrigger value="branches" className="data-[state=active]:bg-cyan-50 data-[state=active]:text-cyan-700 h-10 px-6">
                <GitBranch className="w-4 h-4 mr-2" /> Branch Preview
              </TabsTrigger>
              <TabsTrigger value="synthesis" className="data-[state=active]:bg-pink-50 data-[state=active]:text-pink-700 h-10 px-6">
                <Sparkles className="w-4 h-4 mr-2" /> Synthesis
              </TabsTrigger>
            </>
          )}
        </TabsList>

        <TabsContent value="analysis" className="space-y-6">
          {/* Cost Summary */}
          {component.ai_cost_inr != null && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <IndianRupee className="w-5 h-5 mr-2 text-green-600" />
                  Analysis Cost
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg text-center">
                    <p className="text-sm text-muted-foreground">Total Cost</p>
                    <p className="text-2xl font-bold text-green-700 dark:text-green-400">
                      ₹{component.ai_cost_inr.toFixed(2)}
                    </p>
                  </div>
                  <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-center">
                    <p className="text-sm text-muted-foreground">Input Tokens</p>
                    <p className="text-2xl font-bold text-blue-700 dark:text-blue-400">
                      {component.token_count_input?.toLocaleString() || "—"}
                    </p>
                  </div>
                  <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg text-center">
                    <p className="text-sm text-muted-foreground">Output Tokens</p>
                    <p className="text-2xl font-bold text-purple-700 dark:text-purple-400">
                      {component.token_count_output?.toLocaleString() || "—"}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
          <AnalysisResult />
        </TabsContent>

        <TabsContent value="graph">
          {/* Extraction + Version History buttons */}
          <div className="flex justify-end gap-2 mb-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => id && component && triggerExtraction(String(id), component.component_type)}
              disabled={extracting}
              className="gap-1.5 text-xs"
            >
              {extracting ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <BrainCircuit className="w-3.5 h-3.5" />
              )}
              {extracting ? "Extracting..." : "Extract BOE"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setVersionPanelOpen(true)}
              className="gap-1.5 text-xs"
            >
              <History className="w-3.5 h-3.5" />
              Version History
            </Button>
          </div>
          {graphLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="w-6 h-6 animate-spin text-purple-600" />
              <span className="ml-2 text-sm text-gray-500">Loading knowledge graph...</span>
            </div>
          ) : graphData && graphData.nodes.length > 0 ? (
            <OntologyGraph nodes={graphData.nodes} edges={graphData.edges}
              selectedId={graphSelectedId} onSelectNode={setGraphSelectedId} />
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-gray-400">
              <Network className="w-12 h-12 mb-3" />
              <p className="text-sm font-medium">No concepts extracted yet</p>
              <p className="text-xs mt-1">Concepts appear after analysis + BOE extraction</p>
            </div>
          )}
          {/* Graph Version Panel (slide-over) */}
          <GraphVersionPanel
            sourceType="component"
            sourceId={Number(id)}
            isOpen={versionPanelOpen}
            onClose={() => setVersionPanelOpen(false)}
          />
        </TabsContent>

        {component.component_type === "Repository" && (
          <>
            <TabsContent value="domains">
              {domainData && domainData.nodes.length > 0 ? (
                <div className="space-y-4">
                  <div className="flex gap-2 flex-wrap">
                    {domainData.domains.map((d: any) => (
                      <span key={d.name} className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200">
                        {d.name} ({d.concept_count} concepts, {d.file_count} files)
                      </span>
                    ))}
                  </div>
                  <OntologyGraph
                    nodes={domainData.nodes.map((n: any) => ({ ...n, concept_type: n.domain || n.concept_type }))}
                    edges={domainData.edges}
                    selectedId={graphSelectedId}
                    onSelectNode={setGraphSelectedId}
                  />
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                  <Network className="w-12 h-12 mb-3" />
                  <p className="text-sm font-medium">No domain data available</p>
                  <p className="text-xs mt-1">Analyze files in this repository first</p>
                </div>
              )}
            </TabsContent>

            <TabsContent value="system">
              {systemData && systemData.system_nodes.length > 0 ? (
                <div className="space-y-4">
                  {systemData.synthesis_summary && (
                    <Card>
                      <CardHeader><CardTitle className="text-sm">System Summary</CardTitle></CardHeader>
                      <CardContent><p className="text-sm text-muted-foreground">{systemData.synthesis_summary}</p></CardContent>
                    </Card>
                  )}
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                    {systemData.system_nodes.map((sn: any) => (
                      <Card key={sn.domain_name} className="hover:shadow-md transition-shadow cursor-pointer">
                        <CardContent className="p-4">
                          <h3 className="font-semibold text-sm truncate">{sn.domain_name}</h3>
                          <div className="flex gap-3 mt-2 text-xs text-muted-foreground">
                            <span>{sn.file_count} files</span>
                            <span>{sn.concept_count} concepts</span>
                          </div>
                          {sn.key_concepts.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {sn.key_concepts.slice(0, 3).map((kc: string) => (
                                <span key={kc} className="text-[10px] px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded">
                                  {kc.length > 20 ? kc.slice(0, 18) + "…" : kc}
                                </span>
                              ))}
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                  {systemData.system_edges.length > 0 && (
                    <Card>
                      <CardHeader><CardTitle className="text-sm">Cross-Domain Relationships</CardTitle></CardHeader>
                      <CardContent>
                        <div className="space-y-1">
                          {systemData.system_edges.map((e: any, i: number) => (
                            <div key={i} className="flex items-center gap-2 text-xs">
                              <span className="font-medium text-blue-700">{e.source_domain}</span>
                              <span className="text-gray-400">→</span>
                              <span className="font-medium text-blue-700">{e.target_domain}</span>
                              <span className="text-gray-500">({e.relationship_count} relationships)</span>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                  <Cpu className="w-12 h-12 mb-3" />
                  <p className="text-sm font-medium">No system architecture data</p>
                  <p className="text-xs mt-1">Analyze files in this repository first</p>
                </div>
              )}
            </TabsContent>

            <TabsContent value="branches">
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <select
                    className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
                    value={selectedBranch || ""}
                    onChange={(e) => {
                      const branch = e.target.value;
                      setSelectedBranch(branch);
                      if (branch && id) fetchBranchPreview(String(id), branch);
                    }}
                  >
                    <option value="">
                      {branchList.length === 0 ? "No branches available" : "Select a branch..."}
                    </option>
                    {branchList.map((b: any) => (
                      <option key={b.branch} value={b.branch}>{b.branch} ({b.commit_hash?.slice(0, 8)})</option>
                    ))}
                  </select>
                </div>
                {branchLoading ? (
                  <div className="flex items-center justify-center h-64">
                    <Loader2 className="w-6 h-6 animate-spin text-cyan-600" />
                    <span className="ml-2 text-sm text-gray-500">Loading branch preview...</span>
                  </div>
                ) : branchData && branchData.nodes?.length > 0 ? (
                  <div style={{ height: "500px" }}>
                    <BranchPreviewGraph
                      nodes={branchData.nodes}
                      edges={branchData.edges}
                      branch={selectedBranch || ""}
                      commitHash={branchData.commit_hash || ""}
                      changedFiles={branchData.changed_files || []}
                      selectedId={null}
                      onSelectNode={() => {}}
                    />
                  </div>
                ) : selectedBranch ? (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                    <GitBranch className="w-12 h-12 mb-3" />
                    <p className="text-sm font-medium">No preview data for this branch</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                    <GitBranch className="w-12 h-12 mb-3" />
                    <p className="text-sm font-medium">Select a branch to preview its impact</p>
                    <p className="text-xs mt-1">Branch previews show how code changes affect the knowledge graph</p>
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="synthesis">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold">Repository Synthesis</h3>
                    <p className="text-xs text-muted-foreground">AI-generated cross-file synthesis of your repository&apos;s architecture and patterns</p>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => triggerSynthesis(String(id))}
                    disabled={synthesisTriggering}
                    className="gap-1.5"
                  >
                    {synthesisTriggering ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Play className="w-3.5 h-3.5" />
                    )}
                    {synthesisTriggering ? "Running..." : "Run Synthesis"}
                  </Button>
                </div>
                {synthesisLoading ? (
                  <div className="flex items-center justify-center h-64">
                    <Loader2 className="w-6 h-6 animate-spin text-pink-600" />
                    <span className="ml-2 text-sm text-gray-500">Loading synthesis...</span>
                  </div>
                ) : synthesisData?.synthesis ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      <Badge variant={synthesisData.synthesis_status === "completed" ? "default" : "secondary"}>
                        {synthesisData.synthesis_status || "unknown"}
                      </Badge>
                    </div>
                    {synthesisData.synthesis.architecture_summary && (
                      <Card>
                        <CardHeader><CardTitle className="text-sm">Architecture Summary</CardTitle></CardHeader>
                        <CardContent><p className="text-sm text-muted-foreground whitespace-pre-wrap">{synthesisData.synthesis.architecture_summary}</p></CardContent>
                      </Card>
                    )}
                    {synthesisData.synthesis.key_patterns && synthesisData.synthesis.key_patterns.length > 0 && (
                      <Card>
                        <CardHeader><CardTitle className="text-sm">Key Patterns</CardTitle></CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            {synthesisData.synthesis.key_patterns.map((p: any, i: number) => (
                              <div key={i} className="flex items-start gap-2 text-sm">
                                <span className="mt-1 w-1.5 h-1.5 rounded-full bg-pink-500 flex-shrink-0" />
                                <span>{typeof p === "string" ? p : p.name || p.description || JSON.stringify(p)}</span>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    )}
                    {synthesisData.synthesis.cross_cutting_concerns && synthesisData.synthesis.cross_cutting_concerns.length > 0 && (
                      <Card>
                        <CardHeader><CardTitle className="text-sm">Cross-Cutting Concerns</CardTitle></CardHeader>
                        <CardContent>
                          <div className="flex flex-wrap gap-2">
                            {synthesisData.synthesis.cross_cutting_concerns.map((c: string, i: number) => (
                              <Badge key={i} variant="outline">{c}</Badge>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    )}
                    {/* Render any other synthesis sections generically */}
                    {Object.entries(synthesisData.synthesis)
                      .filter(([k]) => !["architecture_summary", "key_patterns", "cross_cutting_concerns"].includes(k))
                      .map(([key, value]) => (
                        <Card key={key}>
                          <CardHeader><CardTitle className="text-sm capitalize">{key.replace(/_/g, " ")}</CardTitle></CardHeader>
                          <CardContent>
                            <pre className="text-xs text-muted-foreground whitespace-pre-wrap overflow-auto max-h-64">
                              {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
                            </pre>
                          </CardContent>
                        </Card>
                      ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                    <Sparkles className="w-12 h-12 mb-3" />
                    <p className="text-sm font-medium">No synthesis available</p>
                    <p className="text-xs mt-1">Click &quot;Run Synthesis&quot; to generate a cross-file analysis</p>
                  </div>
                )}
              </div>
            </TabsContent>
          </>
        )}
      </Tabs>
    </div>
  );
}
