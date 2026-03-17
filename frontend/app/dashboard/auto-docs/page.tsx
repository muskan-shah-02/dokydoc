"use client";

import { useState, useEffect } from "react";
import {
  FileText,
  Cpu,
  BookOpen,
  Loader2,
  Network,
  TestTube,
  Database,
  Plus,
  ChevronDown,
  ChevronRight,
  Download,
  Copy,
  Check,
  Sparkles,
  Clock,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { MarkdownRenderer } from "@/components/chat/MarkdownRenderer";

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
  doc_type: string;
  title: string;
  status: string;
  created_at: string;
}

interface GeneratedDocFull extends GeneratedDocSummary {
  content: string;
  metadata: Record<string, unknown> | null;
}

interface SourceItem {
  id: number;
  name: string;
  type: "document" | "repository";
}

// ----- Main Page -----

export default function AutoDocsPage() {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [selectedSource, setSelectedSource] = useState<SourceItem | null>(null);
  const [selectedDocType, setSelectedDocType] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [history, setHistory] = useState<GeneratedDocSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [viewingDoc, setViewingDoc] = useState<GeneratedDocFull | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  // Fetch available sources (documents + repositories)
  useEffect(() => {
    Promise.all([
      api.get("/documents/") as Promise<any>,
      api.get("/repositories/") as Promise<any>,
    ])
      .then(([docs, repos]) => {
        const docArray = docs.items || docs.documents || (Array.isArray(docs) ? docs : []);
        const docItems: SourceItem[] = docArray.slice(0, 50).map(
          (d: any) => ({ id: d.id, name: d.filename || `Document #${d.id}`, type: "document" as const })
        );
        const repoItems: SourceItem[] = (Array.isArray(repos) ? repos : repos.items || repos.repositories || []).slice(0, 50).map(
          (r: any) => ({ id: r.id, name: r.name || `Repository #${r.id}`, type: "repository" as const })
        );
        setSources([...docItems, ...repoItems]);
      })
      .catch(console.error);
  }, []);

  // Fetch generation history
  const fetchHistory = () => {
    setHistoryLoading(true);
    (api.get("/auto-docs/") as Promise<any>)
      .then((data) => setHistory(data.docs || []))
      .catch(console.error)
      .finally(() => setHistoryLoading(false));
  };

  useEffect(() => { fetchHistory(); }, []);

  const handleGenerate = async () => {
    if (!selectedSource || !selectedDocType) return;
    setGenerating(true);
    try {
      const data = await api.post("/auto-docs/generate", {
        source_type: selectedSource.type,
        source_id: selectedSource.id,
        doc_type: selectedDocType,
      }) as GeneratedDocFull;
      setViewingDoc(data);
      fetchHistory();
    } catch {
      alert("Generation failed. Please check that this source has been analyzed.");
    } finally {
      setGenerating(false);
    }
  };

  const handleViewDoc = async (id: number) => {
    setViewLoading(true);
    try {
      const data = await api.get(`/auto-docs/${id}`) as GeneratedDocFull;
      setViewingDoc(data);
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

  const handleDownload = (doc: GeneratedDocFull) => {
    const blob = new Blob([doc.content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${doc.doc_type}-${doc.id}.md`;
    a.click();
    URL.revokeObjectURL(url);
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
          <p className="text-sm text-gray-500">AI-generated documentation from your analyzed sources</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Generation Panel */}
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-white border rounded-xl p-5 shadow-sm space-y-4">
            <h2 className="text-sm font-semibold text-gray-800">Generate New Doc</h2>

            {/* Source selector */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1.5">Source</label>
              <select
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
                value={selectedSource ? `${selectedSource.type}:${selectedSource.id}` : ""}
                onChange={(e) => {
                  const [type, idStr] = e.target.value.split(":");
                  const item = sources.find(
                    (s) => s.type === type && s.id === parseInt(idStr, 10)
                  );
                  setSelectedSource(item || null);
                }}
              >
                <option value="">Select a source…</option>
                {sources.filter((s) => s.type === "document").length > 0 && (
                  <optgroup label="Documents">
                    {sources
                      .filter((s) => s.type === "document")
                      .map((s) => (
                        <option key={`document:${s.id}`} value={`document:${s.id}`}>
                          {s.name}
                        </option>
                      ))}
                  </optgroup>
                )}
                {sources.filter((s) => s.type === "repository").length > 0 && (
                  <optgroup label="Repositories">
                    {sources
                      .filter((s) => s.type === "repository")
                      .map((s) => (
                        <option key={`repository:${s.id}`} value={`repository:${s.id}`}>
                          {s.name}
                        </option>
                      ))}
                  </optgroup>
                )}
              </select>
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
              disabled={!selectedSource || !selectedDocType || generating}
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
                This may take 15–30 seconds for complex sources…
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
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-gray-700 truncate">{h.title}</p>
                      <p className="text-xs text-gray-400 flex items-center gap-1 mt-0.5">
                        <Clock className="w-3 h-3" />
                        {new Date(h.created_at).toLocaleDateString()}
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
              <p className="text-sm font-medium">Select a source and doc type, then click Generate</p>
              <p className="text-xs mt-1">Or click a recent generation from the history panel</p>
            </div>
          )}

          {!viewLoading && viewingDoc && (
            <div className="bg-white border rounded-xl shadow-sm overflow-hidden flex flex-col h-full">
              {/* Viewer header */}
              <div className="flex items-center justify-between px-5 py-3 border-b bg-gray-50">
                <div>
                  <h2 className="text-sm font-semibold text-gray-900 truncate max-w-lg">{viewingDoc.title}</h2>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {viewingDoc.source_name && <span>{viewingDoc.source_name} · </span>}
                    {viewingDoc.doc_type} · {new Date(viewingDoc.created_at).toLocaleString()}
                    {viewingDoc.status === "failed" && (
                      <span className="text-red-500 ml-2">⚠ Generation failed</span>
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-2">
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
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs gap-1.5"
                    onClick={() => handleDownload(viewingDoc)}
                  >
                    <Download className="w-3.5 h-3.5" /> Download .md
                  </Button>
                </div>
              </div>

              {/* Content */}
              <div className="flex-1 overflow-y-auto p-6 max-h-[calc(100vh-280px)]">
                {viewingDoc.content ? (
                  <MarkdownRenderer content={viewingDoc.content} />
                ) : (
                  <p className="text-sm text-gray-400 italic">No content generated.</p>
                )}
              </div>

              {/* Token usage footer */}
              {viewingDoc.metadata && (viewingDoc.metadata.input_tokens != null || viewingDoc.metadata.output_tokens != null) && (
                <div className="px-5 py-2 border-t bg-gray-50 flex items-center gap-4 text-xs text-gray-500">
                  <span>Input: {String(viewingDoc.metadata.input_tokens ?? 0)} tokens</span>
                  <span>Output: {String(viewingDoc.metadata.output_tokens ?? 0)} tokens</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
