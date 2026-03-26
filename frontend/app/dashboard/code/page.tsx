"use client";

import React, { useState, useEffect, useRef, useCallback, Suspense } from "react";
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
  Activity,
  BarChart2,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { API_BASE_URL } from "@/lib/api";

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
  onDelete: (id: number, e: React.MouseEvent) => void;
  getStatusBadge: (status: string) => React.ReactElement;
  getStatusIcon: (status: string) => React.ReactElement;
}

function FileTreeRows({
  nodes, depth, expandedFolders, onToggleFolder,
  fileIndexRef, onFileClick, retryingIds, onRetry, onDelete,
  getStatusBadge, getStatusIcon,
}: FileTreeRowsProps): React.ReactElement {
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
                  onDelete={onDelete}
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
              className={`group grid items-center border-b border-muted/20 text-sm hover:bg-muted/30 cursor-pointer ${
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
              <div className="flex items-center justify-end gap-1 px-2 py-2">
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
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 text-red-400 hover:text-red-600 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => { e.stopPropagation(); onDelete(comp.id, e); }}
                  title="Delete file"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          );
        }
      })}
    </>
  );
}

function CodePageInner() {
  // --- State: Repositories (primary view) ---
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [standaloneComponents, setStandaloneComponents] = useState<CodeComponent[]>([]);
  const [expandedRepos, setExpandedRepos] = useState<Set<number>>(new Set());
  const [repoComponents, setRepoComponents] = useState<Record<number, CodeComponent[]>>({});
  const [loadingRepoComponents, setLoadingRepoComponents] = useState<Set<number>>(new Set());
  const [repoStats, setRepoStats] = useState<Record<number, any>>({});
  const [repoActiveTab, setRepoActiveTab] = useState<Record<number, string>>({});
  // Legacy folder-tree state kept for backward compat (no longer used in render)
  const [expandedFolders, setExpandedFolders] = useState<Record<number, Set<string>>>({});
  const [expandedSkipped, setExpandedSkipped] = useState<Set<number>>(new Set());
  const [expandedSkippedCategories, setExpandedSkippedCategories] = useState<Record<number, Set<string>>>({});
  // Scan preview state for Add Component dialog
  const [scanPreview, setScanPreview] = useState<{
    analyze_count: number; skipped_count: number; total: number;
    by_language: Record<string, number>; skipped_by_category: Record<string, number>;
  } | null>(null);
  const [isScanning, setIsScanning] = useState(false);

  // GitHub integration state for repo picker in Add Component dialog
  const [githubRepos, setGithubRepos] = useState<Array<{
    id: number; full_name: string; name: string; private: boolean;
    description: string; default_branch: string; html_url: string;
    language: string; owner_login: string; owner_type: string;
  }>>([]);
  const [githubConnected, setGithubConnected] = useState(false);
  const [githubLogin, setGithubLogin] = useState<string | null>(null);
  const [loadingGithubRepos, setLoadingGithubRepos] = useState(false);
  const [githubRepoSearch, setGithubRepoSearch] = useState("");
  const [githubReposError, setGithubReposError] = useState<string | null>(null);
  const [githubSelectedRepo, setGithubSelectedRepo] = useState<typeof githubRepos[0] | null>(null);
  const [githubFilePath, setGithubFilePath] = useState("");
  const [githubFileTree, setGithubFileTree] = useState<string[]>([]);
  const [githubFileTreeLoading, setGithubFileTreeLoading] = useState(false);
  const [githubFileTreeSearch, setGithubFileTreeSearch] = useState("");
  const [githubTreeMode, setGithubTreeMode] = useState<"search" | "tree">("search");
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [addMode, setAddMode] = useState<"url" | "github">("url");

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

  // Delete confirmation for files inside the repo tree
  const [deletingComponentId, setDeletingComponentId] = useState<number | null>(null);

  // Post-analysis push flow: after a standalone file completes, check if a same-named repo file exists
  const checkedForPushRef = useRef<Set<number>>(new Set());
  const [pendingPushMap, setPendingPushMap] = useState<Record<number, { matchId: number; repoName: string }[]>>({});
  const [activePushDialog, setActivePushDialog] = useState<{
    compId: number; compName: string; compLocation: string;
    matches: { matchId: number; repoName: string }[];
  } | null>(null);

  const router = useRouter();
  const searchParams = useSearchParams();
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
        fetch(`${API_BASE_URL}/repositories/`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`${API_BASE_URL}/code-components/?standalone=true`, {
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

  const fetchGithubRepos = useCallback(async () => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    setLoadingGithubRepos(true);
    setGithubReposError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/integrations/github/repos`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setGithubRepos(data.repos || []);
        setGithubLogin(data.github_login || null);
        setGithubConnected(true);
      } else if (res.status === 404) {
        setGithubConnected(false);
        setGithubReposError(null);
      } else {
        // 401, 502, etc. — GitHub is connected but API call failed
        let detail = `Error ${res.status}`;
        try {
          const err = await res.json();
          detail = err.detail || detail;
        } catch {}
        setGithubConnected(false);
        setGithubReposError(detail);
      }
    } catch (e: any) {
      setGithubConnected(false);
      setGithubReposError(e?.message || "Network error — could not reach server");
    } finally {
      setLoadingGithubRepos(false);
    }
  }, []);

  // Auto-open GitHub repo picker when navigated from integrations page (?add=github)
  useEffect(() => {
    if (searchParams.get("add") === "github") {
      setGithubConnected(false);
      setGithubReposError(null);
      setGithubSelectedRepo(null);
      setGithubFilePath("");
      setIsDialogOpen(true);
      setAddMode("github");
      fetchGithubRepos();
      window.history.replaceState({}, "", "/dashboard/code");
    }
  }, [searchParams, fetchGithubRepos]);

  const fetchGithubFileTree = useCallback(async (repoUrl: string, branch: string) => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    setGithubFileTreeLoading(true);
    setGithubFileTree([]);
    setGithubFileTreeSearch("");
    setExpandedFolders(new Set());
    try {
      const params = new URLSearchParams({ repo_url: repoUrl, branch });
      const res = await fetch(`${API_BASE_URL}/integrations/github/tree?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setGithubFileTree(data.files || []);
      }
    } catch {
      // silently fail — user can still type path manually
    } finally {
      setGithubFileTreeLoading(false);
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
        `${API_BASE_URL}/repositories/${repoId}/components?limit=500`,
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
      const res = await fetch(`${API_BASE_URL}/repositories/${repoId}/stats`, {
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

  // Post-analysis push detection: when a standalone file finishes analysis, check for same-named repo files
  useEffect(() => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    for (const comp of standaloneComponents) {
      if (comp.analysis_status === "completed" && !checkedForPushRef.current.has(comp.id)) {
        checkedForPushRef.current.add(comp.id);
        const basename = comp.name.trim().split("/").pop() || comp.name;
        fetch(
          `${API_BASE_URL}/code-components/check-name?name=${encodeURIComponent(basename)}`,
          { headers: { Authorization: `Bearer ${token}` } }
        )
          .then((r) => r.json())
          .then((matches: { id: number; name: string; location: string; repository_id: number; repo_name: string }[]) => {
            if (matches.length > 0) {
              setActivePushDialog({
                compId: comp.id,
                compName: comp.name,
                compLocation: comp.location,
                matches: matches.map((m) => ({ matchId: m.id, repoName: m.repo_name })),
              });
            }
          })
          .catch(() => {/* ignore */});
      }
    }
  }, [standaloneComponents]);

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
    if (name === "location") setScanPreview(null);
    // When component type changes, reset GitHub file selection state
    if (name === "component_type") {
      setGithubSelectedRepo(null);
      setGithubFilePath("");
      setNewComponent((prev) => ({ ...prev, component_type: value, location: "", version: "" }));
      setScanPreview(null);
    }
  };

  const handleScanPreview = async () => {
    const token = localStorage.getItem("accessToken");
    if (!token || !newComponent.location) return;
    setIsScanning(true);
    setScanPreview(null);
    try {
      const res = await fetch(`${API_BASE_URL}/repositories/scan-preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ url: newComponent.location }),
      });
      if (res.ok) {
        const data = await res.json();
        setScanPreview(data.summary);
      }
    } catch (e) {
      console.error("Scan preview failed:", e);
    } finally {
      setIsScanning(false);
    }
  };

  const registerComponent = async (locationOverride?: string) => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    const payload = locationOverride
      ? { ...newComponent, location: locationOverride }
      : newComponent;
    const res = await fetch(`${API_BASE_URL}/code-components/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
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

    const isRepo = newComponent.component_type === "Repository";

    // For File/Class/Function in GitHub mode: build location from selected repo + file path
    if (addMode === "github" && !isRepo) {
      if (githubSelectedRepo) {
        const trimmedPath = githubFilePath.trim().replace(/^\//, "");
        if (!trimmedPath) {
          setSubmissionError("Enter the file path within the repository (e.g., src/auth/utils.py)");
          setIsSubmitting(false);
          return;
        }
        // Build a direct blob URL so the backend can fetch the file
        const builtLocation = `${githubSelectedRepo.html_url}/blob/${githubSelectedRepo.default_branch}/${trimmedPath}`;
        setNewComponent((prev) => ({ ...prev, location: builtLocation }));
        // Use the built location directly in the request below
        try {
          await registerComponent(builtLocation);
        } catch (error: any) {
          setSubmissionError(error.message);
        } finally {
          setIsSubmitting(false);
        }
        return;
      } else if (!newComponent.location) {
        setSubmissionError("Select a repository from the list or paste a file URL directly.");
        setIsSubmitting(false);
        return;
      }
    }

    if (!newComponent.location) {
      setSubmissionError(
        addMode === "github"
          ? "Please select a repository from the list."
          : "Location URL is required."
      );
      setIsSubmitting(false);
      return;
    }
    try {
      await registerComponent();
    } catch (error: any) {
      setSubmissionError(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Called when user clicks Push (now or from the persistent button)
  const handlePushToRepo = async (compId: number, compLocation: string, matchId: number) => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    try {
      await fetch(`${API_BASE_URL}/code-components/${matchId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ location: compLocation }),
      });
      setSuccessMessage("Repository file updated with the uploaded version.");
      setTimeout(() => setSuccessMessage(null), 5000);
      setPendingPushMap((prev) => { const n = { ...prev }; delete n[compId]; return n; });
    } catch {
      // silently ignore; user can retry
    }
  };

  const handlePushDialogAction = async (push: boolean) => {
    if (!activePushDialog) return;
    const { compId, compLocation, matches } = activePushDialog;
    setActivePushDialog(null);
    if (push) {
      await handlePushToRepo(compId, compLocation, matches[0].matchId);
    } else {
      // Keep push button visible on the standalone row
      setPendingPushMap((prev) => ({ ...prev, [compId]: matches }));
    }
  };

  const handleDeleteRepo = async (repoId: number) => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE_URL}/repositories/${repoId}`, {
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
      const res = await fetch(`${API_BASE_URL}/code-components/${id}`, {
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
      const res = await fetch(`${API_BASE_URL}/code-components/${compId}/retry`, {
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
      const res = await fetch(`${API_BASE_URL}/repositories/${repoId}/retry-failed`, {
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
        await fetch(`${API_BASE_URL}/code-components/${comp.id}/retry`, {
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
              if (open) {
                setAddMode("url");
                setScanPreview(null);
                setGithubRepoSearch("");
                setGithubReposError(null);
                setGithubConnected(false);
                setGithubSelectedRepo(null);
                setGithubFilePath("");
                setGithubFileTree([]);
                setGithubFileTreeSearch("");
                setExpandedFolders(new Set());
                fetchGithubRepos();
              }
            }}
          >
            <DialogTrigger asChild>
              <Button onClick={() => setIsDialogOpen(true)} className="bg-blue-600 hover:bg-blue-700">
                <Plus className="w-4 h-4 mr-2" /> Add Component
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle className="flex items-center space-x-2">
                  <FileCode className="w-5 h-5" />
                  <span>Register New Component</span>
                </DialogTitle>
              </DialogHeader>

              {/* Mode toggle: URL vs GitHub picker */}
              <div className="flex rounded-lg border border-input overflow-hidden text-sm">
                <button
                  type="button"
                  onClick={() => { setAddMode("url"); setScanPreview(null); }}
                  className={`flex-1 px-3 py-2 flex items-center justify-center gap-1.5 transition-colors ${
                    addMode === "url"
                      ? "bg-blue-600 text-white font-medium"
                      : "bg-background text-muted-foreground hover:bg-muted"
                  }`}
                >
                  <Globe className="w-3.5 h-3.5" /> Any Public URL
                </button>
                <button
                  type="button"
                  onClick={() => setAddMode("github")}
                  className={`flex-1 px-3 py-2 flex items-center justify-center gap-1.5 transition-colors ${
                    addMode === "github"
                      ? "bg-gray-900 text-white font-medium"
                      : "bg-background text-muted-foreground hover:bg-muted"
                  }`}
                >
                  <FolderGit2 className="w-3.5 h-3.5" /> My GitHub Repos
                  {githubConnected && (
                    <span className="ml-1 text-[10px] bg-green-500 text-white px-1.5 py-0.5 rounded-full">Connected</span>
                  )}
                </button>
              </div>

              {/* Context hint below the toggle */}
              <p className="text-[11px] text-muted-foreground -mt-1">
                {addMode === "url"
                  ? "Paste any public GitHub or raw file URL — no login needed."
                  : "Browse repos your GitHub account has access to, including private and org repos."}
              </p>

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

                {/* ── GitHub Repo Picker ── */}
                {addMode === "github" ? (
                  <div className="space-y-3">
                    {loadingGithubRepos ? (
                      <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 p-6 text-center">
                        <Loader2 className="w-6 h-6 animate-spin text-blue-500 mx-auto mb-2" />
                        <p className="text-xs text-gray-500">Loading your GitHub repositories…</p>
                      </div>
                    ) : !githubConnected ? (
                      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 text-center space-y-2">
                        <FolderGit2 className="w-8 h-8 text-gray-400 mx-auto" />
                        {githubReposError ? (
                          <>
                            <p className="text-sm text-red-600 font-medium">Failed to load repositories</p>
                            <p className="text-xs text-gray-500">{githubReposError}</p>
                            <button
                              type="button"
                              onClick={() => fetchGithubRepos()}
                              className="text-xs text-blue-600 underline"
                            >
                              Try again
                            </button>
                          </>
                        ) : (
                          <>
                            <p className="text-sm text-gray-600 font-medium">GitHub not connected</p>
                            <p className="text-xs text-gray-400">
                              Go to{" "}
                              <a href="/dashboard/integrations" className="text-blue-600 underline">
                                Integrations
                              </a>{" "}
                              and connect your GitHub account to browse private repos.
                            </p>
                          </>
                        )}
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center gap-2">
                          <div className="relative flex-1">
                            <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
                            <input
                              type="text"
                              value={githubRepoSearch}
                              onChange={(e) => setGithubRepoSearch(e.target.value)}
                              placeholder={`Search ${githubLogin ? `@${githubLogin}` : ""} repos…`}
                              className="w-full pl-8 pr-3 py-2 text-sm border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400"
                            />
                          </div>
                        </div>

                        <div className="max-h-52 overflow-y-auto rounded-md border border-input divide-y">
                          {githubRepos
                            .filter((r) =>
                              !githubRepoSearch ||
                              r.full_name.toLowerCase().includes(githubRepoSearch.toLowerCase()) ||
                              (r.description ?? "").toLowerCase().includes(githubRepoSearch.toLowerCase())
                            )
                            .map((repo) => {
                              const isSelected = newComponent.component_type === "Repository"
                                ? newComponent.location === repo.html_url
                                : githubSelectedRepo?.id === repo.id;
                              return (
                                <button
                                  key={repo.id}
                                  type="button"
                                  onClick={() => {
                                    if (newComponent.component_type === "Repository") {
                                      // Repository type: select whole repo
                                      setNewComponent((prev) => ({
                                        ...prev,
                                        location: repo.html_url,
                                        name: prev.name || repo.name,
                                        version: repo.default_branch,
                                      }));
                                      setScanPreview(null);
                                      setGithubSelectedRepo(null);
                                    } else {
                                      // File/Class/Function: select repo as source, load file tree
                                      setGithubSelectedRepo(repo);
                                      setGithubFilePath("");
                                      setGithubTreeMode("search");
                                      setNewComponent((prev) => ({
                                        ...prev,
                                        name: prev.name || repo.name,
                                        version: repo.default_branch,
                                        location: "",
                                      }));
                                      fetchGithubFileTree(repo.html_url, repo.default_branch);
                                    }
                                  }}
                                  className={`w-full text-left px-3 py-2.5 hover:bg-muted transition-colors ${
                                    isSelected ? "bg-blue-50 border-l-2 border-blue-600" : ""
                                  }`}
                                >
                                  <div className="flex items-center gap-2">
                                    <FolderGit2 className={`w-3.5 h-3.5 shrink-0 ${isSelected ? "text-blue-600" : "text-gray-400"}`} />
                                    <span className="text-sm font-medium truncate">{repo.full_name}</span>
                                    {repo.private && (
                                      <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded border shrink-0">
                                        Private
                                      </span>
                                    )}
                                    {repo.language && (
                                      <span className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded shrink-0">
                                        {repo.language}
                                      </span>
                                    )}
                                  </div>
                                  {repo.description && (
                                    <p className="text-[11px] text-muted-foreground mt-0.5 pl-5 truncate">
                                      {repo.description}
                                    </p>
                                  )}
                                </button>
                              );
                            })}
                          {githubRepos.filter((r) =>
                            !githubRepoSearch ||
                            r.full_name.toLowerCase().includes(githubRepoSearch.toLowerCase())
                          ).length === 0 && !loadingGithubRepos && (
                            <p className="text-sm text-muted-foreground text-center py-4">
                              No repos found matching &quot;{githubRepoSearch}&quot;
                            </p>
                          )}
                        </div>

                        {/* Repository type: selected repo + scan preview */}
                        {newComponent.component_type === "Repository" && newComponent.location && newComponent.location.includes("github.com") && (
                          <div className="space-y-2">
                            <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted rounded px-3 py-1.5">
                              <GitBranch className="w-3 h-3" />
                              <span className="font-mono truncate">{newComponent.location}</span>
                            </div>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              className="w-full h-8 text-xs gap-1.5"
                              onClick={handleScanPreview}
                              disabled={isScanning}
                            >
                              {isScanning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                              Scan repo to preview files
                            </Button>
                            {scanPreview && (
                              <div className="rounded-lg border bg-slate-50 p-3 space-y-2">
                                <div className="flex items-center gap-3 text-sm">
                                  <span className="font-medium">{scanPreview.total} total files</span>
                                  <span className="text-green-700 font-medium">✓ {scanPreview.analyze_count} to analyze</span>
                                  <span className="text-slate-400">⊘ {scanPreview.skipped_count} skipped</span>
                                </div>
                                {Object.keys(scanPreview.by_language).length > 0 && (
                                  <div className="flex flex-wrap gap-1.5">
                                    {Object.entries(scanPreview.by_language).sort((a,b) => b[1]-a[1]).slice(0, 8).map(([lang, cnt]) => (
                                      <span key={lang} className="text-[11px] bg-blue-100 text-blue-700 rounded px-1.5 py-0.5 font-mono">{lang}: {cnt}</span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}

                        {/* File/Class/Function: full file browser after repo selection */}
                        {newComponent.component_type !== "Repository" && githubSelectedRepo && (
                          <div className="space-y-2 pt-1">
                            {/* Selected repo badge */}
                            <div className="flex items-center justify-between bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                              <div className="flex items-center gap-2 min-w-0">
                                <FolderGit2 className="w-3.5 h-3.5 text-green-600 shrink-0" />
                                <span className="text-xs font-medium text-green-800 truncate">{githubSelectedRepo.full_name}</span>
                                {githubSelectedRepo.language && (
                                  <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded shrink-0">{githubSelectedRepo.language}</span>
                                )}
                                <span className="text-[10px] text-green-600">/{githubSelectedRepo.default_branch}</span>
                              </div>
                              <button
                                type="button"
                                onClick={() => {
                                  setGithubSelectedRepo(null);
                                  setGithubFilePath("");
                                  setGithubFileTree([]);
                                  setGithubFileTreeSearch("");
                                }}
                                className="text-[10px] text-gray-400 hover:text-gray-600 underline ml-2 shrink-0"
                              >
                                Change repo
                              </button>
                            </div>

                            {/* File browser */}
                            {githubFileTreeLoading ? (
                              <div className="flex items-center gap-2 text-xs text-gray-500 py-3 justify-center">
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                Loading file tree…
                              </div>
                            ) : (
                              <div className="rounded-md border border-input overflow-hidden">
                                {/* Mode toggle + search */}
                                <div className="flex items-center border-b bg-gray-50">
                                  <div className="relative flex-1">
                                    <Search className="absolute left-2.5 top-2.5 w-3 h-3 text-muted-foreground" />
                                    <input
                                      type="text"
                                      value={githubFileTreeSearch}
                                      onChange={(e) => {
                                        setGithubFileTreeSearch(e.target.value);
                                        setGithubTreeMode("search");
                                      }}
                                      placeholder="Search files…"
                                      className="w-full pl-7 pr-2 py-2 text-xs bg-transparent focus:outline-none"
                                    />
                                  </div>
                                  <div className="flex border-l text-[10px]">
                                    <button
                                      type="button"
                                      onClick={() => setGithubTreeMode("search")}
                                      className={`px-2 py-2 ${githubTreeMode === "search" ? "bg-white font-medium text-blue-600" : "text-gray-400 hover:text-gray-600"}`}
                                    >
                                      List
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => setGithubTreeMode("tree")}
                                      className={`px-2 py-2 border-l ${githubTreeMode === "tree" ? "bg-white font-medium text-blue-600" : "text-gray-400 hover:text-gray-600"}`}
                                    >
                                      Tree
                                    </button>
                                  </div>
                                </div>

                                {/* File list */}
                                <div className="max-h-48 overflow-y-auto">
                                  {githubTreeMode === "search" ? (
                                    // Flat search/filter list
                                    (() => {
                                      const q = githubFileTreeSearch.toLowerCase();
                                      const filtered = githubFileTree
                                        .filter((p) => !q || p.toLowerCase().includes(q))
                                        .slice(0, 60);
                                      return filtered.length === 0 ? (
                                        <p className="text-xs text-muted-foreground text-center py-4">
                                          {q ? `No files matching "${githubFileTreeSearch}"` : "No files found"}
                                        </p>
                                      ) : (
                                        <>
                                          {filtered.map((filePath) => {
                                            const isSelected = githubFilePath === filePath;
                                            const parts = filePath.split("/");
                                            const fileName = parts[parts.length - 1];
                                            const dir = parts.slice(0, -1).join("/");
                                            return (
                                              <button
                                                key={filePath}
                                                type="button"
                                                onClick={() => setGithubFilePath(filePath)}
                                                className={`w-full text-left px-3 py-1.5 flex items-center gap-2 hover:bg-muted transition-colors text-xs ${isSelected ? "bg-blue-50 border-l-2 border-blue-600" : ""}`}
                                              >
                                                <File className={`w-3 h-3 shrink-0 ${isSelected ? "text-blue-600" : "text-gray-400"}`} />
                                                <span className={`font-medium truncate ${isSelected ? "text-blue-700" : ""}`}>{fileName}</span>
                                                {dir && <span className="text-[10px] text-muted-foreground truncate">{dir}/</span>}
                                              </button>
                                            );
                                          })}
                                          {githubFileTree.filter((p) => !q || p.toLowerCase().includes(q)).length > 60 && (
                                            <p className="text-[10px] text-center text-muted-foreground py-1.5 border-t">
                                              Showing 60 of {githubFileTree.filter((p) => !q || p.toLowerCase().includes(q)).length} — search to narrow down
                                            </p>
                                          )}
                                        </>
                                      );
                                    })()
                                  ) : (
                                    // Tree view — folder hierarchy
                                    (() => {
                                      // Build tree structure
                                      const allFolders = new Set<string>();
                                      githubFileTree.forEach((p) => {
                                        const parts = p.split("/");
                                        for (let i = 1; i < parts.length; i++) {
                                          allFolders.add(parts.slice(0, i).join("/"));
                                        }
                                      });

                                      const rootItems: { path: string; isDir: boolean; depth: number }[] = [];
                                      const seen = new Set<string>();

                                      // Add root-level folders and files
                                      const addChildren = (prefix: string, depth: number) => {
                                        const children = new Set<string>();
                                        githubFileTree.forEach((p) => {
                                          if (prefix ? p.startsWith(prefix + "/") : true) {
                                            const rel = prefix ? p.slice(prefix.length + 1) : p;
                                            const firstPart = rel.split("/")[0];
                                            const fullPath = prefix ? `${prefix}/${firstPart}` : firstPart;
                                            if (!seen.has(fullPath)) {
                                              children.add(fullPath);
                                              seen.add(fullPath);
                                            }
                                          }
                                        });
                                        [...children].sort().forEach((childPath) => {
                                          const isDir = allFolders.has(childPath);
                                          rootItems.push({ path: childPath, isDir, depth });
                                          if (isDir && expandedFolders.has(childPath)) {
                                            addChildren(childPath, depth + 1);
                                          }
                                        });
                                      };
                                      addChildren("", 0);

                                      return rootItems.length === 0 ? (
                                        <p className="text-xs text-muted-foreground text-center py-4">No files</p>
                                      ) : (
                                        rootItems.map(({ path, isDir, depth }) => {
                                          const name = path.split("/").pop()!;
                                          const isSelected = !isDir && githubFilePath === path;
                                          const isExpanded = expandedFolders.has(path);
                                          return (
                                            <button
                                              key={path}
                                              type="button"
                                              onClick={() => {
                                                if (isDir) {
                                                  setExpandedFolders((prev) => {
                                                    const next = new Set(prev);
                                                    next.has(path) ? next.delete(path) : next.add(path);
                                                    return next;
                                                  });
                                                } else {
                                                  setGithubFilePath(path);
                                                }
                                              }}
                                              className={`w-full text-left flex items-center gap-1.5 py-1 pr-2 text-xs hover:bg-muted transition-colors ${isSelected ? "bg-blue-50 border-l-2 border-blue-600" : ""}`}
                                              style={{ paddingLeft: `${8 + depth * 14}px` }}
                                            >
                                              {isDir ? (
                                                <>
                                                  <ChevronRight className={`w-3 h-3 text-gray-400 shrink-0 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                                                  <Folder className="w-3 h-3 text-yellow-500 shrink-0" />
                                                </>
                                              ) : (
                                                <>
                                                  <span className="w-3 shrink-0" />
                                                  <File className={`w-3 h-3 shrink-0 ${isSelected ? "text-blue-600" : "text-gray-400"}`} />
                                                </>
                                              )}
                                              <span className={`truncate ${isSelected ? "text-blue-700 font-medium" : ""}`}>{name}</span>
                                            </button>
                                          );
                                        })
                                      );
                                    })()
                                  )}
                                </div>
                              </div>
                            )}

                            {/* Selected file preview + manual override */}
                            <div className="space-y-1">
                              <div className="flex items-center justify-between">
                                <label className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
                                  {githubFilePath ? "Selected file" : "Or type path manually"}
                                </label>
                                {githubFilePath && (
                                  <button type="button" onClick={() => setGithubFilePath("")} className="text-[10px] text-gray-400 hover:text-red-500">Clear</button>
                                )}
                              </div>
                              <div className="relative">
                                <File className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
                                <input
                                  type="text"
                                  value={githubFilePath}
                                  onChange={(e) => setGithubFilePath(e.target.value)}
                                  placeholder="src/auth/utils.py"
                                  className={`w-full pl-8 pr-3 py-2 text-xs border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400 font-mono ${githubFilePath ? "border-blue-300 bg-blue-50" : "border-input"}`}
                                />
                              </div>
                              {githubFilePath.trim() && (
                                <p className="text-[10px] text-muted-foreground font-mono truncate pl-1">
                                  {githubSelectedRepo.html_url}/blob/{githubSelectedRepo.default_branch}/{githubFilePath.trim().replace(/^\//, "")}
                                </p>
                              )}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ) : (
                  /* ── URL mode (original flow) ── */
                  <div>
                    <Label htmlFor="location" className="text-sm font-medium">Location URL</Label>
                    <div className="relative mt-1 flex gap-2">
                      <div className="relative flex-1">
                        <Globe className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                        <Input id="location" name="location" value={newComponent.location}
                          onChange={handleInputChange}
                          placeholder={
                            newComponent.component_type === "Repository"
                              ? "https://github.com/owner/repo"
                              : "https://github.com/owner/repo/blob/main/src/file.py"
                          }
                          className="pl-10" required />
                      </div>
                      {newComponent.location && newComponent.location.includes("github.com") && !newComponent.location.includes("/blob/") && (
                        <Button type="button" variant="outline" size="sm" className="shrink-0 h-10 px-3"
                          onClick={handleScanPreview} disabled={isScanning}>
                          {isScanning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                          <span className="ml-1.5 text-xs">Scan</span>
                        </Button>
                      )}
                    </div>
                    {/* Scan preview result */}
                    {scanPreview && (
                      <div className="mt-2 rounded-lg border bg-slate-50 dark:bg-slate-900 p-3 space-y-2">
                        <div className="flex items-center gap-3 text-sm">
                          <span className="font-medium text-foreground">{scanPreview.total} total files</span>
                          <span className="text-green-700 font-medium">✓ {scanPreview.analyze_count} will be analyzed</span>
                          <span className="text-slate-400">⊘ {scanPreview.skipped_count} skipped</span>
                        </div>
                        {Object.keys(scanPreview.by_language).length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {Object.entries(scanPreview.by_language).sort((a,b) => b[1]-a[1]).slice(0, 8).map(([lang, cnt]) => (
                              <span key={lang} className="text-[11px] bg-blue-100 text-blue-700 rounded px-1.5 py-0.5 font-mono">{lang}: {cnt}</span>
                            ))}
                          </div>
                        )}
                        {Object.keys(scanPreview.skipped_by_category).length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            <span className="text-[11px] text-slate-400 self-center">Skipped:</span>
                            {Object.entries(scanPreview.skipped_by_category).sort((a,b) => b[1]-a[1]).map(([cat, cnt]) => (
                              <span key={cat} className="text-[11px] bg-slate-100 text-slate-500 rounded px-1.5 py-0.5">{cat}: {cnt}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

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

      {/* Post-analysis push dialog: shown when a standalone file's name matches a repo file */}
      <AlertDialog open={!!activePushDialog} onOpenChange={(open) => { if (!open) handlePushDialogAction(false); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>File match found in repository</AlertDialogTitle>
            <AlertDialogDescription>
              Analysis of <strong>&quot;{activePushDialog?.compName}&quot;</strong> is complete.
              A file with the same name exists in{" "}
              {activePushDialog?.matches.map((m, i) => (
                <span key={m.matchId}>
                  {i > 0 && ", "}
                  <span className="font-medium text-gray-700">{m.repoName}</span>
                </span>
              ))}.
              <br /><br />
              Do you want to push your uploaded version to the repository? If you click Cancel, a{" "}
              <strong>Push</strong> button will appear on the file row so you can do it later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => handlePushDialogAction(false)}>
              Cancel — remind me later
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => handlePushDialogAction(true)}
              className="bg-blue-600 hover:bg-blue-700"
            >
              Push to repository
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete confirmation dialog for tree file rows */}
      <AlertDialog open={deletingComponentId !== null} onOpenChange={(open) => { if (!open) setDeletingComponentId(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this file?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove the file and its analysis data. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={() => {
                if (deletingComponentId !== null) {
                  handleDeleteComponent(deletingComponentId);
                  setDeletingComponentId(null);
                }
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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

      {/* ── Currently Analyzing Banner ── */}
      {(() => {
        const repoProcessing = Object.entries(repoComponents).flatMap(([repoId, comps]) =>
          comps
            .filter((c) => c.analysis_status === "processing")
            .map((c) => ({ ...c, context: repositories.find((r) => r.id === Number(repoId))?.name ?? `Repo #${repoId}` }))
        );
        const standaloneProcessing = standaloneComponents
          .filter(c => c.analysis_status === "processing")
          .map(c => ({ ...c, context: "Standalone" }));
        const processing = [...repoProcessing, ...standaloneProcessing];
        if (processing.length === 0) return null;
        return (
          <div className="rounded-lg border-2 border-blue-400 bg-blue-50 dark:bg-blue-950 p-3 space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-blue-700 dark:text-blue-300">
              <Activity className="w-4 h-4 animate-pulse" />
              Analyzing {processing.length} file{processing.length > 1 ? "s" : ""}
              <div className="ml-auto flex items-center gap-2">
                <div className="w-24 h-1.5 bg-blue-200 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 animate-pulse rounded-full" style={{ width: "100%" }} />
                </div>
                <span className="text-xs font-normal text-blue-400">AI processing · 3 files/batch</span>
              </div>
            </div>
            <div className="grid gap-1 sm:grid-cols-2">
              {processing.map((comp) => {
                const fileName = comp.name || comp.location?.split("/").pop() || "unknown";
                const elapsed = comp.analysis_started_at
                  ? Math.round((Date.now() - new Date(comp.analysis_started_at).getTime()) / 1000)
                  : null;
                return (
                  <div key={comp.id} className="flex items-center gap-2 rounded-md bg-white dark:bg-blue-900/40 border border-blue-200 px-3 py-2 text-xs">
                    <Loader2 className="w-3 h-3 text-blue-500 animate-spin flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <span className="font-mono font-medium text-gray-800 dark:text-gray-100 truncate block">{fileName}</span>
                      <span className="text-gray-400 text-[10px]">{comp.context}</span>
                    </div>
                    {elapsed !== null && (
                      <span className={`font-mono flex-shrink-0 ${elapsed > 30 ? "text-amber-500" : "text-blue-400"}`}>{elapsed}s</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* ── File Type Breakdown ── */}
      {(() => {
        const allComps = Object.values(repoComponents).flat();
        if (allComps.length === 0) return null;

        // Derive language from file extension
        const extCounts: Record<string, number> = {};
        for (const comp of allComps) {
          const loc = comp.location ?? comp.name ?? "";
          const fileName = loc.split("/").pop() ?? loc;
          const ext = fileName.includes(".") ? "." + fileName.split(".").pop()!.toLowerCase() : "(no ext)";
          extCounts[ext] = (extCounts[ext] ?? 0) + 1;
        }

        // Count repo-level skipped breakdown from repoStats (uses skipped_category_breakdown array)
        const skippedBreakdown: Record<string, number> = {};
        for (const stats of Object.values(repoStats)) {
          for (const cat of (stats as any).skipped_category_breakdown ?? []) {
            skippedBreakdown[cat.category] = (skippedBreakdown[cat.category] ?? 0) + (cat.count ?? 0);
          }
        }

        const topExts = Object.entries(extCounts)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 8);

        return (
          <div className="rounded-lg border bg-white dark:bg-gray-950 p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
              <BarChart2 className="w-4 h-4 text-indigo-500" />
              Repository File Breakdown
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {topExts.map(([ext, count]) => (
                <div key={ext} className="rounded-md border bg-gray-50 dark:bg-gray-900 px-3 py-2 flex items-center justify-between">
                  <span className="text-xs font-mono text-gray-600 dark:text-gray-400 truncate">{ext}</span>
                  <span className="text-xs font-bold text-gray-900 dark:text-gray-100 ml-2">{count}</span>
                </div>
              ))}
            </div>
            {Object.keys(skippedBreakdown).length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1 border-t">
                <span className="text-xs text-gray-400 self-center">Skipped:</span>
                {Object.entries(skippedBreakdown).map(([cat, cnt]) => (
                  <span key={cat} className="text-xs bg-gray-100 dark:bg-gray-800 text-gray-500 rounded-full px-2 py-0.5">
                    {cat}: {cnt}
                  </span>
                ))}
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

                              {/* ── Status Tabs + Flat File List ── */}
                              {(() => {
                                const activeTab = repoActiveTab[repo.id] ?? "all";
                                const skippedBreakdown: any[] = repoStats[repo.id]?.skipped_category_breakdown ?? [];
                                const skippedCount = repoStats[repo.id]?.skipped_files_count ?? 0;

                                const analyzingComps = components.filter(c => c.analysis_status === "processing");
                                const completedComps = components.filter(c => c.analysis_status === "completed" || c.analysis_status === "redirected");
                                const failedComps = components.filter(c => c.analysis_status === "failed");
                                const pendingComps = components.filter(c => c.analysis_status === "pending");

                                const tabs = [
                                  { id: "all", label: "All", count: components.length, color: "text-gray-600" },
                                  { id: "analyzing", label: "Analyzing", count: analyzingComps.length, color: "text-blue-600" },
                                  { id: "completed", label: "Done", count: completedComps.length, color: "text-green-600" },
                                  { id: "failed", label: "Failed", count: failedComps.length, color: "text-red-600" },
                                  { id: "pending", label: "Queued", count: pendingComps.length, color: "text-amber-600" },
                                  { id: "skipped", label: "Skipped", count: skippedCount, color: "text-slate-500" },
                                ];

                                let visibleComps: CodeComponent[] = components;
                                if (activeTab === "analyzing") visibleComps = analyzingComps;
                                else if (activeTab === "completed") visibleComps = completedComps;
                                else if (activeTab === "failed") visibleComps = failedComps;
                                else if (activeTab === "pending") visibleComps = pendingComps;

                                return (
                                  <div className="border rounded-lg overflow-hidden">
                                    {/* Tab bar */}
                                    <div className="flex items-center border-b bg-slate-50 dark:bg-slate-900 overflow-x-auto">
                                      {tabs.map(tab => (
                                        <button
                                          key={tab.id}
                                          onClick={() => setRepoActiveTab(prev => ({ ...prev, [repo.id]: tab.id }))}
                                          className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium whitespace-nowrap border-b-2 transition-colors ${
                                            activeTab === tab.id
                                              ? `border-blue-500 ${tab.color} bg-white dark:bg-slate-950`
                                              : "border-transparent text-muted-foreground hover:text-foreground hover:bg-white/60"
                                          }`}
                                        >
                                          {tab.label}
                                          {tab.count > 0 && (
                                            <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                                              activeTab === tab.id ? "bg-blue-100 text-blue-700" : "bg-muted"
                                            }`}>
                                              {tab.count}
                                            </span>
                                          )}
                                        </button>
                                      ))}
                                    </div>

                                    {/* Skipped tab: expandable categories with file paths */}
                                    {activeTab === "skipped" ? (
                                      <div className="divide-y">
                                        {skippedBreakdown.length === 0 ? (
                                          <div className="py-6 text-center text-sm text-muted-foreground">No skipped files</div>
                                        ) : skippedBreakdown.map((cat: any) => {
                                          const isOpen = (expandedSkippedCategories[repo.id] ?? new Set()).has(cat.category);
                                          const filesInCategory: any[] = (repoStats[repo.id]?.skipped_files ?? [])
                                            .filter((f: any) => f.category === cat.category);
                                          return (
                                            <div key={cat.category}>
                                              {/* Category header — clickable */}
                                              <button
                                                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/30 transition-colors text-left"
                                                onClick={() => toggleSkippedCategory(repo.id, cat.category)}
                                              >
                                                <EyeOff className="w-4 h-4 text-slate-300 flex-shrink-0" />
                                                <span className="text-sm flex-1 font-medium text-muted-foreground">{cat.category}</span>
                                                <span className="text-xs bg-slate-100 dark:bg-slate-800 text-slate-500 rounded-full px-2 py-0.5 mr-2">
                                                  {cat.count} files
                                                </span>
                                                {isOpen
                                                  ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                                                  : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                                                }
                                              </button>
                                              {/* Expanded file list */}
                                              {isOpen && (
                                                <div className="bg-muted/20 border-t border-b pb-1">
                                                  {filesInCategory.length > 0 ? (
                                                    filesInCategory.map((f: any, i: number) => (
                                                      <div key={i} className="flex items-center gap-2 px-8 py-1.5">
                                                        <span className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 rounded px-1.5 py-0.5 flex-shrink-0">
                                                          {f.ext || "(no ext)"}
                                                        </span>
                                                        <span className="text-xs font-mono text-muted-foreground truncate" title={f.path}>
                                                          {f.path}
                                                        </span>
                                                      </div>
                                                    ))
                                                  ) : (
                                                    <p className="px-8 py-2 text-xs text-muted-foreground italic">
                                                      File paths not available (re-analyze to populate)
                                                    </p>
                                                  )}
                                                </div>
                                              )}
                                            </div>
                                          );
                                        })}
                                        {skippedCount > 0 && (
                                          <div className="px-4 py-2 text-xs text-muted-foreground bg-slate-50/50">
                                            Binaries, images, compiled artifacts and similar files are not analyzed. Click a category to see file paths.
                                          </div>
                                        )}
                                      </div>
                                    ) : (
                                      /* Flat file list */
                                      <div>
                                        {visibleComps.length === 0 ? (
                                          <div className="py-8 text-center text-sm text-muted-foreground">
                                            {activeTab === "failed" ? "No failed files" :
                                             activeTab === "analyzing" ? "No files currently analyzing" :
                                             activeTab === "pending" ? "No files queued" :
                                             activeTab === "completed" ? "No completed files yet" : "No files"}
                                          </div>
                                        ) : (
                                          <>
                                            <div className="grid text-[11px] font-medium text-muted-foreground bg-muted/40 px-4 py-1.5 border-b"
                                              style={{ gridTemplateColumns: "1fr 90px 70px 70px 60px" }}>
                                              <span>File</span>
                                              <span>Status</span>
                                              <span className="text-right">Time</span>
                                              <span className="text-right">Cost</span>
                                              <span className="text-right">Actions</span>
                                            </div>
                                            {visibleComps.map((comp) => {
                                              const fileName = comp.name || comp.location?.split("/").pop() || "unknown";
                                              const dirPath = (() => {
                                                const loc = comp.location ?? "";
                                                const rawMatch = loc.match(/raw\.githubusercontent\.com\/[^/]+\/[^/]+\/[^/]+\/(.+)/);
                                                const ghMatch = loc.match(/github\.com\/[^/]+\/[^/]+\/(?:blob|tree)\/[^/]+\/(.+)/);
                                                const pathPart = rawMatch?.[1] ?? ghMatch?.[1] ?? "";
                                                const parts = pathPart.split("/");
                                                return parts.length > 1 ? parts.slice(0, -1).join("/") : "";
                                              })();
                                              const elapsed = comp.analysis_started_at
                                                ? Math.round(((comp.analysis_completed_at
                                                    ? new Date(comp.analysis_completed_at).getTime()
                                                    : Date.now()) - new Date(comp.analysis_started_at).getTime()) / 1000)
                                                : null;
                                              const isProcessing = comp.analysis_status === "processing";
                                              return (
                                                <div
                                                  key={comp.id}
                                                  className={`grid items-center px-4 py-2.5 border-b border-muted/20 text-sm hover:bg-muted/20 cursor-pointer group ${isProcessing ? "bg-blue-50/60 dark:bg-blue-950/20" : ""}`}
                                                  style={{ gridTemplateColumns: "1fr 90px 70px 70px 60px" }}
                                                  onClick={() => router.push(`/dashboard/code/${comp.id}`)}
                                                >
                                                  <div className="min-w-0 pr-4">
                                                    <div className="flex items-center gap-1.5">
                                                      {isProcessing && <Loader2 className="w-3 h-3 text-blue-500 animate-spin flex-shrink-0" />}
                                                      <span className="font-mono font-medium text-xs truncate">{fileName}</span>
                                                    </div>
                                                    {dirPath && (
                                                      <div className="text-[11px] text-muted-foreground font-mono truncate mt-0.5">/{dirPath}</div>
                                                    )}
                                                    {comp.analysis_status === "failed" && comp.summary && (
                                                      <div className="text-[11px] text-red-500 mt-0.5 truncate" title={comp.summary}>
                                                        {comp.summary.split("\n")[0]}
                                                      </div>
                                                    )}
                                                  </div>
                                                  <div>{getStatusBadge(comp.analysis_status)}</div>
                                                  <div className="text-right text-xs text-muted-foreground font-mono">
                                                    {elapsed !== null ? `${Math.max(0, elapsed)}s` : "—"}
                                                  </div>
                                                  <div className="text-right text-xs font-mono">
                                                    {comp.ai_cost_inr != null && comp.ai_cost_inr > 0
                                                      ? <span className="text-green-700">&#8377;{comp.ai_cost_inr.toFixed(2)}</span>
                                                      : <span className="text-muted-foreground">—</span>}
                                                  </div>
                                                  <div className="flex justify-end gap-1" onClick={e => e.stopPropagation()}>
                                                    {comp.analysis_status === "failed" && (
                                                      <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100"
                                                        disabled={retryingIds.has(comp.id)}
                                                        onClick={(e) => handleRetryComponent(comp.id, e)} title="Retry">
                                                        {retryingIds.has(comp.id) ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3 text-blue-500" />}
                                                      </Button>
                                                    )}
                                                    <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100"
                                                      onClick={() => setDeletingComponentId(comp.id)} title="Delete">
                                                      <Trash2 className="w-3 h-3 text-destructive" />
                                                    </Button>
                                                  </div>
                                                </div>
                                              );
                                            })}
                                          </>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                );
                              })()}
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
                      <div className="flex items-center justify-end gap-2">
                        {/* Push button: shown after user cancels the post-analysis push popup */}
                        {pendingPushMap[comp.id] && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 px-2 text-xs border-blue-300 text-blue-600 hover:bg-blue-50"
                            onClick={() => handlePushToRepo(
                              comp.id,
                              comp.location,
                              pendingPushMap[comp.id][0].matchId
                            )}
                            title={`Push to ${pendingPushMap[comp.id][0].repoName}`}
                          >
                            Push → {pendingPushMap[comp.id][0].repoName}
                          </Button>
                        )}
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
                      </div>
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

export default function CodePage() {
  return (
    <Suspense fallback={null}>
      <CodePageInner />
    </Suspense>
  );
}
