"use client";

import { useCallback, useEffect, useState, useMemo, Fragment } from "react";
import {
  Network,
  GitFork,
  Layers,
  Activity,
  PlusCircle,
  RefreshCw,
  Sparkles,
  Loader2,
  AlertCircle,
  Download,
  Table2,
  Share2,
  ChevronDown,
  ChevronRight,
  Search,
  ArrowRight,
  ArrowLeft,
  Pencil,
  Trash2,
  X,
  Save,
  Circle,
  AlertTriangle,
  FileText,
  Code2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useProject } from "@/contexts/ProjectContext";
import { OntologyGraph } from "@/components/ontology/OntologyGraph";
import { ConceptDialog } from "@/components/ontology/ConceptDialog";
import { RelationshipDialog } from "@/components/ontology/RelationshipDialog";
import { MetaGraphView } from "@/components/ontology/MetaGraphView";

// --- Types ---

interface Concept {
  id: number;
  name: string;
  concept_type: string;
  description: string | null;
  confidence_score: number;
  source_type?: string;
  initiative_id?: number | null;
  is_active: boolean;
  created_at: string;
}

interface ConceptWithRelationships extends Concept {
  outgoing_relationships: Relationship[];
  incoming_relationships: Relationship[];
}

interface Relationship {
  id: number;
  source_concept_id: number;
  target_concept_id: number;
  relationship_type: string;
  description: string | null;
  confidence_score: number;
}

interface GraphNode {
  id: number;
  name: string;
  concept_type: string;
  source_type?: string;
  initiative_id?: number | null;
  confidence_score: number;
}

interface GraphEdge {
  id: number;
  source_concept_id: number;
  target_concept_id: number;
  relationship_type: string;
  confidence_score: number;
}

interface OntologyStats {
  total_concepts: number;
  total_relationships: number;
  concept_types: string[];
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
}

// --- Constants ---

const TYPE_COLORS: Record<string, { dot: string; bg: string; text: string; border: string }> = {
  Entity:    { dot: "bg-blue-500",   bg: "bg-blue-50",    text: "text-blue-700",   border: "border-blue-200" },
  Process:   { dot: "bg-green-500",  bg: "bg-green-50",   text: "text-green-700",  border: "border-green-200" },
  Attribute: { dot: "bg-amber-500",  bg: "bg-amber-50",   text: "text-amber-700",  border: "border-amber-200" },
  Value:     { dot: "bg-purple-500", bg: "bg-purple-50",  text: "text-purple-700", border: "border-purple-200" },
  Event:     { dot: "bg-red-500",    bg: "bg-red-50",     text: "text-red-700",    border: "border-red-200" },
  Role:      { dot: "bg-teal-500",   bg: "bg-teal-50",    text: "text-teal-700",   border: "border-teal-200" },
  Service:   { dot: "bg-indigo-500", bg: "bg-indigo-50",  text: "text-indigo-700", border: "border-indigo-200" },
};

const CONCEPT_TYPES = ["Entity", "Process", "Attribute", "Value", "Event", "Role", "Service"];

function getTypeStyle(type: string) {
  return TYPE_COLORS[type] || { dot: "bg-gray-400", bg: "bg-gray-50", text: "text-gray-700", border: "border-gray-200" };
}

// --- Stat Card ---

function StatCard({ title, value, icon: Icon, color }: {
  title: string; value: string | number; icon: any; color: string;
}) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500">{title}</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
        </div>
        <div className={`rounded-lg p-2.5 ${color}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

// --- Source Badge ---

function SourceBadge({ sourceType }: { sourceType?: string }) {
  if (!sourceType || sourceType === "document") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700 border border-blue-200">
        <FileText className="h-2.5 w-2.5" />
        Doc
      </span>
    );
  }
  if (sourceType === "code") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 text-[10px] font-medium text-green-700 border border-green-200">
        <Code2 className="h-2.5 w-2.5" />
        Code
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700 border border-indigo-200">
      <Layers className="h-2.5 w-2.5" />
      Both
    </span>
  );
}

// --- Confidence Bar ---

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? "bg-green-500" : score >= 0.5 ? "bg-amber-500" : "bg-red-500";
  const textColor = score >= 0.8 ? "text-green-700" : score >= 0.5 ? "text-amber-700" : "text-red-700";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full bg-gray-100">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-medium ${textColor}`}>{pct}%</span>
    </div>
  );
}

