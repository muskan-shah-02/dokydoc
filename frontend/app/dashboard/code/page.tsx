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
  File,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useRouter } from "next/navigation";

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

export default function CodePage() {
  // --- State: Repositories (primary view) ---
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [standaloneComponents, setStandaloneComponents] = useState<CodeComponent[]>([]);
  const [expandedRepos, setExpandedRepos] = useState<Set<number>>(new Set());
  const [repoComponents, setRepoComponents] = useState<Record<number, CodeComponent[]>>({});
  const [loadingRepoComponents, setLoadingRepoComponents] = useState<Set<number>>(new Set());

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

  const fetchRepoComponents = useCallback(async (repoId: number) => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;

    setLoadingRepoComponents((prev) => new Set(prev).add(repoId));
    try {
      const res = await fetch(
        `http://localhost:8000/api/v1/repositories/${repoId}/components`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        setRepoComponents((prev) => ({ ...prev, [repoId]: data }));
      }
    } catch (error) {
      console.error(`Failed to fetch components for repo ${repoId}:`, error);
    } finally {
      setLoadingRepoComponents((prev) => {
        const next = new Set(prev);
        next.delete(repoId);
        return next;
      });
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
        }
        return next;
      });
    },
    [repoComponents, fetchRepoComponents]
  );

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
      pollIntervalRef.current = setInterval(() => fetchData(), 10000);
    }
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [hasActiveAnalysis, fetchData]);

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
    <div className="p-6 space-y-6">
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
                            <div className="text-xs text-muted-foreground truncate">{repo.url}</div>
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
                        <div className="text-sm text-muted-foreground w-24 text-right">
                          {total > 0 ? (
                            <span className="font-mono">{analyzed}/{total} files</span>
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
                      <div className="ml-8 mr-2 border-l-2 border-muted pl-4 py-2 space-y-1">
                        {isLoadingComponents ? (
                          <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Loading files...
                          </div>
                        ) : components.length === 0 ? (
                          <div className="py-3 text-sm text-muted-foreground">
                            No analyzed files yet
                          </div>
                        ) : (
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead>File</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead className="text-right">Duration</TableHead>
                                <TableHead className="text-right">Cost</TableHead>
                                <TableHead className="text-right w-20">Actions</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {components.map((comp) => (
                                <TableRow
                                  key={comp.id}
                                  className={`hover:bg-muted/30 ${comp.analysis_status === "failed" ? "bg-red-50/50" : ""}`}
                                >
                                  <TableCell
                                    className="cursor-pointer"
                                    onClick={() => router.push(`/dashboard/code/${comp.id}`)}
                                  >
                                    <div className="flex items-center gap-2">
                                      <File className={`w-4 h-4 flex-shrink-0 ${comp.analysis_status === "failed" ? "text-red-400" : "text-muted-foreground"}`} />
                                      <div className="min-w-0">
                                        <span className="truncate text-sm block">{comp.name}</span>
                                        {comp.analysis_status === "failed" && comp.summary && (
                                          <span className="text-xs text-red-500 block truncate" title={comp.summary}>
                                            {comp.summary.length > 80 ? comp.summary.slice(0, 78) + "..." : comp.summary}
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  </TableCell>
                                  <TableCell>
                                    <div className="flex items-center gap-1.5">
                                      {getStatusIcon(comp.analysis_status)}
                                      {getStatusBadge(comp.analysis_status)}
                                    </div>
                                  </TableCell>
                                  <TableCell className="text-right text-sm text-muted-foreground">
                                    {comp.analysis_started_at && comp.analysis_completed_at ? (
                                      formatElapsed(
                                        Math.round(
                                          (new Date(comp.analysis_completed_at).getTime() -
                                            new Date(comp.analysis_started_at).getTime()) / 1000
                                        )
                                      )
                                    ) : comp.analysis_status === "processing" && comp.analysis_started_at ? (
                                      <span className="font-mono text-blue-600">
                                        {formatElapsed(elapsedSince(comp.analysis_started_at))}
                                      </span>
                                    ) : (
                                      "—"
                                    )}
                                  </TableCell>
                                  <TableCell className="text-right font-mono text-sm">
                                    {comp.ai_cost_inr != null && comp.ai_cost_inr > 0 ? (
                                      <span className="text-green-700">&#8377;{comp.ai_cost_inr.toFixed(2)}</span>
                                    ) : (
                                      <span className="text-muted-foreground">—</span>
                                    )}
                                  </TableCell>
                                  <TableCell className="text-right">
                                    {comp.analysis_status === "failed" && (
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        className="h-7 px-2 text-xs border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700"
                                        disabled={retryingIds.has(comp.id)}
                                        onClick={(e) => handleRetryComponent(comp.id, e)}
                                      >
                                        {retryingIds.has(comp.id) ? (
                                          <Loader2 className="w-3 h-3 animate-spin mr-1" />
                                        ) : (
                                          <RefreshCw className="w-3 h-3 mr-1" />
                                        )}
                                        Retry
                                      </Button>
                                    )}
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        )}
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
