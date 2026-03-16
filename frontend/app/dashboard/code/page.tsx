"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Code2,
  Plus,
  FileCode,
  Globe,
  GitBranch,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  Search,
  Filter,
  RefreshCw,
  AlertCircle,
  Trash2,
  ChevronRight,
  ChevronDown,
  FolderGit2,
  Folder,
  FolderOpen,
  File,
  Sparkles,
  EyeOff,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useRouter } from "next/navigation";
import Link from "next/link";

// --- Types ---

interface Repository {
  id: number;
  name: string;
  url: string;
  default_branch: string;
  description: string | null;
  analysis_status: string;
  analyzed_files: number | null;
  total_files: number | null;
  total_ai_cost_inr: number | null;
  created_at: string;
}

interface CodeComponent {
  id: number;
  name: string;
  component_type: string;
  location: string;
  version: string;
  summary: string | null;
  analysis_status: "pending" | "processing" | "completed" | "failed" | "redirected";
  ai_cost_inr: number | null;
  token_count_input: number | null;
  token_count_output: number | null;
  analysis_started_at: string | null;
  analysis_completed_at: string | null;
  repository_id: number | null;
  repo_analyzed_files: number | null;
  repo_total_files: number | null;
  repo_analysis_status: string | null;
}

/** Format seconds into human-readable elapsed time */
function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

/** Return elapsed seconds since a given ISO timestamp */
function elapsedSince(isoTimestamp: string | null): number {
  if (!isoTimestamp) return 0;
  return Math.max(0, Math.round((Date.now() - new Date(isoTimestamp).getTime()) / 1000));
}

// --- File Tree Types & Helpers ---

interface TreeFile {
  type: "file";
  name: string;
  path: string;
  component: CodeComponent;
}

interface TreeFolder {
  type: "folder";
  name: string;
  path: string;
  children: TreeNode[];
}

type TreeNode = TreeFolder | TreeFile;

/** Strip the longest common directory prefix shared by all files.
 *  E.g. all paths starting with "https:/raw.githubusercontent.com/org/repo/branch/"
 *  get trimmed so the tree starts at the real project root. */
function stripCommonPrefix(paths: string[]): string[] {
  if (paths.length === 0) return [];
  const split = paths.map((p) => p.split("/"));
  const minLen = Math.min(...split.map((p) => p.length));
  let common = 0;
  for (let i = 0; i < minLen - 1; i++) {
    // Keep iterating while every path shares the same segment
    if (split.every((p) => p[i] === split[0][i])) common++;
    else break;
  }
  return paths.map((p) => p.split("/").slice(common).join("/"));
}

/** Collapse single-child folder chains: a/ → b/ → file becomes "a/b/" as one node. */
function collapseSingleChildFolders(node: TreeFolder): TreeFolder {
  const collapsedChildren: TreeNode[] = node.children.map((child) => {
    if (child.type !== "folder") return child;
    const collapsed = collapseSingleChildFolders(child);
    // Merge while the folder has exactly one child that is also a folder
    let current = collapsed;
    let mergedName = current.name;
    let mergedPath = current.path;
    while (current.children.length === 1 && current.children[0].type === "folder") {
      current = current.children[0] as TreeFolder;
      mergedName = `${mergedName}/${current.name}`;
      mergedPath = current.path;
    }
    return { ...current, name: mergedName, path: mergedPath };
  });
  return { ...node, children: collapsedChildren };
}

