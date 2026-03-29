"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  FileText,
  PlusCircle,
  AlertCircle,
  Link as LinkIcon,
  Unlink,
  Loader2,
  CheckCircle,
  XCircle,
  Download,
  Trash2,
  Wallet,
  RefreshCw,
  IndianRupee,
  Sparkles,
} from "lucide-react";
import { api, API_BASE_URL } from "@/lib/api";
import Link from "next/link";
import { useBillingNotification } from "@/components/BillingToast";

// --- Interface Definitions ---
interface Document {
  id: number;
  filename: string;
  document_type: string;
  version: string;
  created_at: string;
  status: string;
  progress: number;
  error_message?: string | null;
  link_count?: number;
  ai_cost_inr?: number | null;
}

interface CodeComponent {
  id: number;
  name: string;
  component_type: string;
  version: string;
  location?: string;
  repository_id?: number | null;
  analysis_status?: string; // "completed" | "pending" | "failed" | "processing"
}

interface Repository {
  id: number;
  name: string;
  analysis_status: string;
}

// --- Helper: Format Status Text ---
const formatStatus = (status: string) => {
  switch (status) {
    case "uploaded":
      return "Queued";
    case "processing":
      return "Starting...";
    case "parsing":
      return "Extracting Text...";
    case "analyzing":
      return "AI Analysis...";
    case "pass_1_composition":
      return "Classifying...";
    case "pass_2_segmenting":
    case "pass_2_segmentation":
      return "Segmenting...";
    case "pass_3_extraction":
      return "Extracting Data...";
    case "completed":
      return "Completed";
    default:
      return status;
  }
};