// --- Inline Edit Row ---

function ConceptEditRow({
  concept,
  allConcepts,
  onUpdate,
  onDelete,
  onDeleteRelationship,
  onAddRelationship,
  onClose,
}: {
  concept: ConceptWithRelationships;
  allConcepts: Concept[];
  onUpdate: (id: number, data: Partial<Concept>) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  onDeleteRelationship: (id: number) => Promise<void>;
  onAddRelationship: () => void;
  onClose: () => void;
}) {
  const [editName, setEditName] = useState(concept.name);
  const [editType, setEditType] = useState(concept.concept_type);
  const [editDescription, setEditDescription] = useState(concept.description || "");
  const [editConfidence, setEditConfidence] = useState(concept.confidence_score);
  const [saving, setSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const hasChanges =
    editName !== concept.name ||
    editType !== concept.concept_type ||
    editDescription !== (concept.description || "") ||
    editConfidence !== concept.confidence_score;

  const handleSave = async () => {
    setSaving(true);
    try {
      await onUpdate(concept.id, {
        name: editName,
        concept_type: editType,
        description: editDescription || null,
        confidence_score: editConfidence,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try { await onDelete(concept.id); } finally { setDeleting(false); }
  };

  const getConceptName = (id: number) => allConcepts.find((c) => c.id === id)?.name || `#${id}`;

  const outgoing = concept.outgoing_relationships || [];
  const incoming = concept.incoming_relationships || [];

  return (
    <tr>
      <td colSpan={6} className="bg-gray-50 px-4 py-4">
        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-900">Edit: {concept.name}</h3>
            <button onClick={onClose} className="rounded-md p-1 hover:bg-gray-100">
              <X className="h-4 w-4 text-gray-400" />
            </button>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
            {/* Name */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">Name</label>
              <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)}
                className="w-full rounded-md border px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            {/* Type */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">Type</label>
              <select value={editType} onChange={(e) => setEditType(e.target.value)}
                className="w-full rounded-md border bg-white px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
                {CONCEPT_TYPES.map((t) => (<option key={t} value={t}>{t}</option>))}
              </select>
            </div>
            {/* Confidence */}
            <div>
              <label className="mb-1 flex items-center justify-between text-xs font-medium text-gray-600">
                <span>Confidence</span>
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                  editConfidence >= 0.8 ? "bg-green-100 text-green-700" : editConfidence >= 0.5 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"
                }`}>{(editConfidence * 100).toFixed(0)}%</span>
              </label>
              <input type="range" min={0} max={1} step={0.05} value={editConfidence}
                onChange={(e) => setEditConfidence(parseFloat(e.target.value))}
                className="w-full accent-blue-600" />
            </div>
            {/* Description */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">Description</label>
              <input type="text" value={editDescription} onChange={(e) => setEditDescription(e.target.value)}
                placeholder="Describe this concept..."
                className="w-full rounded-md border px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
          </div>

          {/* Relationships */}
          {(outgoing.length > 0 || incoming.length > 0) && (
            <div className="mt-4 border-t pt-3">
              <div className="mb-2 flex items-center justify-between">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Relationships ({outgoing.length + incoming.length})
                </h4>
                <button onClick={onAddRelationship}
                  className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50">
                  <PlusCircle className="h-3 w-3" /> Add
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {outgoing.map((rel) => (
                  <div key={`out-${rel.id}`} className="group flex items-center gap-1.5 rounded-full border bg-white px-2.5 py-1 text-xs">
                    <ArrowRight className="h-3 w-3 text-blue-500" />
                    <span className="text-gray-600">{rel.relationship_type}</span>
                    <span className="font-medium text-gray-900">{getConceptName(rel.target_concept_id)}</span>
                    <button onClick={() => onDeleteRelationship(rel.id)}
                      className="hidden rounded-full p-0.5 text-gray-400 hover:text-red-500 group-hover:inline-flex">
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </div>
                ))}
                {incoming.map((rel) => (
                  <div key={`in-${rel.id}`} className="group flex items-center gap-1.5 rounded-full border bg-white px-2.5 py-1 text-xs">
                    <ArrowLeft className="h-3 w-3 text-green-500" />
                    <span className="font-medium text-gray-900">{getConceptName(rel.source_concept_id)}</span>
                    <span className="text-gray-600">{rel.relationship_type}</span>
                    <button onClick={() => onDeleteRelationship(rel.id)}
                      className="hidden rounded-full p-0.5 text-gray-400 hover:text-red-500 group-hover:inline-flex">
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="mt-4 flex items-center gap-2 border-t pt-3">
            {hasChanges && (
              <button onClick={handleSave} disabled={saving || !editName.trim()}
                className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50">
                {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                Save Changes
              </button>
            )}
            <button onClick={onAddRelationship}
              className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50">
              <PlusCircle className="h-3 w-3" /> Add Relationship
            </button>
            <div className="flex-1" />
            {showDeleteConfirm ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-red-600">Delete this concept?</span>
                <button onClick={() => setShowDeleteConfirm(false)}
                  className="rounded-md border px-2 py-1 text-xs text-gray-600 hover:bg-gray-50">Cancel</button>
                <button onClick={handleDelete} disabled={deleting}
                  className="flex items-center gap-1 rounded-md bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700 disabled:opacity-50">
                  {deleting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                  Delete
                </button>
              </div>
            ) : (
              <button onClick={() => setShowDeleteConfirm(true)}
                className="flex items-center gap-1.5 rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50">
                <Trash2 className="h-3 w-3" /> Delete
              </button>
            )}
          </div>
        </div>
      </td>
    </tr>
  );
}

// --- Main Page ---

type GraphLayer = "all" | "document" | "code" | "meta";
type ViewMode = "table" | "graph";

export default function OntologyDashboard() {
  // Project context — scopes all API calls to selected project
  const { selectedProject } = useProject();
  const initiativeId = selectedProject?.id ?? null;

  // Data state
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [], total_nodes: 0, total_edges: 0 });
  const [stats, setStats] = useState<OntologyStats>({ total_concepts: 0, total_relationships: 0, concept_types: [] });

  // Detail state (for inline editing)
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedDetail, setExpandedDetail] = useState<ConceptWithRelationships | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showConceptDialog, setShowConceptDialog] = useState(false);
  const [showRelDialog, setShowRelDialog] = useState(false);
  const [synonymDetecting, setSynonymDetecting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [graphLayer, setGraphLayer] = useState<GraphLayer>("all");
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"name" | "type" | "confidence" | "source">("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // Meta-graph state (cross-project view)
  const [metaGraph, setMetaGraph] = useState<any>(null);
  const [metaLoading, setMetaLoading] = useState(false);

  // --- Data Fetching ---

  const graphEndpoint = graphLayer === "all" ? "/ontology/graph"
    : graphLayer === "document" ? "/ontology/graph/document"
    : graphLayer === "code" ? "/ontology/graph/code"
    : "/ontology/graph"; // meta uses a separate fetch

  // Build query params — include initiative_id when a project is selected
  const queryParams = useMemo(() => {
    const params: Record<string, string | number | boolean> = {};
    if (initiativeId) params.initiative_id = initiativeId;
    return params;
  }, [initiativeId]);

  const fetchAll = useCallback(async () => {
    try {
      const [conceptsRes, graphRes, statsRes] = await Promise.all([
        api.get<Concept[]>("/ontology/concepts", { limit: 500, ...queryParams }),
        api.get<GraphData>(graphEndpoint, queryParams),
        api.get<OntologyStats>("/ontology/stats", queryParams),
      ]);
      setConcepts(conceptsRes);
      setGraph(graphRes);
      setStats(statsRes);
      setError("");
    } catch (err: any) {
      console.error("Failed to fetch ontology data:", err);
      setError(err.detail || "Failed to load ontology data");
    }
  }, [graphEndpoint, queryParams]);

  // Fetch meta-graph when "meta" tab is active
  const fetchMetaGraph = useCallback(async () => {
    setMetaLoading(true);
    try {
      const data = await api.get<any>("/ontology/graph/meta");
      setMetaGraph(data);
    } catch (err: any) {
      console.error("Failed to fetch meta-graph:", err);
    } finally {
      setMetaLoading(false);
    }
  }, []);

  useEffect(() => {
    if (graphLayer === "meta") {
      fetchMetaGraph();
    }
  }, [graphLayer, fetchMetaGraph]);

  const fetchConceptDetail = useCallback(async (id: number) => {
    setDetailLoading(true);
    try {
      const detail = await api.get<ConceptWithRelationships>(`/ontology/concepts/${id}`);
      setExpandedDetail(detail);
    } catch (err: any) {
      console.error("Failed to fetch concept detail:", err);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchAll().finally(() => setLoading(false));
  }, [fetchAll]);

  useEffect(() => {
    if (expandedId) {
      fetchConceptDetail(expandedId);
    } else {
      setExpandedDetail(null);
    }
  }, [expandedId, fetchConceptDetail]);

  // --- Filtered & Sorted Concepts ---

  const filteredConcepts = useMemo(() => {
    let result = concepts;

    // Layer filter
    if (graphLayer === "document") {
      result = result.filter((c) => !c.source_type || c.source_type === "document" || c.source_type === "both");
    } else if (graphLayer === "code") {
      result = result.filter((c) => c.source_type === "code" || c.source_type === "both");
    }

    // Search
    if (search) {
      const q = search.toLowerCase();
      result = result.filter((c) =>
        c.name.toLowerCase().includes(q) ||
        c.concept_type.toLowerCase().includes(q) ||
        c.description?.toLowerCase().includes(q)
      );
    }

    // Type filter
    if (filterType !== "all") {
      result = result.filter((c) => c.concept_type === filterType);
    }

    // Sort
    result = [...result].sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case "name": cmp = a.name.localeCompare(b.name); break;
        case "type": cmp = a.concept_type.localeCompare(b.concept_type); break;
        case "confidence": cmp = a.confidence_score - b.confidence_score; break;
        case "source": cmp = (a.source_type || "document").localeCompare(b.source_type || "document"); break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    return result;
  }, [concepts, graphLayer, search, filterType, sortBy, sortDir]);

  // Group by type for card view
  const groupedByType = useMemo(() => {
    const groups: Record<string, Concept[]> = {};
    filteredConcepts.forEach((c) => {
      if (!groups[c.concept_type]) groups[c.concept_type] = [];
      groups[c.concept_type].push(c);
    });
    return groups;
  }, [filteredConcepts]);

  // --- Actions ---

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchAll();
    if (expandedId) await fetchConceptDetail(expandedId);
    setRefreshing(false);
  };

  const handleCreateConcept = async (data: {
    name: string; concept_type: string; description: string; confidence_score: number;
  }) => {
    // Scope new concept to current project if one is selected
    const payload = initiativeId ? { ...data, initiative_id: initiativeId } : data;
    await api.post("/ontology/concepts", payload);
    await fetchAll();
  };

  const handleUpdateConcept = async (id: number, data: Partial<Concept>) => {
    await api.put(`/ontology/concepts/${id}`, data);
    await fetchAll();
    await fetchConceptDetail(id);
  };

  const handleDeleteConcept = async (id: number) => {
    await api.delete(`/ontology/concepts/${id}`);
    setExpandedId(null);
    setExpandedDetail(null);
    await fetchAll();
  };

  const handleCreateRelationship = async (data: {
    source_concept_id: number; target_concept_id: number;
    relationship_type: string; description: string; confidence_score: number;
  }) => {
    await api.post("/ontology/relationships", data);
    await fetchAll();
    if (expandedId) await fetchConceptDetail(expandedId);
  };

  const handleDeleteRelationship = async (relId: number) => {
    await api.delete(`/ontology/relationships/${relId}`);
    await fetchAll();
    if (expandedId) await fetchConceptDetail(expandedId);
  };

  const handleDetectSynonyms = async () => {
    setSynonymDetecting(true);
    try {
      await api.post("/ontology/synonyms/detect");
      setTimeout(async () => {
        await fetchAll();
        setSynonymDetecting(false);
      }, 5000);
    } catch {
      setSynonymDetecting(false);
    }
  };

  const handleExportGraph = () => {
    const data = JSON.stringify(graph, null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ontology-graph-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSort = (col: typeof sortBy) => {
    if (sortBy === col) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(col);
      setSortDir("asc");
    }
  };

  const toggleExpand = (id: number) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const density =
    stats.total_concepts > 1
      ? ((stats.total_relationships / (stats.total_concepts * (stats.total_concepts - 1))) * 100).toFixed(1)
      : "0.0";

  // --- Render ---

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-blue-600" />
          <p className="mt-2 text-sm text-gray-500">Loading knowledge graph...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50/50 p-4 lg:p-6">
      {/* Header */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Business Ontology
            {selectedProject && (
              <span className="ml-2 text-base font-medium text-blue-600">
                — {selectedProject.name}
              </span>
            )}
          </h1>
          <p className="mt-0.5 text-sm text-gray-500">
            {selectedProject
              ? `Knowledge graph for ${selectedProject.name} — concepts scoped to this project plus shared concepts`
              : "Knowledge graph extracted from your documents — review, curate, and connect business concepts"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={handleRefresh} disabled={refreshing}
            className="flex items-center gap-1.5 rounded-md border bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50">
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button onClick={handleExportGraph} disabled={graph.nodes.length === 0}
            className="flex items-center gap-1.5 rounded-md border bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50">
            <Download className="h-4 w-4" /> Export
          </button>
          <button onClick={handleDetectSynonyms} disabled={synonymDetecting || concepts.length < 2}
            className="flex items-center gap-1.5 rounded-md border border-purple-200 bg-purple-50 px-3 py-2 text-sm font-medium text-purple-700 hover:bg-purple-100 disabled:opacity-50">
            {synonymDetecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Detect Synonyms
          </button>
          <button onClick={async () => {
              try {
                await api.post("/ontology/extract-code-concepts");
                await fetchAll();
              } catch (e) { console.error("Code concept extraction failed:", e); }
            }}
            className="flex items-center gap-1.5 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm font-medium text-green-700 hover:bg-green-100">
            <Code2 className="h-4 w-4" /> Extract Code Concepts
          </button>
          <button onClick={() => setShowConceptDialog(true)}
            className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700">
            <PlusCircle className="h-4 w-4" /> Add Concept
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Stats Row */}
      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard title="Total Concepts" value={stats.total_concepts} icon={Network} color="bg-blue-50 text-blue-600" />
        <StatCard title="Relationships" value={stats.total_relationships} icon={GitFork} color="bg-green-50 text-green-600" />
        <StatCard title="Concept Types" value={stats.concept_types.length} icon={Layers} color="bg-amber-50 text-amber-600" />
        <StatCard title="Graph Density" value={`${density}%`} icon={Activity} color="bg-purple-50 text-purple-600" />
      </div>

      {/* Controls Bar: Layer Tabs + View Toggle + Search */}
      <div className="mb-4 flex flex-col gap-3 rounded-lg border bg-white p-3 sm:flex-row sm:items-center">
        {/* Layer Tabs */}
        <div className="flex items-center gap-1 rounded-lg bg-gray-100 p-1">
          {[
            { key: "all" as GraphLayer, label: "All", icon: Layers },
            { key: "document" as GraphLayer, label: "Document", icon: FileText },
            { key: "code" as GraphLayer, label: "Code", icon: Code2 },
            { key: "meta" as GraphLayer, label: "Meta-Graph", icon: Share2 },
          ].map((tab) => (
            <button key={tab.key} onClick={() => setGraphLayer(tab.key)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                graphLayer === tab.key ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              }`}>
              <tab.icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* View Toggle */}
        <div className="flex items-center gap-1 rounded-lg bg-gray-100 p-1">
          <button onClick={() => setViewMode("table")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              viewMode === "table" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
            }`}>
            <Table2 className="h-3.5 w-3.5" /> Table
          </button>
          <button onClick={() => setViewMode("graph")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              viewMode === "graph" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
            }`}>
            <Share2 className="h-3.5 w-3.5" /> Graph
          </button>
        </div>

        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2 h-4 w-4 text-gray-400" />
          <input type="text" placeholder="Search concepts by name, type, or description..."
            value={search} onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border py-1.5 pl-8 pr-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
        </div>

        {/* Type Filter */}
        <div className="flex flex-wrap items-center gap-1">
          <button onClick={() => setFilterType("all")}
            className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors ${
              filterType === "all" ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}>
            All
          </button>
          {stats.concept_types.map((type) => (
            <button key={type} onClick={() => setFilterType(filterType === type ? "all" : type)}
              className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors ${
                filterType === type ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}>
              {type}
            </button>
          ))}
        </div>

        {/* Count */}
        <span className="hidden whitespace-nowrap text-xs text-gray-400 sm:block">
          {filteredConcepts.length} concept{filteredConcepts.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* === META-GRAPH VIEW === */}
      {graphLayer === "meta" && (
        <div>
          {metaLoading ? (
            <div className="flex h-64 items-center justify-center rounded-lg border bg-white">
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
              <span className="ml-2 text-sm text-gray-500">Loading meta-graph...</span>
            </div>
          ) : metaGraph ? (
            <MetaGraphView data={metaGraph} />
          ) : (
            <div className="flex h-64 items-center justify-center rounded-lg border bg-white text-sm text-gray-400">
              No meta-graph data available
            </div>
          )}
        </div>
      )}

      {/* === TABLE VIEW === */}
      {graphLayer !== "meta" && viewMode === "table" && (
        <div className="overflow-x-auto rounded-lg border bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                <th className="w-8 px-4 py-3" />
                <th className="cursor-pointer px-4 py-3 hover:text-gray-700" onClick={() => handleSort("name")}>
                  <span className="flex items-center gap-1">
                    Name {sortBy === "name" && <span>{sortDir === "asc" ? "↑" : "↓"}</span>}
                  </span>
                </th>
                <th className="cursor-pointer px-4 py-3 hover:text-gray-700" onClick={() => handleSort("type")}>
                  <span className="flex items-center gap-1">
                    Type {sortBy === "type" && <span>{sortDir === "asc" ? "↑" : "↓"}</span>}
                  </span>
                </th>
                <th className="cursor-pointer px-4 py-3 hover:text-gray-700" onClick={() => handleSort("source")}>
                  <span className="flex items-center gap-1">
                    Source {sortBy === "source" && <span>{sortDir === "asc" ? "↑" : "↓"}</span>}
                  </span>
                </th>
                <th className="cursor-pointer px-4 py-3 hover:text-gray-700" onClick={() => handleSort("confidence")}>
                  <span className="flex items-center gap-1">
                    Confidence {sortBy === "confidence" && <span>{sortDir === "asc" ? "↑" : "↓"}</span>}
                  </span>
                </th>
                <th className="px-4 py-3">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredConcepts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-gray-400">
                    {search || filterType !== "all"
                      ? "No concepts match your filters"
                      : "No concepts yet — upload and analyze documents to build your ontology"}
                  </td>
                </tr>
              ) : (
                filteredConcepts.map((concept) => {
                  const isExpanded = expandedId === concept.id;
                  const style = getTypeStyle(concept.concept_type);
                  return (
                    <Fragment key={concept.id}>
                      <tr
                        className={`cursor-pointer transition-colors ${
                          isExpanded ? "bg-blue-50/50" : "hover:bg-gray-50"
                        }`}
                        onClick={() => toggleExpand(concept.id)}>
                        <td className="px-4 py-3 text-gray-400">
                          {isExpanded
                            ? <ChevronDown className="h-4 w-4" />
                            : <ChevronRight className="h-4 w-4" />}
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-medium text-gray-900">{concept.name}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${style.bg} ${style.text} border ${style.border}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
                            {concept.concept_type}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <SourceBadge sourceType={concept.source_type} />
                        </td>
                        <td className="px-4 py-3">
                          <ConfidenceBar score={concept.confidence_score} />
                        </td>
                        <td className="max-w-xs truncate px-4 py-3 text-gray-500">
                          {concept.description || "—"}
                        </td>
                      </tr>
                      {/* Inline edit panel */}
                      {isExpanded && expandedDetail && !detailLoading && (
                        <ConceptEditRow
                          key={`edit-${concept.id}`}
                          concept={expandedDetail}
                          allConcepts={concepts}
                          onUpdate={handleUpdateConcept}
                          onDelete={handleDeleteConcept}
                          onDeleteRelationship={handleDeleteRelationship}
                          onAddRelationship={() => setShowRelDialog(true)}
                          onClose={() => setExpandedId(null)}
                        />
                      )}
                      {isExpanded && detailLoading && (
                        <tr>
                          <td colSpan={6} className="bg-gray-50 px-4 py-6 text-center">
                            <Loader2 className="mx-auto h-5 w-5 animate-spin text-gray-400" />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* === GRAPH VIEW === */}
      {graphLayer !== "meta" && viewMode === "graph" && (
        <div>
          {/* Legend */}
          <div className="mb-3 flex flex-wrap items-center gap-4 rounded-lg border bg-white px-4 py-2.5">
            <span className="text-xs font-medium text-gray-500">Legend:</span>
            {stats.concept_types.map((type) => {
              const style = getTypeStyle(type);
              return (
                <div key={type} className="flex items-center gap-1.5">
                  <span className={`inline-block h-2.5 w-2.5 rounded-sm ${style.dot}`} />
                  <span className="text-xs text-gray-600">{type}</span>
                </div>
              );
            })}
            <div className="ml-auto flex items-center gap-3 text-xs text-gray-400">
              <span>Confidence:</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-green-500" /> High</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-500" /> Med</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-500" /> Low</span>
            </div>
          </div>

          {/* Scrollable Graph */}
          <OntologyGraph
            nodes={graph.nodes}
            edges={graph.edges}
            selectedId={expandedId}
            onSelectNode={(id) => setExpandedId(id)}
          />

          {/* Selected concept detail below graph */}
          {expandedId && expandedDetail && !detailLoading && (
            <div className="mt-3 rounded-lg border bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-900">
                  Selected: {expandedDetail.name}
                  <span className="ml-2 text-xs font-normal text-gray-500">({expandedDetail.concept_type})</span>
                </h3>
                <button onClick={() => setExpandedId(null)} className="rounded-md p-1 hover:bg-gray-100">
                  <X className="h-4 w-4 text-gray-400" />
                </button>
              </div>
              {expandedDetail.description && (
                <p className="mb-2 text-sm text-gray-600">{expandedDetail.description}</p>
              )}
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <SourceBadge sourceType={expandedDetail.source_type} />
                <ConfidenceBar score={expandedDetail.confidence_score} />
                <span>
                  {(expandedDetail.outgoing_relationships?.length || 0) + (expandedDetail.incoming_relationships?.length || 0)} relationships
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Dialogs */}
      <ConceptDialog
        open={showConceptDialog}
        onClose={() => setShowConceptDialog(false)}
        onCreate={handleCreateConcept}
      />
      <RelationshipDialog
        open={showRelDialog}
        onClose={() => setShowRelDialog(false)}
        concepts={concepts}
        onCreate={handleCreateRelationship}
        preselectedSourceId={expandedId}
      />
    </div>
  );
}