function buildFileTree(components: CodeComponent[]): TreeFolder {
  const root: TreeFolder = { type: "folder", name: "", path: "", children: [] };
  const sorted = [...components].sort((a, b) => {
    const order: Record<string, number> = { processing: 0, pending: 1, failed: 2, completed: 3, redirected: 3 };
    return (order[a.analysis_status] ?? 2) - (order[b.analysis_status] ?? 2);
  });

  // Normalize all paths first, then strip common URL/path prefix
  const normalized = sorted.map((comp) =>
    comp.location.replace(/^\.\//, "").replace(/\\/g, "/")
  );
  const trimmed = stripCommonPrefix(normalized);

  for (let i = 0; i < sorted.length; i++) {
    const comp = sorted[i];
    const path = trimmed[i] || normalized[i];
    const parts = path.split("/").filter(Boolean);
    const fileName = parts[parts.length - 1];
    const dirParts = parts.slice(0, -1);
    let current = root;
    let currentPath = "";
    for (const part of dirParts) {
      currentPath = currentPath ? `${currentPath}/${part}` : part;
      let child = current.children.find(
        (c): c is TreeFolder => c.type === "folder" && c.name === part
      );
      if (!child) {
        child = { type: "folder", name: part, path: currentPath, children: [] };
        current.children.push(child);
      }
      current = child;
    }
    current.children.push({ type: "file", name: fileName, path, component: comp });
  }

  // Collapse single-child folder chains to reduce visual noise
  return collapseSingleChildFolders(root);
}

function countFolder(folder: TreeFolder): { total: number; completed: number; processing: number; failed: number; pending: number } {
  let total = 0, completed = 0, processing = 0, failed = 0, pending = 0;
  function traverse(node: TreeNode) {
    if (node.type === "file") {
      total++;
      const s = node.component.analysis_status;
      if (s === "completed" || s === "redirected") completed++;
      else if (s === "processing") processing++;
      else if (s === "failed") failed++;
      else pending++;
    } else {
      for (const child of node.children) traverse(child);
    }
  }
  for (const child of folder.children) traverse(child);
  return { total, completed, processing, failed, pending };
}

interface FileTreeRowsProps {
  nodes: TreeNode[];
  depth: number;
  expandedFolders: Set<string>;
  onToggleFolder: (path: string) => void;
  fileIndexRef: { value: number };
  onFileClick: (id: number) => void;
  retryingIds: Set<number>;
  onRetry: (id: number, e: any) => void;
  getStatusBadge: (status: string) => JSX.Element;
  getStatusIcon: (status: string) => JSX.Element;
}

function FileTreeRows({
  nodes, depth, expandedFolders, onToggleFolder,
  fileIndexRef, onFileClick, retryingIds, onRetry,
  getStatusBadge, getStatusIcon,
}: FileTreeRowsProps): JSX.Element {
  return (
    <>
      {nodes.map((node) => {
        if (node.type === "folder") {
          const isExpanded = expandedFolders.has(node.path);
          const counts = countFolder(node);
          return (
            <div key={node.path}>
              {/* Folder row */}
              <div
                className="flex items-center gap-2 px-3 py-1.5 hover:bg-muted/40 cursor-pointer border-b border-muted/30 select-none"
                style={{ paddingLeft: `${depth * 16 + 12}px` }}
                onClick={() => onToggleFolder(node.path)}
              >
                <span className="text-muted-foreground flex-shrink-0">
                  {isExpanded
                    ? <ChevronDown className="w-3.5 h-3.5" />
                    : <ChevronRight className="w-3.5 h-3.5" />}
                </span>
                {isExpanded
                  ? <FolderOpen className="w-4 h-4 text-yellow-500 flex-shrink-0" />
                  : <Folder className="w-4 h-4 text-yellow-500 flex-shrink-0" />}
                <span className="text-sm font-medium flex-1 min-w-0">{node.name}/</span>
                <div className="text-xs flex-shrink-0 ml-auto flex items-center gap-2 text-muted-foreground">
                  {counts.processing > 0 && <span className="text-blue-500">{counts.processing} analyzing</span>}
                  {counts.failed > 0 && <span className="text-red-500">{counts.failed} failed</span>}
                  {counts.pending > 0 && <span className="text-amber-500">{counts.pending} pending</span>}
                  <span className={counts.completed === counts.total ? "text-green-600 font-medium" : ""}>
                    {counts.completed}/{counts.total} files
                  </span>
                </div>
              </div>
              {/* Children */}
              {isExpanded && (
                <FileTreeRows
                  nodes={node.children}
                  depth={depth + 1}
                  expandedFolders={expandedFolders}
                  onToggleFolder={onToggleFolder}
                  fileIndexRef={fileIndexRef}
                  onFileClick={onFileClick}
                  retryingIds={retryingIds}
                  onRetry={onRetry}
                  getStatusBadge={getStatusBadge}
                  getStatusIcon={getStatusIcon}
                />
              )}
            </div>
          );
        } else {
          // File row
          const comp = node.component;
          const idx = ++fileIndexRef.value;
          return (
            <div
              key={comp.id}
              className={`grid items-center border-b border-muted/20 text-sm hover:bg-muted/30 cursor-pointer ${
                comp.analysis_status === "processing"
                  ? "bg-blue-50/70 dark:bg-blue-950/30 border-l-2 border-l-blue-500"
                  : comp.analysis_status === "pending"
                    ? "bg-amber-50/50 dark:bg-amber-950/20 border-l-2 border-l-amber-400"
                    : comp.analysis_status === "failed"
                      ? "bg-red-50/50 dark:bg-red-950/20 border-l-2 border-l-red-400"
                      : ""
              }`}
              style={{ gridTemplateColumns: "44px 1fr 80px 120px 70px 80px 80px" }}
              onClick={() => onFileClick(comp.id)}
            >
              <div className="text-center text-xs text-muted-foreground font-mono py-2">{idx}</div>
              <div className="flex items-center gap-2 py-2 min-w-0" style={{ paddingLeft: `${depth * 16 + 8}px` }}>
                <File className={`w-4 h-4 flex-shrink-0 ${comp.analysis_status === "failed" ? "text-red-400" : "text-muted-foreground"}`} />
                <div className="min-w-0">
                  <span className="truncate text-sm block">{node.name}</span>
                  {comp.analysis_status === "failed" && comp.summary && (() => {
                    let errorMsg = comp.summary;
                    let solution: string | null = null;
                    const nlSplit = comp.summary.split("\nSolution: ");
                    if (nlSplit.length >= 2) {
                      errorMsg = nlSplit[0];
                      solution = nlSplit.slice(1).join("\nSolution: ");
                    } else {
                      const solIdx = comp.summary.indexOf("Solution:");
                      if (solIdx > 0) {
                        errorMsg = comp.summary.slice(0, solIdx).trim();
                        solution = comp.summary.slice(solIdx + 9).trim();
                      }
                    }
                    return (
                      <div className="mt-1 space-y-0.5">
                        <div className="flex items-start gap-1">
                          <AlertCircle className="w-3 h-3 text-red-500 mt-0.5 flex-shrink-0" />
                          <span className="text-xs text-red-600 font-medium block" title={errorMsg}>
                            {errorMsg.length > 90 ? errorMsg.slice(0, 88) + "..." : errorMsg}
                          </span>
                        </div>
                        {solution && (
                          <div className="flex items-start gap-1 ml-4">
                            <span className="text-xs text-amber-600 bg-amber-50 dark:bg-amber-950 rounded px-1.5 py-0.5 block" title={solution}>
                              {solution.length > 100 ? solution.slice(0, 98) + "..." : solution}
                            </span>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              </div>
              <div className="text-xs font-mono text-muted-foreground px-2 py-2">
                {comp.version
                  ? <span title={comp.version}>{comp.version.length > 8 ? comp.version.slice(0, 7) + "…" : comp.version}</span>
                  : <span className="text-gray-400">—</span>}
              </div>
              <div className="flex items-center gap-1.5 px-2 py-2">
                {getStatusIcon(comp.analysis_status)}
                {getStatusBadge(comp.analysis_status)}
              </div>
              <div className="text-right text-sm text-muted-foreground px-2 py-2">
                {comp.analysis_started_at && comp.analysis_completed_at
                  ? formatElapsed(Math.round((new Date(comp.analysis_completed_at).getTime() - new Date(comp.analysis_started_at).getTime()) / 1000))
                  : comp.analysis_status === "processing" && comp.analysis_started_at
                    ? <span className="font-mono text-blue-600">{formatElapsed(elapsedSince(comp.analysis_started_at))}</span>
                    : "—"}
              </div>
              <div className="text-right font-mono text-sm px-2 py-2">
                {comp.ai_cost_inr != null && comp.ai_cost_inr > 0
                  ? <span className="text-green-700">&#8377;{comp.ai_cost_inr.toFixed(2)}</span>
                  : comp.analysis_status === "completed"
                    ? <span className="text-muted-foreground text-xs">cached</span>
                    : <span className="text-muted-foreground">—</span>}
              </div>
              <div className="text-right px-2 py-2">
                {comp.analysis_status === "failed" && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2 text-xs border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700"
                    disabled={retryingIds.has(comp.id)}
                    onClick={(e) => { e.stopPropagation(); onRetry(comp.id, e); }}
                  >
                    {retryingIds.has(comp.id)
                      ? <Loader2 className="w-3 h-3 animate-spin mr-1" />
                      : <RefreshCw className="w-3 h-3 mr-1" />}
                    Retry
                  </Button>
                )}
              </div>
            </div>
          );
        }
      })}
    </>
  );
}

export default function CodePage() {
  // --- State: Repositories (primary view) ---
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [standaloneComponents, setStandaloneComponents] = useState<CodeComponent[]>([]);
  const [expandedRepos, setExpandedRepos] = useState<Set<number>>(new Set());
  const [repoComponents, setRepoComponents] = useState<Record<number, CodeComponent[]>>({});
  const [loadingRepoComponents, setLoadingRepoComponents] = useState<Set<number>>(new Set());
  const [repoStats, setRepoStats] = useState<Record<number, any>>({});
  const [expandedFolders, setExpandedFolders] = useState<Record<number, Set<string>>>({});
  const [expandedSkipped, setExpandedSkipped] = useState<Set<number>>(new Set());
  const [expandedSkippedCategories, setExpandedSkippedCategories] = useState<Record<number, Set<string>>>({});

  // --- State: UI ---
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [newComponent, setNewComponent] = useState({
    name: "",
    component_type: "File",
    location: "",
    version: "",
  });
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const router = useRouter();
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Scroll position preservation — prevent auto-scroll to top on polling re-renders
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const savedScrollRef = useRef<number>(0);

  // --- Data Fetching ---

  const fetchData = useCallback(async (showRefreshing = false) => {
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setIsLoading(false);
      return;
    }
    if (showRefreshing) setIsRefreshing(true);
    try {
      // Fetch repositories and standalone components in parallel
      const [reposRes, standaloneRes] = await Promise.all([
        fetch("http://localhost:8000/api/v1/repositories/", {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch("http://localhost:8000/api/v1/code-components/?standalone=true", {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (reposRes.ok) {
        const repos = await reposRes.json();
        setRepositories(repos);
      } else {
        setRepositories([]);
      }

      if (standaloneRes.ok) {
        const standalone = await standaloneRes.json();
        setStandaloneComponents(standalone);
      } else {
        setStandaloneComponents([]);
      }
    } catch (error) {
      console.error("Failed to fetch data:", error);
      setRepositories([]);
      setStandaloneComponents([]);
    } finally {
      setIsLoading(false);
      if (showRefreshing) setIsRefreshing(false);
    }
  }, []);

  const fetchRepoComponents = useCallback(async (repoId: number, isPolling = false) => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;

    // Only show loading spinner on first load, not polling updates
    if (!isPolling) {
      setLoadingRepoComponents((prev) => new Set(prev).add(repoId));
    }
    try {
      const res = await fetch(
        `http://localhost:8000/api/v1/repositories/${repoId}/components?limit=500`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        // Preserve scroll position during polling updates
        if (isPolling && scrollContainerRef.current) {
          savedScrollRef.current = scrollContainerRef.current.scrollTop;
        }
        setRepoComponents((prev) => ({ ...prev, [repoId]: data }));
        // Auto-expand root-level folders on first load (not polling)
        if (!isPolling) {
          const rootFolders = new Set<string>();
          for (const comp of data) {
            const parts = comp.location.replace(/^\.\//, "").split("/");
            if (parts.length > 1) rootFolders.add(parts[0]);
          }
          if (rootFolders.size > 0) {
            setExpandedFolders((prev) => prev[repoId] ? prev : { ...prev, [repoId]: rootFolders });
          }
        }
        // Restore scroll after React re-render
        if (isPolling) {
          requestAnimationFrame(() => {
            if (scrollContainerRef.current) {
              scrollContainerRef.current.scrollTop = savedScrollRef.current;
            }
          });
        }
      }
    } catch (error) {
      console.error(`Failed to fetch components for repo ${repoId}:`, error);
    } finally {
      if (!isPolling) {
        setLoadingRepoComponents((prev) => {
          const next = new Set(prev);
          next.delete(repoId);
          return next;
        });
      }
    }
  }, []);

  // --- Fetch Repo Stats ---

  const fetchRepoStats = useCallback(async (repoId: number) => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    try {
      const res = await fetch(`http://localhost:8000/api/v1/repositories/${repoId}/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setRepoStats((prev) => ({ ...prev, [repoId]: data }));
      }
    } catch (error) {
      console.error(`Failed to fetch stats for repo ${repoId}:`, error);
    }
  }, []);

  // --- Expand/Collapse ---

  const toggleRepo = useCallback(
    (repoId: number) => {
      setExpandedRepos((prev) => {
        const next = new Set(prev);
        if (next.has(repoId)) {
          next.delete(repoId);
        } else {
          next.add(repoId);
          // Lazy-fetch components on first expand
          if (!repoComponents[repoId]) {
            fetchRepoComponents(repoId);
          }
          // Fetch stats for expanded repo
          if (!repoStats[repoId]) {
            fetchRepoStats(repoId);
          }
        }
        return next;
      });
    },
    [repoComponents, fetchRepoComponents, repoStats, fetchRepoStats]
  );

  const toggleFolder = useCallback((repoId: number, folderPath: string) => {
    setExpandedFolders((prev) => {
      const current = new Set(prev[repoId] ?? []);
      if (current.has(folderPath)) current.delete(folderPath);
      else current.add(folderPath);
      return { ...prev, [repoId]: current };
    });
  }, []);

  const toggleSkippedSection = useCallback((repoId: number) => {
    setExpandedSkipped((prev) => {
      const next = new Set(prev);
      if (next.has(repoId)) next.delete(repoId); else next.add(repoId);
      return next;
    });
  }, []);

  const toggleSkippedCategory = useCallback((repoId: number, category: string) => {
    setExpandedSkippedCategories((prev) => {
      const current = new Set(prev[repoId] ?? []);
      if (current.has(category)) current.delete(category); else current.add(category);
      return { ...prev, [repoId]: current };
    });
  }, []);

  // Check if any repo is actively being analyzed
  const hasActiveAnalysis = repositories.some(
    (r) => r.analysis_status === "analyzing" || r.analysis_status === "pending"
  );

  // Smart polling
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    if (hasActiveAnalysis) {
      pollIntervalRef.current = setInterval(() => {
        // Save scroll position before polling re-renders
        if (scrollContainerRef.current) {
          savedScrollRef.current = scrollContainerRef.current.scrollTop;
        }
        fetchData();
        // Also refresh expanded repos so file-level progress updates live
        for (const repoId of expandedRepos) {
          fetchRepoComponents(repoId, true);
        }
        // Restore scroll after data update
        requestAnimationFrame(() => {
          if (scrollContainerRef.current) {
            scrollContainerRef.current.scrollTop = savedScrollRef.current;
          }
        });
      }, 8000);
    }
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [hasActiveAnalysis, fetchData, expandedRepos, fetchRepoComponents]);

  useEffect(() => {
    if (!hasActiveAnalysis) return;
    const ticker = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(ticker);
  }, [hasActiveAnalysis]);

  // --- Filtering ---

  const filteredRepos = repositories.filter((r) => {
    const matchesSearch =
      !searchTerm ||
      r.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.url.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || r.analysis_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const filteredStandalone = standaloneComponents.filter((c) => {
    const matchesSearch =
      !searchTerm ||
      c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.location.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || c.analysis_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // --- Handlers ---

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setNewComponent((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmissionError(null);
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setSubmissionError("Authentication error. Please log in again.");
      setIsSubmitting(false);
      return;
    }
    try {
      const res = await fetch("http://localhost:8000/api/v1/code-components/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(newComponent),
      });
      if (res.ok) {
        setIsDialogOpen(false);
        setNewComponent({ name: "", component_type: "File", location: "", version: "" });
        setSuccessMessage("Component registered! Analysis is running in the background.");
        setTimeout(() => setSuccessMessage(null), 6000);
        fetchData(true);
      } else {
        const errorData = await res.json();
        throw new Error(errorData.detail?.[0]?.msg || errorData.detail || "Failed to create component.");
      }
    } catch (error: any) {
      setSubmissionError(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteRepo = async (repoId: number) => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    try {
      const res = await fetch(`http://localhost:8000/api/v1/repositories/${repoId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) fetchData(true);
    } catch (error) {
      console.error("Error deleting repository:", error);
    }
  };

  const handleDeleteComponent = async (id: number) => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    try {
      const res = await fetch(`http://localhost:8000/api/v1/code-components/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) fetchData(true);
    } catch (error) {
      console.error("Error deleting component:", error);
    }
  };

  // --- Retry failed component ---

  const [retryingIds, setRetryingIds] = useState<Set<number>>(new Set());

  const handleRetryComponent = async (compId: number, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent row click navigation
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    setRetryingIds((prev) => new Set(prev).add(compId));
    try {
      const res = await fetch(`http://localhost:8000/api/v1/code-components/${compId}/retry`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setSuccessMessage("Retry started for the component. Analysis running in background.");
        setTimeout(() => setSuccessMessage(null), 5000);
        // Re-fetch to show updated status
        fetchData(true);
        // Also refresh expanded repo components
        for (const repoId of expandedRepos) {
          fetchRepoComponents(repoId);
        }
      } else {
        const err = await res.json();
        setSubmissionError(err.detail || "Retry failed");
        setTimeout(() => setSubmissionError(null), 5000);
      }
    } catch (error) {
      console.error("Failed to retry component:", error);
    } finally {
      setRetryingIds((prev) => {
        const next = new Set(prev);
        next.delete(compId);
        return next;
      });
    }
  };

  // --- Retry All Failed ---

  const [retryingAllRepo, setRetryingAllRepo] = useState<number | null>(null);

  // --- Re-Analyze with File Selection ---
  const [reanalyzeRepoId, setReanalyzeRepoId] = useState<number | null>(null);
  const [reanalyzeSearch, setReanalyzeSearch] = useState("");
  const [reanalyzeSelected, setReanalyzeSelected] = useState<Set<number>>(new Set());
  const [reanalyzeSubmitting, setReanalyzeSubmitting] = useState(false);

  const handleRetryAllFailed = async (repoId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    setRetryingAllRepo(repoId);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/repositories/${repoId}/retry-failed`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSuccessMessage(`Retrying ${data.failed_count} failed files sequentially (rate-limited).`);
        setTimeout(() => setSuccessMessage(null), 6000);
        fetchData(true);
        if (expandedRepos.has(repoId)) {
          fetchRepoComponents(repoId);
        }
      } else {
        const err = await res.json();
        setSubmissionError(err.detail || "Retry all failed");
        setTimeout(() => setSubmissionError(null), 5000);
      }
    } catch (error) {
      console.error("Failed to retry all:", error);
    } finally {
      setRetryingAllRepo(null);
    }
  };

  // --- Re-Analyze Selected Files ---

  const openReanalyzeDialog = (repoId: number) => {
    const comps = repoComponents[repoId] || [];
    setReanalyzeRepoId(repoId);
    setReanalyzeSearch("");
    // Select all files by default
    setReanalyzeSelected(new Set(comps.map((c) => c.id)));
  };

  const handleReanalyze = async () => {
    if (!reanalyzeRepoId || reanalyzeSelected.size === 0) return;
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    setReanalyzeSubmitting(true);
    try {
      // Get the selected component IDs and build file_list for the analyze endpoint
      const comps = repoComponents[reanalyzeRepoId] || [];
      const selectedComps = comps.filter((c) => reanalyzeSelected.has(c.id));
      const fileList = selectedComps.map((c) => ({
        path: c.location || c.name,
        url: c.location || "",
        language: "",
      }));

      // Reset selected components to pending first
      for (const comp of selectedComps) {
        await fetch(`http://localhost:8000/api/v1/code-components/${comp.id}/retry`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      }

      setSuccessMessage(`Re-analyzing ${selectedComps.length} files. Progress will update live.`);
      setTimeout(() => setSuccessMessage(null), 6000);
      setReanalyzeRepoId(null);
      fetchData(true);
      if (expandedRepos.has(reanalyzeRepoId)) {
        fetchRepoComponents(reanalyzeRepoId);
      }
    } catch (error) {
      console.error("Failed to trigger re-analysis:", error);
      setSubmissionError("Failed to trigger re-analysis");
      setTimeout(() => setSubmissionError(null), 5000);
    } finally {
      setReanalyzeSubmitting(false);
    }
  };

  // --- Status Helpers ---

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return <Badge variant="success">completed</Badge>;
      case "analyzing":
      case "processing":
        return <Badge variant="default">analyzing</Badge>;
      case "failed":
        return <Badge variant="destructive">failed</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      case "analyzing":
      case "processing":
        return <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />;
      case "failed":
        return <XCircle className="w-4 h-4 text-red-600" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  // --- Stats ---

  const repoStatusCounts = {
    total: repositories.length,
    completed: repositories.filter((r) => r.analysis_status === "completed").length,
    analyzing: repositories.filter((r) => r.analysis_status === "analyzing").length,
    failed: repositories.filter((r) => r.analysis_status === "failed").length,
    pending: repositories.filter(
      (r) => !["completed", "analyzing", "failed"].includes(r.analysis_status)
    ).length,
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div ref={scrollContainerRef} className="p-6 space-y-6 h-full overflow-y-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
            <Code2 className="w-6 h-6 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Code Repository Library</h1>
            <p className="text-muted-foreground">
              Manage and analyze your repositories and code components
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <Link
            href="/dashboard/chat?repo=0"
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-purple-600 bg-purple-50 hover:bg-purple-100 rounded-lg transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            Ask AI about code
          </Link>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchData(true)}
            disabled={isRefreshing}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Dialog
            open={isDialogOpen}
            onOpenChange={(open) => {
              setIsDialogOpen(open);
              setSubmissionError(null);
            }}
          >
            <DialogTrigger asChild>
              <Button onClick={() => setIsDialogOpen(true)} className="bg-blue-600 hover:bg-blue-700">
                <Plus className="w-4 h-4 mr-2" /> Add Component
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle className="flex items-center space-x-2">
                  <FileCode className="w-5 h-5" />
                  <span>Register New Component</span>
                </DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <Label htmlFor="name" className="text-sm font-medium">Component Name</Label>
                  <Input id="name" name="name" value={newComponent.name} onChange={handleInputChange}
                    placeholder="e.g., Authentication Service" className="mt-1" required />
                </div>
                <div>
                  <Label htmlFor="component_type" className="text-sm font-medium">Component Type</Label>
                  <select id="component_type" name="component_type" value={newComponent.component_type}
                    onChange={handleInputChange}
                    className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm mt-1">
                    <option value="File">File</option>
                    <option value="Repository">Repository</option>
                    <option value="Class">Class</option>
                    <option value="Function">Function</option>
                  </select>
                </div>
                <div>
                  <Label htmlFor="location" className="text-sm font-medium">Location URL</Label>
                  <div className="relative mt-1">
                    <Globe className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                    <Input id="location" name="location" value={newComponent.location}
                      onChange={handleInputChange} placeholder="https://..." className="pl-10" required />
                  </div>
                </div>
                <div>
                  <Label htmlFor="version" className="text-sm font-medium">Version / Git Hash</Label>
                  <div className="relative mt-1">
                    <GitBranch className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                    <Input id="version" name="version" value={newComponent.version}
                      onChange={handleInputChange} placeholder="v1.0.0 or commit hash" className="pl-10" required />
                  </div>
                </div>
                {submissionError && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Registration Failed</AlertTitle>
                    <AlertDescription>{submissionError}</AlertDescription>
                  </Alert>
                )}
                <div className="flex space-x-2 pt-4">
                  <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)}
                    className="flex-1" disabled={isSubmitting}>Cancel</Button>
                  <Button type="submit" className="flex-1 bg-blue-600 hover:bg-blue-700" disabled={isSubmitting}>
                    {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {isSubmitting ? "Registering..." : "Register Component"}
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {successMessage && (
        <Alert className="border-green-200 bg-green-50 dark:bg-green-950 dark:border-green-800">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800 dark:text-green-200">
            {successMessage}
          </AlertDescription>
        </Alert>
      )}

      {submissionError && (
        <Alert className="border-red-200 bg-red-50 dark:bg-red-950 dark:border-red-800">
          <AlertCircle className="h-4 w-4 text-red-600" />
          <AlertDescription className="text-red-800 dark:text-red-200">
            {submissionError}
          </AlertDescription>
        </Alert>
      )}

      {/* Stats Cards — Repo-level */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Repositories</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{repoStatusCounts.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-green-600">Completed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{repoStatusCounts.completed}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-blue-600">Analyzing</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{repoStatusCounts.analyzing}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-red-600">Failed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{repoStatusCounts.failed}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              Standalone
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-500">{standaloneComponents.length}</div>
          </CardContent>
        </Card>
      </div>

      {/* Component-Level Aggregate Stats */}
      {(() => {
        const allComponents = Object.values(repoComponents).flat();
        if (allComponents.length === 0) return null;
        const totalFiles = allComponents.length;
        const completedFiles = allComponents.filter(c => c.analysis_status === "completed").length;
        const failedFiles = allComponents.filter(c => c.analysis_status === "failed").length;
        const processingFiles = allComponents.filter(c => c.analysis_status === "processing").length;
        const totalCostAll = allComponents.reduce((sum, c) => sum + (c.ai_cost_inr || 0), 0);
        const successRate = totalFiles > 0 ? Math.round((completedFiles / totalFiles) * 100) : 0;
        const avgCost = completedFiles > 0 ? totalCostAll / completedFiles : 0;

        return (
          <div className="rounded-lg border bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-950 dark:to-gray-950 p-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-1.5 text-sm font-medium text-foreground">
                <FileCode className="w-4 h-4" />
                File Analysis Overview
              </div>
              <div className="flex items-center gap-4 flex-wrap text-xs">
                <span className="font-mono">{totalFiles} files loaded</span>
                <span className="text-green-600 font-medium">{completedFiles} done ({successRate}%)</span>
                {processingFiles > 0 && (
                  <span className="text-blue-600 font-medium">{processingFiles} in progress</span>
                )}
                {failedFiles > 0 && (
                  <span className="text-red-600 font-semibold">{failedFiles} failed</span>
                )}
                {totalCostAll > 0 && (
                  <span className="font-mono text-green-700">&#8377;{totalCostAll.toFixed(2)} total</span>
                )}
                {avgCost > 0 && (
                  <span className="font-mono text-muted-foreground">~&#8377;{avgCost.toFixed(2)}/file</span>
                )}
              </div>
            </div>
            {/* Progress bar */}
            {totalFiles > 0 && (
              <div className="mt-2 h-2 w-full rounded-full bg-gray-200 dark:bg-gray-800 overflow-hidden flex">
                {completedFiles > 0 && (
                  <div className="h-full bg-green-500" style={{ width: `${(completedFiles / totalFiles) * 100}%` }} />
                )}
                {processingFiles > 0 && (
                  <div className="h-full bg-blue-500 animate-pulse" style={{ width: `${(processingFiles / totalFiles) * 100}%` }} />
                )}
                {failedFiles > 0 && (
                  <div className="h-full bg-red-500" style={{ width: `${(failedFiles / totalFiles) * 100}%` }} />
                )}
              </div>
            )}
          </div>
        );
      })()}

      {/* Search & Filter */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search repositories or components..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-muted-foreground" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="all">All Statuses</option>
                <option value="completed">Completed</option>
                <option value="analyzing">Analyzing</option>
                <option value="failed">Failed</option>
                <option value="pending">Pending</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Repositories — Expandable Rows */}
      <Card>
        <CardHeader>
          <CardTitle>Repositories ({filteredRepos.length})</CardTitle>
          <CardDescription>
            Click a repository to expand and view its analyzed files
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredRepos.length === 0 && filteredStandalone.length === 0 ? (
            <div className="text-center py-8">
              <Code2 className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">
                {repositories.length === 0
                  ? "No repositories onboarded yet"
                  : "No repositories match your filters"}
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              {filteredRepos.map((repo) => {
                const isExpanded = expandedRepos.has(repo.id);
                const components = repoComponents[repo.id] || [];
                const isLoadingComponents = loadingRepoComponents.has(repo.id);
                const analyzed = repo.analyzed_files ?? 0;
                const total = repo.total_files ?? 0;
                const pct = total > 0 ? Math.round((analyzed / total) * 100) : 0;

                return (
                  <Collapsible key={repo.id} open={isExpanded} onOpenChange={() => toggleRepo(repo.id)}>
                    {/* Repo Row */}
                    <div className="flex items-center border rounded-lg px-4 py-3 hover:bg-muted/50 transition-colors group">
                      <CollapsibleTrigger asChild>
                        <button className="flex items-center flex-1 text-left gap-3">
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                          )}
                          <FolderGit2 className="w-5 h-5 text-blue-500 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="font-medium truncate">{repo.name}</div>
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <span className="truncate">{repo.url}</span>
                              <span className="inline-flex items-center gap-0.5 bg-slate-100 dark:bg-slate-800 rounded px-1.5 py-0.5 font-mono text-[10px] flex-shrink-0">
                                <GitBranch className="w-2.5 h-2.5" />
                                {repo.default_branch}
                              </span>
                            </div>
                          </div>
                        </button>
                      </CollapsibleTrigger>

                      <div className="flex items-center gap-4 flex-shrink-0 ml-4">
                        {/* Status */}
                        <div className="flex items-center gap-1.5">
                          {getStatusIcon(repo.analysis_status)}
                          {getStatusBadge(repo.analysis_status)}
                        </div>

                        {/* Files progress */}
                        <div className="text-sm text-muted-foreground w-28 text-right">
                          {total > 0 ? (
                            <span className="font-mono">
                              {analyzed}/{repoStats[repo.id]?.total_repo_files ?? total} files
                            </span>
                          ) : (
                            <span>—</span>
                          )}
                        </div>

                        {/* Cost */}
                        <div className="text-sm font-mono w-20 text-right">
                          {repo.total_ai_cost_inr != null && repo.total_ai_cost_inr > 0 ? (
                            <span className="text-green-700">&#8377;{repo.total_ai_cost_inr.toFixed(2)}</span>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </div>

                        {/* Delete */}
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="icon" className="opacity-0 group-hover:opacity-100">
                              <Trash2 className="w-4 h-4 text-destructive" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete Repository?</AlertDialogTitle>
                              <AlertDialogDescription>
                                This will permanently delete &quot;{repo.name}&quot; and all its analyzed components.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDeleteRepo(repo.id)}>Delete</AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </div>

                    {/* Expanded: File Components */}
                    <CollapsibleContent>
                      <div className="ml-8 mr-2 border-l-2 border-muted pl-4 py-2 space-y-2">
                        {isLoadingComponents ? (
                          <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Loading files...
                          </div>
                        ) : components.length === 0 ? (
                          <div className="py-3 text-sm text-muted-foreground">
                            No analyzed files yet
                          </div>
                        ) : (() => {
                          const completedCount = components.filter((c) => c.analysis_status === "completed").length;
                          const failedCount = components.filter((c) => c.analysis_status === "failed").length;
                          const processingCount = components.filter((c) => c.analysis_status === "processing").length;
                          const pendingCount = components.filter((c) => c.analysis_status === "pending").length;
                          const totalCost = components.reduce((sum, c) => sum + (c.ai_cost_inr || 0), 0);

                          return (
                            <>
                              {/* Summary stats bar */}
                              <div className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-1.5 text-xs">
                                <div className="flex items-center gap-3">
                                  <span className="font-medium text-foreground">
                                    {components.length} analyzed
                                    {repoStats[repo.id]?.skipped_files_count > 0 && (
                                      <span className="text-muted-foreground font-normal"> · {repoStats[repo.id].skipped_files_count} skipped · {repoStats[repo.id].total_repo_files} total</span>
                                    )}
                                  </span>
                                  {completedCount > 0 && (
                                    <span className="text-green-600">{completedCount} completed</span>
                                  )}
                                  {processingCount > 0 && (
                                    <span className="text-blue-600">{processingCount} analyzing</span>
                                  )}
                                  {failedCount > 0 && (
                                    <span className="text-red-600">{failedCount} failed</span>
                                  )}
                                  {pendingCount > 0 && (
                                    <span className="text-gray-500">{pendingCount} pending</span>
                                  )}
                                  {totalCost > 0 && (
                                    <span className="font-mono text-green-700">Total: &#8377;{totalCost.toFixed(2)}</span>
                                  )}
                                </div>
                                <div className="flex items-center gap-2">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    className="h-6 px-2 text-xs border-blue-200 text-blue-600 hover:bg-blue-50"
                                    onClick={(e) => { e.stopPropagation(); openReanalyzeDialog(repo.id); }}
                                  >
                                    <Filter className="w-3 h-3 mr-1" />
                                    Re-Analyze
                                  </Button>
                                  {failedCount > 0 && (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="h-6 px-2 text-xs border-red-200 text-red-600 hover:bg-red-50"
                                      disabled={retryingAllRepo === repo.id}
                                      onClick={(e) => handleRetryAllFailed(repo.id, e)}
                                    >
                                      {retryingAllRepo === repo.id ? (
                                        <Loader2 className="w-3 h-3 animate-spin mr-1" />
                                      ) : (
                                        <RefreshCw className="w-3 h-3 mr-1" />
                                      )}
                                      Retry All Failed ({failedCount})
                                    </Button>
                                  )}
                                </div>
                              </div>

                              {/* Detailed Stats Panel (from backend) */}
                              {repoStats[repo.id] && (() => {
                                const stats = repoStats[repo.id];
                                return (
                                  <div className="rounded-md border bg-slate-50/50 dark:bg-slate-950/50 p-3 space-y-2">
                                    <div className="flex items-center gap-4 flex-wrap text-xs">
                                      {stats.services_count > 0 && (
                                        <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-800 rounded-full px-2 py-0.5 font-medium">
                                          Services: {stats.services_count}
                                        </span>
                                      )}
                                      {stats.endpoints_count > 0 && (
                                        <span className="inline-flex items-center gap-1 bg-green-100 text-green-800 rounded-full px-2 py-0.5 font-medium">
                                          Endpoints: {stats.endpoints_count}
                                        </span>
                                      )}
                                      {stats.models_count > 0 && (
                                        <span className="inline-flex items-center gap-1 bg-purple-100 text-purple-800 rounded-full px-2 py-0.5 font-medium">
                                          Models: {stats.models_count}
                                        </span>
                                      )}
                                    </div>
                                    {stats.extension_breakdown?.length > 0 && (
                                      <div className="flex items-center gap-2 flex-wrap text-[11px] text-muted-foreground">
                                        <span className="font-medium text-foreground">Files:</span>
                                        {stats.extension_breakdown.slice(0, 8).map((ext: any) => (
                                          <span key={ext.ext} className="bg-muted rounded px-1.5 py-0.5 font-mono">
                                            {ext.ext}: {ext.count}
                                          </span>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                );
                              })()}

                              {/* Hierarchical folder tree view */}
                              <div className="border rounded-md overflow-hidden">
                                {/* Header row */}
                                <div
                                  className="grid bg-muted/50 border-b text-xs font-medium text-muted-foreground py-2"
                                  style={{ gridTemplateColumns: "44px 1fr 80px 120px 70px 80px 80px" }}
                                >
                                  <div className="text-center">#</div>
                                  <div className="pl-3">File</div>
                                  <div className="px-2">Version</div>
                                  <div className="px-2">Status</div>
                                  <div className="text-right px-2">Duration</div>
                                  <div className="text-right px-2">Cost</div>
                                  <div className="text-right px-2">Actions</div>
                                </div>
                                {/* Tree rows */}
                                {(() => {
                                  const tree = buildFileTree(components);
                                  const repoExpanded = expandedFolders[repo.id] ?? new Set<string>();
                                  const fileIndexRef = { value: 0 };
                                  return (
                                    <FileTreeRows
                                      nodes={tree.children}
                                      depth={0}
                                      expandedFolders={repoExpanded}
                                      onToggleFolder={(path) => toggleFolder(repo.id, path)}
                                      fileIndexRef={fileIndexRef}
                                      onFileClick={(id) => router.push(`/dashboard/code/${id}`)}
                                      retryingIds={retryingIds}
                                      onRetry={handleRetryComponent}
                                      getStatusBadge={getStatusBadge}
                                      getStatusIcon={getStatusIcon}
                                    />
                                  );
                                })()}
                              </div>

                              {/* Evaluation Not Required section */}
                              {repoStats[repo.id]?.skipped_files_count > 0 && (
                                <div className="border rounded-md overflow-hidden">
                                  <div
                                    className="flex items-center gap-2 px-3 py-2 bg-slate-50/70 dark:bg-slate-900/50 cursor-pointer hover:bg-muted/50 select-none"
                                    onClick={() => toggleSkippedSection(repo.id)}
                                  >
                                    {expandedSkipped.has(repo.id)
                                      ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
                                      : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />}
                                    <EyeOff className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                                    <span className="text-sm font-medium text-muted-foreground">Evaluation Not Required</span>
                                    <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
                                      {repoStats[repo.id].skipped_category_breakdown?.slice(0, 4).map((cat: any) => (
                                        <span key={cat.category} className="bg-muted rounded px-1.5 py-0.5">
                                          {cat.category}: {cat.count}
                                        </span>
                                      ))}
                                      <span className="font-medium">{repoStats[repo.id].skipped_files_count} files</span>
                                    </div>
                                  </div>

                                  {expandedSkipped.has(repo.id) && (
                                    <div>
                                      {repoStats[repo.id].skipped_category_breakdown?.map((cat: any) => {
                                        const categoryFiles = (repoStats[repo.id].skipped_files || []).filter((f: any) => f.category === cat.category);
                                        const isCatExpanded = expandedSkippedCategories[repo.id]?.has(cat.category);
                                        return (
                                          <div key={cat.category}>
                                            <div
                                              className="flex items-center gap-2 px-3 py-1.5 hover:bg-muted/30 cursor-pointer border-t border-muted/30 select-none"
                                              style={{ paddingLeft: "28px" }}
                                              onClick={() => toggleSkippedCategory(repo.id, cat.category)}
                                            >
                                              {isCatExpanded
                                                ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                                                : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />}
                                              <Folder className="w-4 h-4 text-slate-400 flex-shrink-0" />
                                              <span className="text-sm flex-1">{cat.category}</span>
                                              <span className="text-xs text-muted-foreground">{cat.count} files</span>
                                            </div>
                                            {isCatExpanded && categoryFiles.map((sf: any) => {
                                              const fileName = sf.path.split('/').pop();
                                              return (
                                                <div
                                                  key={sf.path}
                                                  className="flex items-center gap-2 py-1 text-xs text-muted-foreground border-t border-muted/20"
                                                  style={{ paddingLeft: "56px" }}
                                                  title={sf.path}
                                                >
                                                  <File className="w-3.5 h-3.5 flex-shrink-0 text-slate-300" />
                                                  <span className="truncate flex-1 font-mono">{fileName}</span>
                                                  <span className="text-slate-400 flex-shrink-0 font-mono mr-3">{sf.ext}</span>
                                                </div>
                                              );
                                            })}
                                          </div>
                                        );
                                      })}
                                    </div>
                                  )}
                                </div>
                              )}
                            </>
                          );
                        })()}
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Standalone Components (no repository) */}
      {/* Re-Analyze Dialog — Excel-style file selection */}
      {reanalyzeRepoId !== null && (() => {
        const comps = repoComponents[reanalyzeRepoId] || [];
        const filtered = comps.filter(
          (c) => !reanalyzeSearch || c.name.toLowerCase().includes(reanalyzeSearch.toLowerCase())
        );
        const allFilteredSelected = filtered.length > 0 && filtered.every((c) => reanalyzeSelected.has(c.id));
        return (
          <Dialog open={true} onOpenChange={(open) => { if (!open) setReanalyzeRepoId(null); }}>
            <DialogContent className="sm:max-w-lg max-h-[80vh] flex flex-col">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Filter className="w-4 h-4" />
                  Select Files to Re-Analyze
                </DialogTitle>
              </DialogHeader>
              <div className="flex items-center gap-2 px-1">
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
                  <Input
                    placeholder="Search files..."
                    value={reanalyzeSearch}
                    onChange={(e) => setReanalyzeSearch(e.target.value)}
                    className="pl-8 h-8 text-sm"
                  />
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs whitespace-nowrap"
                  onClick={() => {
                    if (allFilteredSelected) {
                      // Deselect all filtered
                      setReanalyzeSelected((prev) => {
                        const next = new Set(prev);
                        filtered.forEach((c) => next.delete(c.id));
                        return next;
                      });
                    } else {
                      // Select all filtered
                      setReanalyzeSelected((prev) => {
                        const next = new Set(prev);
                        filtered.forEach((c) => next.add(c.id));
                        return next;
                      });
                    }
                  }}
                >
                  {allFilteredSelected ? "Deselect All" : "Select All"}
                </Button>
              </div>
              <div className="text-xs text-muted-foreground px-1">
                {reanalyzeSelected.size} of {comps.length} files selected
              </div>
              <div className="flex-1 overflow-y-auto border rounded-md max-h-[50vh]">
                {filtered.length === 0 ? (
                  <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                    No files match your search
                  </div>
                ) : (
                  <div className="divide-y">
                    {filtered.map((comp) => {
                      const isChecked = reanalyzeSelected.has(comp.id);
                      return (
                        <label
                          key={comp.id}
                          className={`flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-muted/50 transition-colors ${
                            isChecked ? "bg-blue-50/50 dark:bg-blue-950/20" : ""
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {
                              setReanalyzeSelected((prev) => {
                                const next = new Set(prev);
                                if (next.has(comp.id)) next.delete(comp.id);
                                else next.add(comp.id);
                                return next;
                              });
                            }}
                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 h-4 w-4"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm truncate">{comp.name}</div>
                            <div className="text-[10px] text-muted-foreground truncate">
                              {comp.location}
                            </div>
                          </div>
                          <div className="flex-shrink-0">
                            {getStatusBadge(comp.analysis_status)}
                          </div>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" size="sm" onClick={() => setReanalyzeRepoId(null)}>
                  Cancel
                </Button>
                <Button
                  size="sm"
                  className="bg-blue-600 hover:bg-blue-700"
                  disabled={reanalyzeSelected.size === 0 || reanalyzeSubmitting}
                  onClick={handleReanalyze}
                >
                  {reanalyzeSubmitting ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  ) : (
                    <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                  )}
                  Re-Analyze {reanalyzeSelected.size} Files
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        );
      })()}

      {filteredStandalone.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Standalone Components ({filteredStandalone.length})</CardTitle>
            <CardDescription>
              Components not linked to any repository
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredStandalone.map((comp) => (
                  <TableRow key={comp.id} className="group">
                    <TableCell
                      onClick={() => router.push(`/dashboard/code/${comp.id}`)}
                      className="font-medium cursor-pointer"
                    >
                      {comp.name}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <FileCode className="w-4 h-4 text-muted-foreground" />
                        <span>{comp.component_type}</span>
                      </div>
                    </TableCell>
                    <TableCell className="max-w-xs truncate" title={comp.location}>
                      {comp.location}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        {getStatusIcon(comp.analysis_status)}
                        {getStatusBadge(comp.analysis_status)}
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {comp.ai_cost_inr != null && comp.ai_cost_inr > 0 ? (
                        <span className="text-green-700">&#8377;{comp.ai_cost_inr.toFixed(2)}</span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="ghost" size="icon" className="opacity-0 group-hover:opacity-100">
                            <Trash2 className="w-4 h-4 text-destructive" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This will permanently delete &quot;{comp.name}&quot; and its analysis data.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction onClick={() => handleDeleteComponent(comp.id)}>
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
