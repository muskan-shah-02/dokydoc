"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  FolderKanban,
  ArrowLeft,
  FileText,
  GitBranch,
  Network,
  PlusCircle,
  Trash2,
  Loader2,
  AlertCircle,
  RefreshCw,
  X,
  ExternalLink,
  GitCompare,
} from "lucide-react";
import { api } from "@/lib/api";
import { useProject, Initiative } from "@/contexts/ProjectContext";
import { CrossGraphView } from "@/components/ontology/CrossGraphView";
import { GapAnalysis } from "@/components/ontology/GapAnalysis";
import { RequirementTraceabilityPanel } from "@/components/ontology/RequirementTraceabilityPanel";

interface InitiativeAsset {
  id: number;
  initiative_id: number;
  asset_type: string;
  asset_id: number;
  is_active: boolean;
  created_at: string;
}

interface Document {
  id: number;
  filename: string;
  status: string;
  file_type: string;
  created_at: string;
}

interface Repository {
  id: number;
  name: string;
  url: string;
  analysis_status: string;
  created_at: string;
}

interface OntologyStats {
  total_concepts: number;
  total_relationships: number;
  concept_types: string[];
}

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = Number(params.id);
  const { setSelectedProject } = useProject();

  const [project, setProject] = useState<Initiative | null>(null);
  const [assets, setAssets] = useState<InitiativeAsset[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [ontologyStats, setOntologyStats] = useState<OntologyStats>({
    total_concepts: 0, total_relationships: 0, concept_types: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Alignment (Level 4)
  const [alignmentData, setAlignmentData] = useState<any>(null);
  const [alignmentLoading, setAlignmentLoading] = useState(false);
  const [alignmentOpen, setAlignmentOpen] = useState(false);
  const [selectedMappingId, setSelectedMappingId] = useState<number | null>(null);
  const [mappingRunning, setMappingRunning] = useState(false);
  const [extractionRunning, setExtractionRunning] = useState(false);

  // For linking assets
  const [showLinkDialog, setShowLinkDialog] = useState(false);
  const [linkType, setLinkType] = useState<"DOCUMENT" | "REPOSITORY">("DOCUMENT");
  const [allDocs, setAllDocs] = useState<Document[]>([]);
  const [allRepos, setAllRepos] = useState<Repository[]>([]);
  const [linking, setLinking] = useState(false);

  const fetchProject = useCallback(async () => {
    try {
      const [projectRes, assetsRes, statsRes] = await Promise.all([
        api.get<Initiative>(`/initiatives/${projectId}`),
        api.get<InitiativeAsset[]>(`/initiatives/${projectId}/assets`),
        api.get<OntologyStats>("/ontology/stats", { initiative_id: projectId }),
      ]);
      setProject(projectRes);
      setAssets(assetsRes.filter((a) => a.is_active));
      setOntologyStats(statsRes);
      setSelectedProject(projectRes);

      // Fetch actual document/repo details for linked assets
      const docIds = assetsRes.filter((a) => a.asset_type === "DOCUMENT" && a.is_active).map((a) => a.asset_id);
      const repoIds = assetsRes.filter((a) => a.asset_type === "REPOSITORY" && a.is_active).map((a) => a.asset_id);

      const docs: Document[] = [];
      for (const id of docIds) {
        try {
          const doc = await api.get<Document>(`/documents/${id}`);
          docs.push(doc);
        } catch { /* asset may have been deleted */ }
      }
      setDocuments(docs);

      const repositories: Repository[] = [];
      for (const id of repoIds) {
        try {
          const repo = await api.get<Repository>(`/repositories/${id}`);
          repositories.push(repo);
        } catch { /* asset may have been deleted */ }
      }
      setRepos(repositories);
      setError("");
    } catch (err: any) {
      setError(err.detail || "Failed to load project");
    }
  }, [projectId, setSelectedProject]);

  useEffect(() => {
    setLoading(true);
    fetchProject().finally(() => setLoading(false));
  }, [fetchProject]);

  const handleUnlinkAsset = async (assetLinkId: number) => {
    try {
      await api.delete(`/initiatives/${projectId}/assets/${assetLinkId}`);
      await fetchProject();
    } catch (err: any) {
      setError(err.detail || "Failed to unlink asset");
    }
  };

  const openLinkDialog = async (type: "DOCUMENT" | "REPOSITORY") => {
    setLinkType(type);
    setShowLinkDialog(true);
    try {
      if (type === "DOCUMENT") {
        const docs = await api.get<Document[]>("/documents/", { limit: 200 });
        setAllDocs(docs);
      } else {
        const repos = await api.get<Repository[]>("/repositories/", { limit: 200 });
        setAllRepos(repos);
      }
    } catch { /* ignore */ }
  };

  const fetchAlignment = useCallback(async (forceReload = false) => {
    if (alignmentData && !forceReload) return; // already loaded
    setAlignmentLoading(true);
    try {
      const data = await api.get<any>(`/ontology/graph/alignment/${projectId}`);
      setAlignmentData(data);
    } catch {
      setAlignmentData({ document_nodes: [], code_nodes: [], mappings: [], coverage_stats: null });
    } finally {
      setAlignmentLoading(false);
    }
  }, [projectId, alignmentData]);

  const handleRunMapping = async () => {
    setMappingRunning(true);
    try {
      await api.post("/ontology/run-mapping");
      // Reload alignment data after a brief delay for mapping to complete
      setTimeout(async () => {
        await fetchAlignment(true);
        setMappingRunning(false);
      }, 3000);
    } catch {
      setMappingRunning(false);
    }
  };

  const handleRunExtraction = async () => {
    setExtractionRunning(true);
    try {
      // Trigger extraction for all linked documents and repos
      const docAssets = assets.filter((a) => a.asset_type === "DOCUMENT" && a.is_active);
      const repoAssets = assets.filter((a) => a.asset_type === "REPOSITORY" && a.is_active);
      const promises: Promise<any>[] = [];
      for (const a of docAssets) {
        promises.push(api.post(`/ontology/extract/document/${a.asset_id}`).catch(() => null));
      }
      for (const a of repoAssets) {
        promises.push(api.post(`/ontology/extract/repository/${a.asset_id}`).catch(() => null));
      }
      await Promise.all(promises);
      // After extraction, run mapping
      await api.post("/ontology/run-mapping").catch(() => null);
      setTimeout(async () => {
        await fetchAlignment(true);
        setExtractionRunning(false);
      }, 5000);
    } catch {
      setExtractionRunning(false);
    }
  };

  const handleLinkAsset = async (assetId: number) => {
    setLinking(true);
    try {
      await api.post(`/initiatives/${projectId}/assets?asset_type=${linkType}&asset_id=${assetId}`);
      setShowLinkDialog(false);
      await fetchProject();
    } catch (err: any) {
      setError(err.detail || "Failed to link asset");
    } finally {
      setLinking(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        <p className="ml-2 text-sm text-gray-500">Loading project...</p>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex h-96 flex-col items-center justify-center">
        <AlertCircle className="h-8 w-8 text-red-400" />
        <p className="mt-2 text-sm text-gray-500">Project not found</p>
        <button onClick={() => router.push("/dashboard/projects")} className="mt-3 text-sm text-blue-600 hover:underline">
          Back to Projects
        </button>
      </div>
    );
  }

  const linkedDocIds = new Set(assets.filter((a) => a.asset_type === "DOCUMENT").map((a) => a.asset_id));
  const linkedRepoIds = new Set(assets.filter((a) => a.asset_type === "REPOSITORY").map((a) => a.asset_id));

  return (
    <div className="min-h-screen bg-gray-50/50 p-4 lg:p-6">
      {/* Back + Header */}
      <div className="mb-6">
        <button onClick={() => router.push("/dashboard/projects")} className="mb-3 flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
          <ArrowLeft className="h-4 w-4" /> Back to Projects
        </button>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-blue-50 p-3">
              <FolderKanban className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
              {project.description && (
                <p className="mt-0.5 text-sm text-gray-500">{project.description}</p>
              )}
            </div>
          </div>
          <button onClick={() => { setLoading(true); fetchProject().finally(() => setLoading(false)); }}
            className="flex items-center gap-1.5 rounded-md border bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4" /> {error}
          <button onClick={() => setError("")} className="ml-auto"><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Stats Cards */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500">Documents</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">{documents.length}</p>
            </div>
            <div className="rounded-lg bg-blue-50 p-2.5"><FileText className="h-5 w-5 text-blue-600" /></div>
          </div>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500">Repositories</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">{repos.length}</p>
            </div>
            <div className="rounded-lg bg-green-50 p-2.5"><GitBranch className="h-5 w-5 text-green-600" /></div>
          </div>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500">Ontology Concepts</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">{ontologyStats.total_concepts}</p>
            </div>
            <div className="rounded-lg bg-purple-50 p-2.5"><Network className="h-5 w-5 text-purple-600" /></div>
          </div>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500">Relationships</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">{ontologyStats.total_relationships}</p>
            </div>
            <div className="rounded-lg bg-amber-50 p-2.5"><Network className="h-5 w-5 text-amber-600" /></div>
          </div>
        </div>
      </div>

      {/* Documents Section */}
      <div className="mb-6 rounded-lg border bg-white">
        <div className="flex items-center justify-between border-b px-5 py-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            <FileText className="h-4 w-4 text-blue-500" /> Documents
          </h2>
          <button onClick={() => openLinkDialog("DOCUMENT")}
            className="flex items-center gap-1 rounded-md bg-blue-50 px-2.5 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100">
            <PlusCircle className="h-3.5 w-3.5" /> Link Document
          </button>
        </div>
        {documents.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-gray-400">
            No documents linked to this project yet
          </div>
        ) : (
          <div className="divide-y">
            {documents.map((doc) => {
              const assetLink = assets.find((a) => a.asset_type === "DOCUMENT" && a.asset_id === doc.id);
              return (
                <div key={doc.id} className="group flex items-center justify-between px-5 py-3 hover:bg-gray-50">
                  <div className="flex items-center gap-3">
                    <FileText className="h-4 w-4 text-gray-400" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">{doc.filename}</p>
                      <p className="text-xs text-gray-500">{doc.file_type} &middot; {doc.status}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => router.push(`/dashboard/documents/${doc.id}`)}
                      className="rounded-md p-1 text-gray-400 hover:text-blue-500">
                      <ExternalLink className="h-3.5 w-3.5" />
                    </button>
                    {assetLink && (
                      <button onClick={() => handleUnlinkAsset(assetLink.id)}
                        className="hidden rounded-md p-1 text-gray-400 hover:text-red-500 group-hover:block">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Repositories Section */}
      <div className="mb-6 rounded-lg border bg-white">
        <div className="flex items-center justify-between border-b px-5 py-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            <GitBranch className="h-4 w-4 text-green-500" /> Repositories
          </h2>
          <button onClick={() => openLinkDialog("REPOSITORY")}
            className="flex items-center gap-1 rounded-md bg-green-50 px-2.5 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100">
            <PlusCircle className="h-3.5 w-3.5" /> Link Repository
          </button>
        </div>
        {repos.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-gray-400">
            No repositories linked to this project yet
          </div>
        ) : (
          <div className="divide-y">
            {repos.map((repo) => {
              const assetLink = assets.find((a) => a.asset_type === "REPOSITORY" && a.asset_id === repo.id);
              return (
                <div key={repo.id} className="group flex items-center justify-between px-5 py-3 hover:bg-gray-50">
                  <div className="flex items-center gap-3">
                    <GitBranch className="h-4 w-4 text-gray-400" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">{repo.name}</p>
                      <p className="text-xs text-gray-500">{repo.url} &middot; {repo.analysis_status}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => router.push(`/dashboard/code/${repo.id}`)}
                      className="rounded-md p-1 text-gray-400 hover:text-blue-500">
                      <ExternalLink className="h-3.5 w-3.5" />
                    </button>
                    {assetLink && (
                      <button onClick={() => handleUnlinkAsset(assetLink.id)}
                        className="hidden rounded-md p-1 text-gray-400 hover:text-red-500 group-hover:block">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <button
          onClick={() => router.push("/dashboard/ontology")}
          className="flex items-center gap-3 rounded-lg border bg-white p-4 text-left hover:border-purple-300 hover:shadow-sm"
        >
          <div className="rounded-lg bg-purple-50 p-2.5">
            <Network className="h-5 w-5 text-purple-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900">View Ontology Graph</p>
            <p className="text-xs text-gray-500">
              {ontologyStats.total_concepts} concepts, {ontologyStats.total_relationships} relationships
            </p>
          </div>
        </button>
        <button
          onClick={() => router.push("/dashboard/code")}
          className="flex items-center gap-3 rounded-lg border bg-white p-4 text-left hover:border-green-300 hover:shadow-sm"
        >
          <div className="rounded-lg bg-green-50 p-2.5">
            <GitBranch className="h-5 w-5 text-green-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900">Browse Code</p>
            <p className="text-xs text-gray-500">View repositories and code components</p>
          </div>
        </button>
      </div>

      {/* Doc ↔ Code Alignment (Level 4) */}
      <div className="mt-6 rounded-lg border bg-white">
        <button
          onClick={() => {
            const next = !alignmentOpen;
            setAlignmentOpen(next);
            if (next) fetchAlignment();
          }}
          className="flex w-full items-center justify-between border-b px-5 py-3 text-left"
        >
          <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            <GitCompare className="h-4 w-4 text-indigo-500" /> Doc ↔ Code Alignment
          </h2>
          <span className="text-xs text-gray-400">{alignmentOpen ? "Collapse" : "Expand"}</span>
        </button>
        {alignmentOpen && (
          <div className="p-5">
            {alignmentLoading ? (
              <div className="flex h-40 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
                <p className="ml-2 text-sm text-gray-500">Loading alignment data...</p>
              </div>
            ) : alignmentData && (alignmentData.document_nodes?.length > 0 || alignmentData.code_nodes?.length > 0) ? (
              <>
                {/* Coverage Stats */}
                {alignmentData.coverage_stats && (
                  <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div className="rounded-lg border bg-blue-50/60 p-3">
                      <p className="text-xs font-medium text-gray-500">Doc Concepts</p>
                      <p className="mt-1 text-xl font-bold text-gray-900">{alignmentData.coverage_stats.total_doc_concepts}</p>
                    </div>
                    <div className="rounded-lg border bg-green-50/60 p-3">
                      <p className="text-xs font-medium text-gray-500">Code Concepts</p>
                      <p className="mt-1 text-xl font-bold text-gray-900">{alignmentData.coverage_stats.total_code_concepts}</p>
                    </div>
                    <div className="rounded-lg border bg-indigo-50/60 p-3">
                      <p className="text-xs font-medium text-gray-500">Mappings Found</p>
                      <p className="mt-1 text-xl font-bold text-gray-900">{alignmentData.mappings?.length ?? 0}</p>
                    </div>
                    <div className="rounded-lg border bg-amber-50/60 p-3">
                      <p className="text-xs font-medium text-gray-500">Coverage</p>
                      <p className="mt-1 text-xl font-bold text-gray-900">{Math.round((alignmentData.coverage_stats.coverage_pct ?? 0) * 100)}%</p>
                    </div>
                  </div>
                )}
                {/* Gap Analysis Summary */}
                {alignmentData.gap_analysis && (
                  <div className="mb-4">
                    <GapAnalysis data={alignmentData.gap_analysis} loading={false} />
                  </div>
                )}
                {/* Action buttons */}
                <div className="mb-4 flex items-center gap-2">
                  <button
                    onClick={handleRunExtraction}
                    disabled={extractionRunning || mappingRunning}
                    className="flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {extractionRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                    {extractionRunning ? "Extracting..." : "Extract & Map"}
                  </button>
                  <button
                    onClick={handleRunMapping}
                    disabled={mappingRunning || extractionRunning}
                    className="flex items-center gap-1.5 rounded-md border border-indigo-200 bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
                  >
                    {mappingRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <GitCompare className="h-3.5 w-3.5" />}
                    {mappingRunning ? "Mapping..." : "Run Mapping Only"}
                  </button>
                  <button
                    onClick={() => fetchAlignment(true)}
                    disabled={alignmentLoading}
                    className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${alignmentLoading ? "animate-spin" : ""}`} />
                    Refresh
                  </button>
                </div>
                {/* Cross Graph View */}
                <div className="rounded-lg border" style={{ height: "500px" }}>
                  <CrossGraphView
                    documentNodes={alignmentData.document_nodes || []}
                    codeNodes={alignmentData.code_nodes || []}
                    mappings={alignmentData.mappings || []}
                    selectedMappingId={selectedMappingId}
                    onSelectMapping={setSelectedMappingId}
                  />
                </div>
              </>
            ) : (
              <div className="flex h-40 flex-col items-center justify-center text-gray-400">
                <GitCompare className="mb-2 h-8 w-8" />
                <p className="text-sm">No alignment data yet</p>
                <p className="mt-1 text-xs">Link documents and repositories, then analyze them to see doc ↔ code alignment</p>
                <div className="mt-3 flex items-center gap-2">
                  <button
                    onClick={handleRunExtraction}
                    disabled={extractionRunning}
                    className="flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {extractionRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                    {extractionRunning ? "Running..." : "Extract Ontology & Run Mapping"}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Requirement Traceability (L4 extension) */}
      {assets.length > 0 && (
        <div className="mt-6">
          <RequirementTraceabilityPanel
            initiativeId={projectId}
            documentIds={assets.filter(a => a.asset_type === "DOCUMENT").map(a => a.asset_id)}
          />
        </div>
      )}

      {/* Link Asset Dialog */}
      {showLinkDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                Link {linkType === "DOCUMENT" ? "Document" : "Repository"}
              </h2>
              <button onClick={() => setShowLinkDialog(false)} className="rounded-md p-1 hover:bg-gray-100">
                <X className="h-5 w-5 text-gray-400" />
              </button>
            </div>
            <div className="max-h-80 overflow-y-auto">
              {linkType === "DOCUMENT" ? (
                allDocs.length === 0 ? (
                  <p className="py-8 text-center text-sm text-gray-400">No documents available</p>
                ) : (
                  <div className="divide-y">
                    {allDocs.filter((d) => !linkedDocIds.has(d.id)).map((doc) => (
                      <button
                        key={doc.id}
                        onClick={() => handleLinkAsset(doc.id)}
                        disabled={linking}
                        className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-blue-50 disabled:opacity-50"
                      >
                        <FileText className="h-4 w-4 text-gray-400" />
                        <div>
                          <p className="text-sm font-medium text-gray-900">{doc.filename}</p>
                          <p className="text-xs text-gray-500">{doc.status}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                )
              ) : (
                allRepos.length === 0 ? (
                  <p className="py-8 text-center text-sm text-gray-400">No repositories available</p>
                ) : (
                  <div className="divide-y">
                    {allRepos.filter((r) => !linkedRepoIds.has(r.id)).map((repo) => (
                      <button
                        key={repo.id}
                        onClick={() => handleLinkAsset(repo.id)}
                        disabled={linking}
                        className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-green-50 disabled:opacity-50"
                      >
                        <GitBranch className="h-4 w-4 text-gray-400" />
                        <div>
                          <p className="text-sm font-medium text-gray-900">{repo.name}</p>
                          <p className="text-xs text-gray-500">{repo.analysis_status}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