// --- Upload Dialog Component ---
const UploadDialog = ({ onUploadSuccess }: { onUploadSuccess: () => void }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [version, setVersion] = useState("");
  const [documentType, setDocumentType] = useState("BRD");
  const [uploadStep, setUploadStep] = useState<
    "idle" | "uploading" | "triggering" | "done"
  >("idle");
  const [uploadProgress, setUploadProgress] = useState(0); // BUG-02 FIX
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleUploadAndAnalyze = async () => {
    if (!selectedFile || !version || !documentType) {
      setError("All fields are required.");
      return;
    }

    const token = localStorage.getItem("accessToken");
    setError(null);
    setUploadProgress(0);

    try {
      // --- Step 1: Upload with progress tracking (BUG-02 FIX) ---
      setUploadStep("uploading");
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("version", version);
      formData.append("document_type", documentType);

      // Show immediate visual feedback with a minimum progress value
      setUploadProgress(5);
      const docData = await new Promise<any>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${API_BASE_URL}/documents/upload`);
        xhr.setRequestHeader("Authorization", `Bearer ${token}`);

        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            // Ensure progress never appears to go backwards and always starts visible
            const pct = Math.max(5, Math.round((event.loaded / event.total) * 100));
            setUploadProgress(pct);
          }
        };

        xhr.onload = () => {
          setUploadProgress(100);
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              resolve(JSON.parse(xhr.responseText));
            } catch {
              reject(new Error("Invalid response from server"));
            }
          } else {
            try {
              const errData = JSON.parse(xhr.responseText);
              reject(new Error(errData.detail || "Upload failed"));
            } catch {
              reject(new Error(`Upload failed (${xhr.status})`));
            }
          }
        };

        xhr.onerror = () => reject(new Error("Network error during upload"));
        xhr.send(formData);
      });

      // --- Step 2: Trigger Analysis ---
      setUploadStep("triggering");
      const analyzeRes = await fetch(
        `${API_BASE_URL}/documents/${docData.id}/analyze`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!analyzeRes.ok) {
        console.error("Failed to trigger analysis automatically");
      }

      // Success
      setUploadStep("done");
      onUploadSuccess();

      // Reset form after a short delay
      setTimeout(() => {
        setIsOpen(false);
        setUploadStep("idle");
        setSelectedFile(null);
        setVersion("");
        setUploadProgress(0);
      }, 1000);
    } catch (err) {
      setError((err as Error).message);
      setUploadStep("idle");
      setUploadProgress(0);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <PlusCircle className="mr-2 h-4 w-4" /> Upload Document
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Upload New Document</DialogTitle>
          <DialogDescription>
            Select a file to upload. Analysis will start automatically.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="file">Document File</Label>
            <Input
              id="file"
              type="file"
              onChange={handleFileChange}
              disabled={uploadStep !== "idle"}
            />
          </div>
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="version">Version</Label>
            <Input
              id="version"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="e.g., v1.0"
              disabled={uploadStep !== "idle"}
            />
          </div>
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="documentType">Document Type</Label>
            <select
              id="documentType"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
              disabled={uploadStep !== "idle"}
            >
              <option value="BRD">BRD</option>
              <option value="SRS">SRS</option>
              <option value="Tech Spec">Tech Spec</option>
              <option value="Other">Other</option>
            </select>
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          {/* BUG-02 FIX: Show upload progress bar */}
          {uploadStep === "uploading" && (
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Uploading file...</span>
                <span>{uploadProgress}%</span>
              </div>
              <Progress value={uploadProgress} className="h-2" />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button
            onClick={handleUploadAndAnalyze}
            disabled={uploadStep !== "idle"}
          >
            {uploadStep === "idle" && "Upload & Analyze"}
            {uploadStep === "uploading" && (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Uploading {uploadProgress}%
              </>
            )}
            {uploadStep === "triggering" && (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Starting AI...
              </>
            )}
            {uploadStep === "done" && (
              <>
                <CheckCircle className="mr-2 h-4 w-4" /> Done!
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// --- Helpers for Link Modal ---

/** Extract relative file path from raw.githubusercontent.com URL */
function extractRelativePath(location?: string): string {
  if (!location) return "";
  // https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{...path}
  const m = location.match(/raw\.githubusercontent\.com\/[^/]+\/[^/]+\/[^/]+\/(.+)/);
  return m ? m[1] : location;
}

/** Get top-level folder from a relative path */
function topFolder(relativePath: string): string {
  const parts = relativePath.split("/");
  return parts.length > 1 ? parts[0] : "(root)";
}

/** Analysis status badge */
const StatusBadge = ({ status }: { status?: string }) => {
  if (status === "completed")
    return <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-green-100 text-green-700">Analyzed ✓</span>;
  if (status === "failed")
    return <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-red-100 text-red-600">Failed</span>;
  if (status === "processing" || status === "pending")
    return <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-600">Pending</span>;
  return null;
};

// --- Manage Links Dialog Component ---
const ManageLinksDialog = ({
  document,
  onLinksChanged,
}: {
  document: Document;
  onLinksChanged: () => void;
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [allComponents, setAllComponents] = useState<CodeComponent[]>([]);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [linkedIds, setLinkedIds] = useState<Set<number>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [onlyAnalyzed, setOnlyAnalyzed] = useState(true);
  const [expandedRepos, setExpandedRepos] = useState<Set<number | string>>(new Set());
  const [toggling, setToggling] = useState<Set<number>>(new Set());
  const token = localStorage.getItem("accessToken");

  const fetchAllData = useCallback(async () => {
    if (!isOpen || !token) return;
    setIsLoading(true);
    setError(null);
    try {
      const [compsRes, linkedRes, reposRes] = await Promise.all([
        fetch(`${API_BASE_URL}/code-components/?limit=1000`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE_URL}/links/document/${document.id}`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE_URL}/repositories/`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (!compsRes.ok) throw new Error("Failed to fetch code components.");
      if (!linkedRes.ok) throw new Error("Failed to fetch existing links.");

      const comps: CodeComponent[] = await compsRes.json();
      const linked: CodeComponent[] = await linkedRes.json();
      setAllComponents(comps);
      setLinkedIds(new Set(linked.map((c) => c.id)));

      if (reposRes.ok) {
        const reposData = await reposRes.json();
        setRepos(Array.isArray(reposData) ? reposData : reposData.items || []);
      }

      // Auto-expand repos that have linked files
      const linkedRepoIds = new Set(linked.map((c) => {
        const full = comps.find((x) => x.id === c.id);
        return full?.repository_id ?? "standalone";
      }));
      setExpandedRepos(linkedRepoIds as Set<number | string>);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [isOpen, document.id, token]);

  useEffect(() => { fetchAllData(); }, [fetchAllData]);

  const handleLinkToggle = async (comp: CodeComponent) => {
    const isLinked = linkedIds.has(comp.id);
    setToggling((prev) => new Set(prev).add(comp.id));
    try {
      const res = await fetch(`${API_BASE_URL}/links/`, {
        method: isLinked ? "DELETE" : "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ document_id: document.id, code_component_id: comp.id }),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || `Failed to ${isLinked ? "unlink" : "link"}`);
      }
      // Optimistic update — avoid full refetch for snappy UX
      setLinkedIds((prev) => {
        const next = new Set(prev);
        isLinked ? next.delete(comp.id) : next.add(comp.id);
        return next;
      });
      onLinksChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setToggling((prev) => { const next = new Set(prev); next.delete(comp.id); return next; });
    }
  };

  // Build repo map for names
  const repoMap = new Map(repos.map((r) => [r.id, r.name]));

  // Filter logic
  const term = search.toLowerCase();
  const visible = allComponents.filter((c) => {
    if (onlyAnalyzed && c.analysis_status !== "completed") return false;
    if (!term) return true;
    const rel = extractRelativePath(c.location);
    return c.name.toLowerCase().includes(term) || rel.toLowerCase().includes(term);
  });

  // Group by repo → folder
  type FolderMap = Map<string, CodeComponent[]>;
  type RepoGroup = { repoId: number | string; repoName: string; folders: FolderMap; linkedCount: number };
  const repoGroups = new Map<number | string, RepoGroup>();

  for (const comp of visible) {
    const repoId = comp.repository_id ?? "standalone";
    const repoName = comp.repository_id ? (repoMap.get(comp.repository_id) ?? `Repo #${comp.repository_id}`) : "Standalone Files";
    if (!repoGroups.has(repoId)) {
      repoGroups.set(repoId, { repoId, repoName, folders: new Map(), linkedCount: 0 });
    }
    const group = repoGroups.get(repoId)!;
    if (linkedIds.has(comp.id)) group.linkedCount++;
    const rel = extractRelativePath(comp.location);
    const folder = topFolder(rel);
    if (!group.folders.has(folder)) group.folders.set(folder, []);
    group.folders.get(folder)!.push(comp);
  }

  // Linked first, then alphabetical
  const sortedGroups = [...repoGroups.values()].sort((a, b) => b.linkedCount - a.linkedCount);

  const totalLinked = linkedIds.size;
  const totalVisible = visible.length;

  const toggleRepo = (id: number | string) => {
    setExpandedRepos((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={(o) => { setIsOpen(o); if (!o) setSearch(""); }}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <LinkIcon className="mr-2 h-4 w-4" />
          Link Code ({document.link_count || 0})
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Link Code Files — {document.filename}</DialogTitle>
          <DialogDescription>
            Linked files are used by the validation engine to detect mismatches between this document and the actual code.
          </DialogDescription>
        </DialogHeader>

        {/* Controls */}
        <div className="flex gap-2 items-center">
          <Input
            placeholder="Search by filename or path..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 h-8 text-sm"
          />
          <label className="flex items-center gap-1.5 text-xs text-gray-600 whitespace-nowrap cursor-pointer select-none">
            <input
              type="checkbox"
              checked={onlyAnalyzed}
              onChange={(e) => setOnlyAnalyzed(e.target.checked)}
              className="rounded"
            />
            Analyzed only
          </label>
        </div>

        {/* Summary bar */}
        <div className="flex items-center gap-3 text-xs text-gray-500 border-b pb-2">
          <span><span className="font-semibold text-blue-600">{totalLinked}</span> linked</span>
          <span>·</span>
          <span>{totalVisible} files shown</span>
          {!onlyAnalyzed && (
            <span className="text-amber-600">⚠ Unanalyzed files cannot be validated</span>
          )}
        </div>

        {isLoading && <p className="text-sm text-gray-500 py-4 text-center">Loading...</p>}
        {error && <p className="text-sm text-red-500 px-1">{error}</p>}

        {!isLoading && !error && (
          <div className="flex-1 overflow-y-auto space-y-2 pr-1 min-h-0">

            {sortedGroups.length === 0 && (
              <p className="text-sm text-gray-400 text-center py-8">
                {search ? `No files matching "${search}"` : onlyAnalyzed ? "No analyzed files found. Uncheck 'Analyzed only' to see all files." : "No code files found."}
              </p>
            )}

            {sortedGroups.map(({ repoId, repoName, folders, linkedCount }) => {
              const isExpanded = expandedRepos.has(repoId);
              const totalInRepo = [...folders.values()].reduce((s, f) => s + f.length, 0);

              return (
                <div key={String(repoId)} className="border rounded-lg overflow-hidden">
                  {/* Repo header */}
                  <button
                    onClick={() => toggleRepo(repoId)}
                    className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 text-left"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-800">{repoName}</span>
                      {linkedCount > 0 && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
                          {linkedCount} linked
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-gray-400">
                      <span>{totalInRepo} files</span>
                      <span>{isExpanded ? "▲" : "▼"}</span>
                    </div>
                  </button>

                  {/* Folders + files */}
                  {isExpanded && (
                    <div className="divide-y">
                      {[...folders.entries()].map(([folder, files]) => {
                        const folderLinked = files.filter((f) => linkedIds.has(f.id)).length;
                        return (
                          <div key={folder}>
                            {/* Folder subheader */}
                            <div className="px-3 py-1 bg-gray-50/50 flex items-center justify-between">
                              <span className="text-xs text-gray-500 font-mono">{folder}/</span>
                              {folderLinked > 0 && (
                                <span className="text-[10px] text-blue-500">{folderLinked} linked</span>
                              )}
                            </div>
                            {/* Files */}
                            <ul className="divide-y divide-gray-50">
                              {files.map((comp) => {
                                const isLinked = linkedIds.has(comp.id);
                                const isToggling = toggling.has(comp.id);
                                const rel = extractRelativePath(comp.location);
                                // Show path without the top folder (already shown in header)
                                const displayPath = rel.includes("/") ? rel.split("/").slice(1).join("/") : rel;
                                const notAnalyzed = comp.analysis_status !== "completed";

                                return (
                                  <li
                                    key={comp.id}
                                    className={`flex items-center justify-between px-3 py-2 hover:bg-gray-50 transition-colors ${isLinked ? "bg-blue-50/60" : ""}`}
                                  >
                                    <div className="min-w-0 flex-1 mr-3">
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <span className={`text-sm font-medium truncate ${notAnalyzed ? "text-gray-400" : "text-gray-800"}`}>
                                          {comp.name}
                                        </span>
                                        <StatusBadge status={comp.analysis_status} />
                                      </div>
                                      {displayPath && displayPath !== comp.name && (
                                        <p className="text-xs text-gray-400 font-mono truncate">{displayPath}</p>
                                      )}
                                    </div>
                                    <Button
                                      variant={isLinked ? "destructive" : "outline"}
                                      size="sm"
                                      className={`shrink-0 h-7 px-2 text-xs ${!isLinked ? "hover:border-blue-400 hover:text-blue-600" : ""}`}
                                      disabled={isToggling || (notAnalyzed && !isLinked)}
                                      onClick={() => handleLinkToggle(comp)}
                                      title={notAnalyzed && !isLinked ? "File must be analyzed first for validation to work" : ""}
                                    >
                                      {isToggling ? (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                      ) : isLinked ? (
                                        <><Unlink className="h-3 w-3 mr-1" />Unlink</>
                                      ) : (
                                        <><LinkIcon className="h-3 w-3 mr-1" />Link</>
                                      )}
                                    </Button>
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

// --- Document Status Cell Component (With Live Polling & Billing Notifications) ---
const DocumentStatusCell = ({
  doc,
  onUpdate,
}: {
  doc: Document;
  onUpdate: (updatedDoc: Document) => void;
}) => {
  const [status, setStatus] = useState(doc.status);
  const [progress, setProgress] = useState(doc.progress);
  const [errorMessage, setErrorMessage] = useState(doc.error_message);
  const [notifiedProcessing, setNotifiedProcessing] = useState(false);
  const billingNotification = useBillingNotification();

  useEffect(() => {
    // Define active states that require polling
    const activeStates = [
      "uploaded",
      "processing",
      "parsing",
      "analyzing",
      "pass_1_composition",
      "pass_2_segmenting",
      "pass_2_segmentation",
      "pass_3_extraction",
    ];

    // Show processing started notification when entering AI analysis phases
    const aiStates = ["analyzing", "pass_1_composition", "pass_2_segmenting", "pass_3_extraction"];
    if (aiStates.includes(status) && !notifiedProcessing) {
      setNotifiedProcessing(true);
      // Fetch current balance and show notification
      billingNotification.refreshBalance().then((balance) => {
        if (balance !== null) {
          billingNotification.showProcessingStarted(balance);
        }
      });
    }

    if (activeStates.includes(status)) {
      const intervalId = setInterval(async () => {
        const token = localStorage.getItem("accessToken");
        try {
          const response = await fetch(
            `${API_BASE_URL}/documents/${doc.id}/status`,
            { headers: { Authorization: `Bearer ${token}` } }
          );

          if (!response.ok) return; // Skip this poll if error

          const data = await response.json();

          // Only update if something changed
          if (data.status !== status || data.progress !== progress) {
            setStatus(data.status);
            setProgress(data.progress);
            setErrorMessage(data.error_message);

            // Show completion notification with cost
            if (data.status === "completed") {
              // Fetch document cost and new balance
              try {
                const [costData, newBalance] = await Promise.all([
                  api.get<{ ai_cost_inr: number }>(`/billing/documents/${doc.id}/cost`),
                  billingNotification.refreshBalance(),
                ]);
                const cost = costData?.ai_cost_inr || 0;
                billingNotification.showProcessingComplete(cost, newBalance || 0);
              } catch (err) {
                console.error("Failed to fetch document cost:", err);
              }

              onUpdate({
                ...doc,
                status: data.status,
                progress: data.progress,
                error_message: data.error_message,
              });
            } else if (data.status.includes("failed")) {
              billingNotification.showError(data.error_message || "Document processing failed");
              onUpdate({
                ...doc,
                status: data.status,
                progress: data.progress,
                error_message: data.error_message,
              });
            }
          }

          // Stop polling if done or failed
          if (data.status === "completed" || data.status.includes("failed")) {
            clearInterval(intervalId);
          }
        } catch (error) {
          console.error("Polling error:", error);
        }
      }, 3000); // Poll every 3 seconds

      return () => clearInterval(intervalId);
    }
  }, [status, doc.id, onUpdate, doc, progress, notifiedProcessing, billingNotification]);

  if (status === "completed") {
    return (
      <span className="flex items-center text-green-600 font-medium">
        <CheckCircle className="w-4 h-4 mr-1" /> Completed
      </span>
    );
  }

  if (status.includes("failed") || status.includes("error")) {
    return (
      <div className="flex flex-col">
        <span className="flex items-center text-red-600 font-medium">
          <XCircle className="w-4 h-4 mr-1" /> Failed
        </span>
        {errorMessage && (
          <span
            className="text-xs text-red-500 max-w-[150px] truncate"
            title={errorMessage}
          >
            {errorMessage}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
        <span>{formatStatus(status)}</span>
        <span>{progress}%</span>
      </div>
      <Progress value={progress} className="w-24 h-2" />
    </div>
  );
};

// --- Balance Display Component ---
const BalanceDisplay = ({
  balance,
  billingType,
  lowBalanceAlert,
  onRefresh,
  isRefreshing
}: {
  balance: number;
  billingType: string;
  lowBalanceAlert: boolean;
  onRefresh: () => void;
  isRefreshing: boolean;
}) => {
  if (billingType !== "prepaid") return null;

  const isLow = balance < 100 || lowBalanceAlert;

  return (
    <div className={`flex items-center gap-2 rounded-lg px-3 py-2 ${
      isLow ? "bg-orange-50 border border-orange-200" : "bg-green-50 border border-green-200"
    }`}>
      <Wallet className={`h-4 w-4 ${isLow ? "text-orange-600" : "text-green-600"}`} />
      <div className="flex flex-col">
        <span className="text-xs text-gray-500">Balance</span>
        <span className={`font-semibold ${isLow ? "text-orange-700" : "text-green-700"}`}>
          INR {balance.toFixed(2)}
        </span>
      </div>
      <button
        onClick={onRefresh}
        disabled={isRefreshing}
        className="ml-1 p-1 rounded hover:bg-white/50"
        title="Refresh balance"
      >
        <RefreshCw className={`h-3 w-3 text-gray-400 ${isRefreshing ? "animate-spin" : ""}`} />
      </button>
      {isLow && (
        <Link
          href="/settings/billing"
          className="text-xs text-orange-600 underline hover:text-orange-800"
        >
          Top up
        </Link>
      )}
    </div>
  );
};

// --- Main Documents Page Component ---
export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [billingInfo, setBillingInfo] = useState<{
    balance: number;
    billingType: string;
    lowBalanceAlert: boolean;
  } | null>(null);
  const [refreshingBalance, setRefreshingBalance] = useState(false);

  interface BillingUsageResponse {
    balance_inr?: number;
    billing_type?: string;
    low_balance_alert?: boolean;
  }

  const fetchBillingInfo = useCallback(async () => {
    try {
      const data = await api.get<BillingUsageResponse>("/billing/usage");
      setBillingInfo({
        balance: data?.balance_inr || 0,
        billingType: data?.billing_type || "prepaid",
        lowBalanceAlert: data?.low_balance_alert || false,
      });
    } catch (err) {
      console.error("Failed to fetch billing info:", err);
    }
  }, []);

  const handleRefreshBalance = async () => {
    setRefreshingBalance(true);
    await fetchBillingInfo();
    setRefreshingBalance(false);
  };

  const fetchDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setError("Authentication token not found.");
      setIsLoading(false);
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/documents/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to fetch documents.");
      }
      const raw = await response.json();
      const data: Document[] = Array.isArray(raw) ? raw : (raw.items ?? raw.documents ?? []);

      // Fetch link counts
      const documentsWithLinkCounts = await Promise.all(
        data.map(async (doc) => {
          try {
            const linksResponse = await fetch(
              `${API_BASE_URL}/links/document/${doc.id}`,
              { headers: { Authorization: `Bearer ${token}` } }
            );
            if (!linksResponse.ok) return { ...doc, link_count: 0 };
            const linkedComponents: CodeComponent[] =
              await linksResponse.json();
            return { ...doc, link_count: linkedComponents.length };
          } catch {
            return { ...doc, link_count: 0 };
          }
        })
      );

      // Sort by newest first
      documentsWithLinkCounts.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setDocuments(documentsWithLinkCounts);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
    fetchBillingInfo();
  }, [fetchDocuments, fetchBillingInfo]);

  const handleDocumentUpdate = (updatedDoc: Document) => {
    setDocuments((currentDocs) =>
      currentDocs.map((d) => (d.id === updatedDoc.id ? updatedDoc : d))
    );
    // Refresh balance when a document finishes processing (completed or failed)
    if (updatedDoc.status === "completed" || updatedDoc.status.includes("failed")) {
      fetchBillingInfo();
    }
  };

  // Helper for download
  const handleDownload = (docId: number, filename: string) => {
    const token = localStorage.getItem("accessToken");
    fetch(`${API_BASE_URL}/documents/${docId}/download`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => response.blob())
      .then((blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
      })
      .catch((err) => console.error("Download failed", err));
  };

  // --- Delete Handler ---
  const handleDelete = async (id: number, filename: string) => {
    if (
      !confirm(
        `Are you sure you want to delete "${filename}"? This cannot be undone.`
      )
    ) {
      return;
    }

    setDeletingId(id);
    const token = localStorage.getItem("accessToken");

    try {
      const response = await fetch(
        `${API_BASE_URL}/documents/${id}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!response.ok) {
        throw new Error("Failed to delete document");
      }

      // Remove from UI immediately
      setDocuments((docs) => docs.filter((d) => d.id !== id));
    } catch (err) {
      alert("Error deleting document: " + (err as Error).message);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="p-2 sm:p-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
          Document Library
        </h1>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/chat?doc=0"
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-purple-600 bg-purple-50 hover:bg-purple-100 rounded-lg transition-colors"
          >
            <Sparkles className="h-4 w-4" />
            Ask AI about documents
          </Link>
          {billingInfo && (
            <BalanceDisplay
              balance={billingInfo.balance}
              billingType={billingInfo.billingType}
              lowBalanceAlert={billingInfo.lowBalanceAlert}
              onRefresh={handleRefreshBalance}
              isRefreshing={refreshingBalance}
            />
          )}
          <UploadDialog onUploadSuccess={() => {
            fetchDocuments();
            // Refresh balance after upload triggers analysis
            setTimeout(fetchBillingInfo, 2000);
          }} />
        </div>
      </div>

      {isLoading && (
        <div className="flex justify-center p-10">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      )}

      {error && (
        <div className="text-red-500 bg-red-100 p-4 rounded-lg flex items-center mb-4">
          <AlertCircle className="mr-2" /> Error: {error}
        </div>
      )}

      {!isLoading && !error && (
        <div className="rounded-lg border shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Filename</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Analysis Cost</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.length > 0 ? (
                documents.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center">
                        <FileText className="h-4 w-4 mr-2 text-blue-500" />
                        <a
                          href={`/dashboard/documents/${doc.id}`}
                          className="text-blue-600 hover:underline font-semibold"
                        >
                          {doc.filename}
                        </a>
                        {/* Download Button */}
                        <button
                          onClick={() => handleDownload(doc.id, doc.filename)}
                          className="ml-2 text-gray-400 hover:text-gray-700"
                          title="Download Original"
                        >
                          <Download className="h-3 w-3" />
                        </button>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80">
                        {doc.document_type}
                      </span>
                    </TableCell>
                    <TableCell>{doc.version}</TableCell>
                    <TableCell>
                      <DocumentStatusCell
                        doc={doc}
                        onUpdate={handleDocumentUpdate}
                      />
                    </TableCell>
                    <TableCell>
                      {doc.status === "completed" && doc.ai_cost_inr != null ? (
                        <span className="flex items-center gap-1 text-green-700 font-medium">
                          <IndianRupee className="h-3 w-3" />
                          {doc.ai_cost_inr.toFixed(2)}
                        </span>
                      ) : doc.status === "completed" ? (
                        <span className="text-gray-400 text-sm">-</span>
                      ) : (
                        <span className="text-gray-400 text-sm">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end items-center gap-2">
                        <ManageLinksDialog
                          document={doc}
                          onLinksChanged={fetchDocuments}
                        />

                        {/* Delete Button */}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-500 hover:text-red-700 hover:bg-red-50"
                          onClick={() => handleDelete(doc.id, doc.filename)}
                          disabled={deletingId === doc.id}
                          title="Delete Document"
                        >
                          {deletingId === doc.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="text-center h-24 text-muted-foreground"
                  >
                    No documents found. Upload your first document to get
                    started.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
