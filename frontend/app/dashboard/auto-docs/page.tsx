"use client";

import { useState, useEffect, useRef } from "react";
import {
  FileText,
  Cpu,
  BookOpen,
  Loader2,
  Network,
  TestTube,
  Database,
  Plus,
  X,
  Download,
  Copy,
  Check,
  Sparkles,
  Clock,
  AlertCircle,
  Layers,
  Code,
  Tag,
  FileCode,
  ChevronRight,
  ChevronDown,
  Search,
  Wand2,
  Send,
  RotateCcw,
  CheckCircle2,
  PanelBottomOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { MarkdownRenderer } from "@/components/chat/MarkdownRenderer";
import { MermaidDiagram } from "@/components/ontology/MermaidDiagram";

// ----- Types -----

interface DocTypeInfo {
  id: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  badge: string;
  badgeColor: string;
}

const DOC_TYPES: DocTypeInfo[] = [
  {
    id: "component_spec",
    label: "Component Specification",
    description: "Overview, responsibilities, interfaces, dependencies, and NFRs",
    icon: FileText,
    badge: "Sprint A",
    badgeColor: "bg-blue-100 text-blue-700",
  },
  {
    id: "architecture_diagram",
    label: "Architecture Diagram",
    description: "Mermaid diagram showing services, databases, and connections",
    icon: Network,
    badge: "Sprint A",
    badgeColor: "bg-blue-100 text-blue-700",
  },
  {
    id: "api_summary",
    label: "API Summary",
    description: "Endpoint table, schemas, auth, and error codes",
    icon: Cpu,
    badge: "Sprint A",
    badgeColor: "bg-blue-100 text-blue-700",
  },
  {
    id: "brd",
    label: "Business Requirements Document",
    description: "Formal BRD with objectives, functional requirements, and acceptance criteria",
    icon: BookOpen,
    badge: "Sprint B",
    badgeColor: "bg-purple-100 text-purple-700",
  },
  {
    id: "test_cases",
    label: "Test Cases",
    description: "Unit, integration, E2E, security, and performance test cases",
    icon: TestTube,
    badge: "Sprint B",
    badgeColor: "bg-purple-100 text-purple-700",
  },
  {
    id: "data_models",
    label: "Data Models",
    description: "ER diagram, table definitions, relationships, and indexes",
    icon: Database,
    badge: "Sprint B",
    badgeColor: "bg-purple-100 text-purple-700",
  },
];

interface GeneratedDocSummary {
  id: number;
  source_type: string;
  source_id: number;
  source_name: string | null;
  source_ids?: Array<{ type: string; id: number }> | null;
  doc_type: string;
  title: string;
  status: string;
  created_at: string;
}

interface GeneratedDocFull extends GeneratedDocSummary {
  content: string;
  metadata: Record<string, unknown> | null;
}

type SourceType =
  | "document"
  | "repository"
  | "code_file"
  | "standalone"
  | "jira_item"
  | "analysis";

interface SourceItem {
  id: number;
  name: string;
  type: SourceType;
  repoId?: number;
  repoName?: string;
}

interface RepoItem {
  id: number;
  name: string;
}

// ----- Style helpers -----

const SOURCE_STYLES: Record<
  SourceType,
  { chip: string; hover: string; check: string; icon: React.ComponentType<{ className?: string }> }
> = {
  document:   { chip: "bg-blue-100 text-blue-700",   hover: "hover:bg-blue-50",   check: "text-blue-600",   icon: FileText },
  repository: { chip: "bg-green-100 text-green-700", hover: "hover:bg-green-50",  check: "text-green-600",  icon: Database },
  code_file:  { chip: "bg-amber-100 text-amber-700", hover: "hover:bg-amber-50",  check: "text-amber-600",  icon: FileCode },
  standalone: { chip: "bg-teal-100 text-teal-700",   hover: "hover:bg-teal-50",   check: "text-teal-600",   icon: Code },
  jira_item:  { chip: "bg-purple-100 text-purple-700", hover: "hover:bg-purple-50", check: "text-purple-600", icon: Tag },
  analysis:   { chip: "bg-indigo-100 text-indigo-700", hover: "hover:bg-indigo-50", check: "text-indigo-600", icon: Sparkles },
};

// ----- Main Page -----

export default function AutoDocsPage() {
  // Sources
  const [documents, setDocuments] = useState<SourceItem[]>([]);
  const [repositories, setRepositories] = useState<RepoItem[]>([]);
  const [standaloneFiles, setStandaloneFiles] = useState<SourceItem[]>([]);
  const [jiraItems, setJiraItems] = useState<SourceItem[]>([]);
  const [analysisResults, setAnalysisResults] = useState<SourceItem[]>([]);
  // Lazy-loaded repo files: repoId → SourceItem[]
  const [repoFiles, setRepoFiles] = useState<Record<number, SourceItem[]>>({});
  const [repoFilesLoading, setRepoFilesLoading] = useState<Set<number>>(new Set());
  const [expandedRepos, setExpandedRepos] = useState<Set<number>>(new Set());

  // Selection & UI
  const [selectedSources, setSelectedSources] = useState<SourceItem[]>([]);
  const [selectedDocType, setSelectedDocType] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [history, setHistory] = useState<GeneratedDocSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [viewingDoc, setViewingDoc] = useState<GeneratedDocFull | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [diagramView, setDiagramView] = useState<"rendered" | "diagram">("rendered");
  const [showSourcePicker, setShowSourcePicker] = useState(false);
  const [sourceSearch, setSourceSearch] = useState("");
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);

  // AI Refinement panel
  const [showRefinePanel, setShowRefinePanel] = useState(false);
  const [refinePrompt, setRefinePrompt] = useState("");
  const [refining, setRefining] = useState(false);
  const [refineSaveAsNew, setRefineSaveAsNew] = useState(false);
  const [refineResult, setRefineResult] = useState<{
    content: string;
    saved: boolean;
    id: number | null;
    title?: string;
  } | null>(null);

  const pickerRef = useRef<HTMLDivElement>(null);
  const downloadMenuRef = useRef<HTMLDivElement>(null);
  const refineTextareaRef = useRef<HTMLTextAreaElement>(null);

  // Close picker / download menu on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setShowSourcePicker(false);
      }
      if (downloadMenuRef.current && !downloadMenuRef.current.contains(e.target as Node)) {
        setShowDownloadMenu(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Fetch all source lists
  useEffect(() => {
    // Documents
    (api.get("/documents/") as Promise<any>)
      .then((docs) => {
        const arr = docs.items || docs.documents || (Array.isArray(docs) ? docs : []);
        setDocuments(
          arr.slice(0, 100).map((d: any) => ({
            id: d.id,
            name: d.filename || `Document #${d.id}`,
            type: "document" as const,
          }))
        );
      })
      .catch(console.error);

    // Repositories
    (api.get("/repositories/") as Promise<any>)
      .then((repos) => {
        const arr = Array.isArray(repos) ? repos : repos.items || repos.repositories || [];
        setRepositories(arr.slice(0, 50).map((r: any) => ({ id: r.id, name: r.name || `Repository #${r.id}` })));
      })
      .catch(console.error);

    // Standalone files
    (api.get("/code-components/?standalone=true&limit=100") as Promise<any>)
      .then((data) => {
        const arr = Array.isArray(data) ? data : [];
        setStandaloneFiles(
          arr.map((c: any) => ({
            id: c.id,
            name: c.name || c.location || `File #${c.id}`,
            type: "standalone" as const,
          }))
        );
      })
      .catch(console.error);

    // Jira items
    (api.get("/integrations/jira/items?limit=100") as Promise<any>)
      .then((data) => {
        const arr = data.items || (Array.isArray(data) ? data : []);
        setJiraItems(
          arr.map((j: any) => ({
            id: j.id,
            name: j.external_key ? `${j.external_key}: ${(j.title || "").slice(0, 50)}` : j.title || `JIRA #${j.id}`,
            type: "jira_item" as const,
          }))
        );
      })
      .catch(() => {/* Jira may not be connected — silently ignore */});
  }, []);

  const fetchHistory = () => {
    setHistoryLoading(true);
    (api.get("/auto-docs/") as Promise<any>)
      .then((data) => {
        setHistory(data.docs || []);
        // Convert to SourceItem for the analysis results section
        setAnalysisResults(
          (data.docs || []).slice(0, 50).map((d: any) => ({
            id: d.id,
            name: d.title || `Analysis #${d.id}`,
            type: "analysis" as const,
          }))
        );
      })
      .catch(console.error)
      .finally(() => setHistoryLoading(false));
  };

  useEffect(() => { fetchHistory(); }, []);

  // Lazy-load files for a specific repo
  const loadRepoFiles = (repoId: number, repoName: string) => {
    if (repoFiles[repoId] !== undefined || repoFilesLoading.has(repoId)) return;
    setRepoFilesLoading((prev) => new Set(prev).add(repoId));
    (api.get(`/code-components/?repository_id=${repoId}&limit=500`) as Promise<any>)
      .then((data) => {
        const arr = Array.isArray(data) ? data : [];
        setRepoFiles((prev) => ({
          ...prev,
          [repoId]: arr.map((c: any) => ({
            id: c.id,
            name: c.name || c.location || `File #${c.id}`,
            type: "code_file" as const,
            repoId,
            repoName,
          })),
        }));
      })
      .catch(console.error)
      .finally(() => {
        setRepoFilesLoading((prev) => {
          const next = new Set(prev);
          next.delete(repoId);
          return next;
        });
      });
  };

  const toggleRepoExpand = (repo: RepoItem) => {
    setExpandedRepos((prev) => {
      const next = new Set(prev);
      if (next.has(repo.id)) {
        next.delete(repo.id);
      } else {
        next.add(repo.id);
        loadRepoFiles(repo.id, repo.name);
      }
      return next;
    });
  };

  const toggleSource = (src: SourceItem) => {
    setSelectedSources((prev) => {
      const exists = prev.find((s) => s.type === src.type && s.id === src.id);
      if (exists) return prev.filter((s) => !(s.type === src.type && s.id === src.id));
      return [...prev, src];
    });
  };

  const removeSource = (src: SourceItem) => {
    setSelectedSources((prev) => prev.filter((s) => !(s.type === src.type && s.id === src.id)));
  };

  const isSelected = (src: SourceItem) =>
    selectedSources.some((s) => s.type === src.type && s.id === src.id);

  const handleGenerate = async () => {
    if (selectedSources.length === 0 || !selectedDocType) return;
    setGenerating(true);
    try {
      const payload = {
        sources: selectedSources.map((s) => ({ type: s.type, id: s.id })),
        doc_type: selectedDocType,
      };
      const data = await api.post("/auto-docs/generate-multi", payload) as GeneratedDocFull;
      setViewingDoc(data);
      setDiagramView("rendered");
      fetchHistory();
    } catch {
      alert("Generation failed. Please check that your selected sources have been analyzed.");
    } finally {
      setGenerating(false);
    }
  };

  const handleViewDoc = async (id: number) => {
    setViewLoading(true);
    try {
      const data = await api.get(`/auto-docs/${id}`) as GeneratedDocFull;
      setViewingDoc(data);
      setDiagramView("rendered");
    } catch {
      alert("Failed to load document.");
    } finally {
      setViewLoading(false);
    }
  };

  const handleCopy = (content: string, id: number) => {
    navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const extractMermaid = (content: string): string | null => {
    const match = content.match(/```mermaid\n([\s\S]*?)```/);
    return match ? match[1].trim() : null;
  };

  const handleDownload = (doc: GeneratedDocFull) => {
    const blob = new Blob([doc.content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${doc.doc_type}-${doc.id}.md`;
    a.click();
    URL.revokeObjectURL(url);
    setShowDownloadMenu(false);
  };

  const handleExport = async (doc: GeneratedDocFull, format: "docx" | "pdf") => {
    setExportingFormat(format);
    setShowDownloadMenu(false);
    try {
      const token = localStorage.getItem("accessToken");
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const resp = await fetch(`${apiBase}/auto-docs/${doc.id}/export?format=${format}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) throw new Error(`Export failed: ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${doc.doc_type}-${doc.id}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(`Export failed. Please try again.\n${err}`);
    } finally {
      setExportingFormat(null);
    }
  };

  const handleRefine = async () => {
    if (!viewingDoc || !refinePrompt.trim() || refining) return;
    setRefining(true);
    setRefineResult(null);
    try {
      const result = await api.post(`/auto-docs/${viewingDoc.id}/refine`, {
        prompt: refinePrompt.trim(),
        save_as_new: refineSaveAsNew,
      }) as any;
      setRefineResult(result);
      if (refineSaveAsNew && result.id) {
        // Refresh history so new version appears in sidebar
        (api.get("/auto-docs/") as Promise<any>).then((data) => {
          const arr = data.items || data.docs || (Array.isArray(data) ? data : []);
          setHistory(arr.slice(0, 10));
        }).catch(() => {});
      }
    } catch (err) {
      alert(`Refinement failed. Please try again.\n${err}`);
    } finally {
      setRefining(false);
    }
  };

  const acceptRefinement = () => {
    if (!refineResult || !viewingDoc) return;
    setViewingDoc({ ...viewingDoc, content: refineResult.content });
    setRefineResult(null);
    setRefinePrompt("");
    setShowRefinePanel(false);
  };

  const discardRefinement = () => {
    setRefineResult(null);
    setRefinePrompt("");
  };

  // Filter helpers
  const q = sourceSearch.toLowerCase();
  const filtered = <T extends { name: string }>(arr: T[]) =>
    q ? arr.filter((i) => i.name.toLowerCase().includes(q)) : arr;

  const filteredRepoFiles = (repoId: number) => {
    const files = repoFiles[repoId] || [];
    return q ? files.filter((f) => f.name.toLowerCase().includes(q)) : files;
  };

  // Section row renderer
  const SourceRow = ({ src }: { src: SourceItem }) => {
    const style = SOURCE_STYLES[src.type];
    const Icon = style.icon;
    const selected = isSelected(src);
    return (
      <button
        key={`${src.type}:${src.id}`}
        onClick={() => toggleSource(src)}
        className={`w-full text-left flex items-center gap-2 px-3 py-2 text-sm transition-colors ${
          selected ? `${style.hover} font-medium` : `text-gray-700 ${style.hover}`
        }`}
      >
        <Icon className="w-3.5 h-3.5 flex-shrink-0 text-gray-400" />
        <span className="truncate flex-1">{src.name}</span>
        {selected && <Check className={`w-3.5 h-3.5 flex-shrink-0 ${style.check}`} />}
      </button>
    );
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg">
          <Sparkles className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Auto Docs</h1>
          <p className="text-sm text-gray-500">
            AI-generated documentation from one or more analyzed sources
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Generation Panel */}
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-white border rounded-xl p-5 shadow-sm space-y-4">
            <h2 className="text-sm font-semibold text-gray-800">Generate New Doc</h2>

            {/* Multi-source selector */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1.5">
                Sources
                <span className="ml-1 text-gray-400 font-normal">(select one or more)</span>
              </label>

              {/* Selected chips */}
              {selectedSources.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {selectedSources.map((s) => {
                    const style = SOURCE_STYLES[s.type];
                    const Icon = style.icon;
                    return (
                      <span
                        key={`${s.type}:${s.id}`}
                        className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full font-medium ${style.chip}`}
                      >
                        <Icon className="w-3 h-3" />
                        <span className="max-w-[120px] truncate">{s.name}</span>
                        <button onClick={() => removeSource(s)} className="hover:opacity-70">
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    );
                  })}
                </div>
              )}

              {/* Add source button + dropdown */}
              <div ref={pickerRef} className="relative">
                <button
                  onClick={() => { setShowSourcePicker(!showSourcePicker); setSourceSearch(""); }}
                  className="w-full flex items-center justify-center gap-2 text-sm border border-dashed border-gray-300 rounded-lg px-3 py-2 text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  {selectedSources.length === 0 ? "Add source" : "Add another source"}
                </button>

                {/* Source picker dropdown */}
                {showSourcePicker && (
                  <div className="absolute z-50 left-0 right-0 mt-1 border rounded-lg bg-white shadow-xl max-h-80 overflow-y-auto">
                    {/* Search */}
                    <div className="sticky top-0 z-10 bg-white border-b px-3 py-2">
                      <div className="flex items-center gap-2 bg-gray-50 rounded-md px-2 py-1.5">
                        <Search className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                        <input
                          autoFocus
                          type="text"
                          placeholder="Search sources…"
                          value={sourceSearch}
                          onChange={(e) => setSourceSearch(e.target.value)}
                          className="flex-1 bg-transparent text-xs outline-none text-gray-700 placeholder-gray-400"
                        />
                        {sourceSearch && (
                          <button onClick={() => setSourceSearch("")}>
                            <X className="w-3 h-3 text-gray-400 hover:text-gray-600" />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Documents section */}
                    {filtered(documents).length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 px-3 pt-2 pb-1 bg-gray-50 sticky top-[48px] z-[5]">
                          Documents
                        </p>
                        {filtered(documents).map((s) => <SourceRow key={`doc:${s.id}`} src={s} />)}
                      </div>
                    )}

                    {/* Repositories + expandable files section */}
                    {repositories.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 px-3 pt-2 pb-1 bg-gray-50">
                          Repositories
                        </p>
                        {repositories
                          .filter((r) => !q || r.name.toLowerCase().includes(q))
                          .map((repo) => {
                            const repoSrc: SourceItem = { id: repo.id, name: repo.name, type: "repository" };
                            const isExpanded = expandedRepos.has(repo.id);
                            const isLoading = repoFilesLoading.has(repo.id);
                            const files = filteredRepoFiles(repo.id);
                            const repoSelected = isSelected(repoSrc);

                            return (
                              <div key={`repo:${repo.id}`}>
                                {/* Repo row */}
                                <div className={`flex items-center group text-sm transition-colors ${repoSelected ? "bg-green-50" : "hover:bg-green-50"}`}>
                                  {/* Expand toggle */}
                                  <button
                                    onClick={() => toggleRepoExpand(repo)}
                                    className="flex-shrink-0 flex items-center justify-center w-8 h-8 text-gray-400 hover:text-gray-600"
                                    title="Browse files in this repo"
                                  >
                                    {isLoading ? (
                                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                    ) : isExpanded ? (
                                      <ChevronDown className="w-3.5 h-3.5" />
                                    ) : (
                                      <ChevronRight className="w-3.5 h-3.5" />
                                    )}
                                  </button>
                                  {/* Select whole repo */}
                                  <button
                                    onClick={() => toggleSource(repoSrc)}
                                    className="flex-1 flex items-center gap-2 pr-3 py-2 text-left"
                                  >
                                    <Database className="w-3.5 h-3.5 flex-shrink-0 text-green-500" />
                                    <span className={`truncate flex-1 ${repoSelected ? "text-green-700 font-medium" : "text-gray-700"}`}>{repo.name}</span>
                                    {repoSelected && <Check className="w-3.5 h-3.5 flex-shrink-0 text-green-600" />}
                                  </button>
                                </div>

                                {/* Expanded file list */}
                                {isExpanded && (
                                  <div className="ml-6 border-l border-gray-200">
                                    {isLoading && (
                                      <div className="px-3 py-2 text-xs text-gray-400 flex items-center gap-2">
                                        <Loader2 className="w-3 h-3 animate-spin" /> Loading files…
                                      </div>
                                    )}
                                    {!isLoading && files.length === 0 && (
                                      <p className="px-3 py-2 text-xs text-gray-400">
                                        {q ? "No files match your search." : "No analyzed files found."}
                                      </p>
                                    )}
                                    {!isLoading && files.length > 0 && (
                                      <>
                                        {files.map((f) => <SourceRow key={`cf:${f.id}`} src={f} />)}
                                        {!q && (repoFiles[repo.id] || []).length >= 500 && (
                                          <p className="px-3 py-1.5 text-xs text-gray-400 italic">
                                            Showing first 500 files. Use search to find more.
                                          </p>
                                        )}
                                      </>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                      </div>
                    )}

                    {/* Standalone files section */}
                    {filtered(standaloneFiles).length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 px-3 pt-2 pb-1 bg-gray-50">
                          Standalone Files
                        </p>
                        {filtered(standaloneFiles).map((s) => <SourceRow key={`sf:${s.id}`} src={s} />)}
                      </div>
                    )}

                    {/* Jira items section */}
                    {filtered(jiraItems).length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 px-3 pt-2 pb-1 bg-gray-50">
                          Jira Tickets
                        </p>
                        {filtered(jiraItems).map((s) => <SourceRow key={`jira:${s.id}`} src={s} />)}
                      </div>
                    )}

                    {/* Previous analyses section */}
                    {filtered(analysisResults).length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 px-3 pt-2 pb-1 bg-gray-50">
                          Previous Analyses
                        </p>
                        {filtered(analysisResults).map((s) => <SourceRow key={`analysis:${s.id}`} src={s} />)}
                      </div>
                    )}

                    {/* Empty state */}
                    {documents.length === 0 &&
                      repositories.length === 0 &&
                      standaloneFiles.length === 0 &&
                      jiraItems.length === 0 &&
                      analysisResults.length === 0 && (
                        <p className="text-xs text-gray-400 px-3 py-3">
                          No analyzed sources found. Upload documents or connect a repository first.
                        </p>
                      )}
                  </div>
                )}
              </div>

              {selectedSources.length > 1 && (
                <p className="text-xs text-blue-600 mt-1.5 flex items-center gap-1">
                  <Layers className="w-3 h-3" />
                  {selectedSources.length} sources will be combined for richer context
                </p>
              )}
            </div>

            {/* Doc type selector */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1.5">Document Type</label>
              <div className="space-y-1.5">
                {DOC_TYPES.map((dt) => {
                  const Icon = dt.icon;
                  return (
                    <button
                      key={dt.id}
                      onClick={() => setSelectedDocType(dt.id)}
                      className={`w-full text-left flex items-start gap-3 p-3 rounded-lg border transition-colors ${
                        selectedDocType === dt.id
                          ? "border-blue-400 bg-blue-50"
                          : "border-gray-200 hover:border-gray-300 bg-white"
                      }`}
                    >
                      <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${selectedDocType === dt.id ? "text-blue-600" : "text-gray-400"}`} />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-gray-800">{dt.label}</span>
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${dt.badgeColor}`}>
                            {dt.badge}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5 truncate">{dt.description}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <Button
              className="w-full bg-blue-600 hover:bg-blue-700"
              disabled={selectedSources.length === 0 || !selectedDocType || generating}
              onClick={handleGenerate}
            >
              {generating ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Generating…
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-2" />
                  Generate
                </>
              )}
            </Button>

            {generating && (
              <p className="text-xs text-gray-500 text-center">
                This may take 15–45 seconds for multiple sources…
              </p>
            )}
          </div>

          {/* History */}
          <div className="bg-white border rounded-xl p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-800 mb-3">Recent Generations</h2>
            {historyLoading ? (
              <div className="flex items-center gap-2 text-sm text-gray-400 py-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading…
              </div>
            ) : history.length === 0 ? (
              <p className="text-xs text-gray-400 py-2">No documents generated yet.</p>
            ) : (
              <div className="space-y-2">
                {history.slice(0, 10).map((h) => (
                  <button
                    key={h.id}
                    onClick={() => handleViewDoc(h.id)}
                    className="w-full text-left flex items-start gap-2 p-2 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    <FileText className="w-3.5 h-3.5 text-gray-400 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-gray-700 truncate">{h.title}</p>
                      <p className="text-xs text-gray-400 flex items-center gap-1 mt-0.5">
                        <Clock className="w-3 h-3" />
                        {new Date(h.created_at).toLocaleDateString()}
                        {h.source_type === "multi" && (
                          <span className="ml-1 text-blue-400 flex items-center gap-0.5">
                            <Layers className="w-3 h-3" />
                            multi
                          </span>
                        )}
                      </p>
                    </div>
                    {h.status === "failed" && (
                      <AlertCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Document Viewer */}
        <div className="lg:col-span-2">
          {viewLoading && (
            <div className="flex items-center justify-center h-64 bg-white border rounded-xl">
              <Loader2 className="w-5 h-5 animate-spin text-blue-500 mr-2" />
              <span className="text-sm text-gray-500">Loading…</span>
            </div>
          )}

          {!viewLoading && !viewingDoc && (
            <div className="flex flex-col items-center justify-center h-64 bg-white border rounded-xl text-gray-400">
              <Sparkles className="w-12 h-12 mb-3" />
              <p className="text-sm font-medium">Add sources and select a doc type, then click Generate</p>
              <p className="text-xs mt-1">Combine documents + repositories for richer output</p>
            </div>
          )}

          {!viewLoading && viewingDoc && (() => {
            const mermaidSyntax = extractMermaid(viewingDoc.content ?? "");
            const hasMermaid = !!mermaidSyntax;
            return (
              <div className="bg-white border rounded-xl shadow-sm overflow-hidden flex flex-col h-full">
                {/* Viewer header */}
                <div className="flex items-center justify-between px-5 py-3 border-b bg-gray-50">
                  <div>
                    <h2 className="text-sm font-semibold text-gray-900 truncate max-w-lg">{viewingDoc.title}</h2>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {viewingDoc.source_name && <span>{viewingDoc.source_name} · </span>}
                      {viewingDoc.doc_type} · {new Date(viewingDoc.created_at).toLocaleString()}
                      {viewingDoc.source_type === "multi" && (
                        <span className="ml-2 text-blue-500 font-medium flex items-center gap-0.5 inline-flex">
                          <Layers className="w-3 h-3" />
                          {(viewingDoc.source_ids || []).length} sources
                        </span>
                      )}
                      {viewingDoc.status === "failed" && (
                        <span className="text-red-500 ml-2">⚠ Generation failed</span>
                      )}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {hasMermaid && (
                      <div className="flex rounded-md border overflow-hidden text-xs">
                        <button
                          onClick={() => setDiagramView("rendered")}
                          className={`px-3 py-1.5 font-medium transition-colors ${diagramView === "rendered" ? "bg-indigo-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
                        >
                          Code
                        </button>
                        <button
                          onClick={() => setDiagramView("diagram")}
                          className={`px-3 py-1.5 font-medium transition-colors border-l ${diagramView === "diagram" ? "bg-indigo-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
                        >
                          View Diagram
                        </button>
                      </div>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs gap-1.5"
                      onClick={() => handleCopy(viewingDoc.content, viewingDoc.id)}
                    >
                      {copiedId === viewingDoc.id ? (
                        <><Check className="w-3.5 h-3.5 text-green-600" /> Copied</>
                      ) : (
                        <><Copy className="w-3.5 h-3.5" /> Copy</>
                      )}
                    </Button>
                    {/* Refine with AI */}
                    <Button
                      size="sm"
                      variant={showRefinePanel ? "default" : "outline"}
                      className={`h-7 text-xs gap-1.5 ${showRefinePanel ? "bg-indigo-600 text-white hover:bg-indigo-700" : ""}`}
                      onClick={() => {
                        setShowRefinePanel((v) => !v);
                        setRefineResult(null);
                        setTimeout(() => refineTextareaRef.current?.focus(), 50);
                      }}
                    >
                      <Wand2 className="w-3.5 h-3.5" /> Refine with AI
                    </Button>
                    {/* Download dropdown */}
                    <div className="relative" ref={downloadMenuRef}>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs gap-1.5"
                        onClick={() => setShowDownloadMenu((v) => !v)}
                        disabled={!!exportingFormat}
                      >
                        {exportingFormat ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Download className="w-3.5 h-3.5" />
                        )}
                        {exportingFormat ? `Exporting ${exportingFormat.toUpperCase()}…` : "Download"}
                        <ChevronDown className="w-3 h-3 ml-0.5" />
                      </Button>
                      {showDownloadMenu && (
                        <div className="absolute right-0 top-8 z-50 w-44 bg-white border border-gray-200 rounded-md shadow-lg py-1 text-xs">
                          <button
                            className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-gray-700"
                            onClick={() => handleDownload(viewingDoc)}
                          >
                            <FileText className="w-3.5 h-3.5 text-gray-400" />
                            Markdown (.md)
                          </button>
                          <button
                            className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-gray-700"
                            onClick={() => handleExport(viewingDoc, "docx")}
                          >
                            <FileText className="w-3.5 h-3.5 text-blue-500" />
                            Word Document (.docx)
                          </button>
                          <button
                            className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-gray-700"
                            onClick={() => handleExport(viewingDoc, "pdf")}
                          >
                            <FileText className="w-3.5 h-3.5 text-red-500" />
                            PDF (.pdf)
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Content */}
                <div className={`flex-1 overflow-y-auto p-6 ${showRefinePanel ? "max-h-[calc(100vh-480px)]" : "max-h-[calc(100vh-280px)]"}`}>
                  {viewingDoc.content ? (
                    hasMermaid && diagramView === "diagram" ? (
                      <MermaidDiagram
                        syntax={mermaidSyntax!}
                        title={viewingDoc.title}
                        className="w-full"
                      />
                    ) : (
                      <MarkdownRenderer content={viewingDoc.content} />
                    )
                  ) : (
                    <p className="text-sm text-gray-400 italic">No content generated.</p>
                  )}
                </div>

                {/* ── AI Refinement Panel ── */}
                {showRefinePanel && (
                  <div className="border-t bg-gradient-to-b from-indigo-50 to-white">
                    {/* Panel header */}
                    <div className="flex items-center gap-2 px-5 pt-3 pb-2">
                      <Wand2 className="w-4 h-4 text-indigo-600" />
                      <span className="text-sm font-semibold text-indigo-800">Refine with AI</span>
                      <span className="text-xs text-gray-400 ml-1">Ask AI to tweak, expand, or restructure this document</span>
                    </div>

                    {/* Result preview — shown after AI responds */}
                    {refineResult && (
                      <div className="mx-5 mb-3 rounded-lg border border-green-200 bg-green-50 p-3">
                        <div className="flex items-center gap-1.5 mb-2">
                          <CheckCircle2 className="w-4 h-4 text-green-600" />
                          <span className="text-xs font-semibold text-green-800">
                            {refineResult.saved ? `Saved as new doc: "${refineResult.title}"` : "Refinement ready — preview below"}
                          </span>
                        </div>
                        <p className="text-xs text-gray-600 line-clamp-3 font-mono bg-white rounded border border-green-100 p-2 mb-3">
                          {refineResult.content.slice(0, 300)}{refineResult.content.length > 300 ? "…" : ""}
                        </p>
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            className="h-7 text-xs bg-green-600 hover:bg-green-700 text-white gap-1.5"
                            onClick={acceptRefinement}
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" /> Accept Changes
                          </Button>
                          {!refineResult.saved && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs gap-1.5"
                              onClick={async () => {
                                if (!viewingDoc) return;
                                setRefining(true);
                                try {
                                  const r = await api.post(`/auto-docs/${viewingDoc.id}/refine`, {
                                    prompt: refinePrompt.trim() || "Save this refinement",
                                    save_as_new: true,
                                  }) as any;
                                  setRefineResult(r);
                                  (api.get("/auto-docs/") as Promise<any>).then((d) => {
                                    const arr = d.items || d.docs || (Array.isArray(d) ? d : []);
                                    setHistory(arr.slice(0, 10));
                                  }).catch(() => {});
                                } catch { /* ignore */ } finally { setRefining(false); }
                              }}
                            >
                              <PanelBottomOpen className="w-3.5 h-3.5" /> Save as New Doc
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 text-xs text-gray-500 gap-1.5"
                            onClick={discardRefinement}
                          >
                            <RotateCcw className="w-3.5 h-3.5" /> Discard
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Prompt input */}
                    <div className="px-5 pb-4">
                      <div className="flex gap-2 items-end">
                        <div className="flex-1 relative">
                          <textarea
                            ref={refineTextareaRef}
                            rows={2}
                            value={refinePrompt}
                            onChange={(e) => setRefinePrompt(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleRefine();
                            }}
                            placeholder='e.g. "Make the executive summary shorter" · "Add a security requirements section" · "Rewrite in formal tone" · Ctrl+Enter to send'
                            className="w-full resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                          />
                        </div>
                        <div className="flex flex-col gap-1.5 items-end">
                          <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer select-none whitespace-nowrap">
                            <input
                              type="checkbox"
                              checked={refineSaveAsNew}
                              onChange={(e) => setRefineSaveAsNew(e.target.checked)}
                              className="rounded"
                            />
                            Save as new doc
                          </label>
                          <Button
                            size="sm"
                            className="h-8 text-xs px-4 bg-indigo-600 hover:bg-indigo-700 text-white gap-1.5"
                            onClick={handleRefine}
                            disabled={refining || !refinePrompt.trim()}
                          >
                            {refining ? (
                              <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Refining…</>
                            ) : (
                              <><Send className="w-3.5 h-3.5" /> Send to AI</>
                            )}
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Token usage footer */}
                {viewingDoc.metadata && (viewingDoc.metadata.input_tokens != null || viewingDoc.metadata.output_tokens != null) && (
                  <div className="px-5 py-2 border-t bg-gray-50 flex items-center gap-4 text-xs text-gray-500">
                    <span>Input: {String(viewingDoc.metadata.input_tokens ?? 0)} tokens</span>
                    <span>Output: {String(viewingDoc.metadata.output_tokens ?? 0)} tokens</span>
                    {viewingDoc.metadata.source_count != null && (
                      <span className="text-blue-500">
                        <Layers className="w-3 h-3 inline mr-0.5" />
                        {String(viewingDoc.metadata.source_count)} sources combined
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
}
