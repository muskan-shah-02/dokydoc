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
} from "lucide-react";
import { api } from "@/lib/api";
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

    try {
      // --- Step 1: Upload ---
      setUploadStep("uploading");
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("version", version);
      formData.append("document_type", documentType);

      const uploadRes = await fetch(
        "http://localhost:8000/api/v1/documents/upload",
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        }
      );

      if (!uploadRes.ok) {
        const errData = await uploadRes.json();
        throw new Error(errData.detail || "Upload failed");
      }

      const docData = await uploadRes.json();

      // --- Step 2: Trigger Analysis ---
      setUploadStep("triggering");
      const analyzeRes = await fetch(
        `http://localhost:8000/api/v1/documents/${docData.id}/analyze`,
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
      }, 1000);
    } catch (err) {
      setError((err as Error).message);
      setUploadStep("idle");
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
        </div>
        <DialogFooter>
          <Button
            onClick={handleUploadAndAnalyze}
            disabled={uploadStep !== "idle"}
          >
            {uploadStep === "idle" && "Upload & Analyze"}
            {uploadStep === "uploading" && (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Uploading...
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

// --- Manage Links Dialog Component ---
const ManageLinksDialog = ({
  document,
  onLinksChanged,
}: {
  document: Document;
  onLinksChanged: () => void;
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [allCodeComponents, setAllCodeComponents] = useState<CodeComponent[]>(
    []
  );
  const [linkedComponentIds, setLinkedComponentIds] = useState<Set<number>>(
    new Set()
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = localStorage.getItem("accessToken");

  const fetchAllData = useCallback(async () => {
    if (!isOpen || !token) return;
    setIsLoading(true);
    setError(null);
    try {
      const componentsRes = await fetch(
        "http://localhost:8000/api/v1/code-components/",
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!componentsRes.ok)
        throw new Error("Failed to fetch code components.");
      const allComps: CodeComponent[] = await componentsRes.json();
      setAllCodeComponents(allComps);

      const linkedRes = await fetch(
        `http://localhost:8000/api/v1/links/document/${document.id}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!linkedRes.ok) throw new Error("Failed to fetch existing links.");
      const linkedComps: CodeComponent[] = await linkedRes.json();
      setLinkedComponentIds(new Set(linkedComps.map((c) => c.id)));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [isOpen, document.id, token]);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  const handleLinkToggle = async (component: CodeComponent) => {
    const isCurrentlyLinked = linkedComponentIds.has(component.id);
    const endpoint = "http://localhost:8000/api/v1/links/";
    const method = isCurrentlyLinked ? "DELETE" : "POST";
    try {
      const response = await fetch(endpoint, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          document_id: document.id,
          code_component_id: component.id,
        }),
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(
          errData.detail || `Failed to ${isCurrentlyLinked ? "unlink" : "link"}`
        );
      }
      await fetchAllData();
      onLinksChanged();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <LinkIcon className="mr-2 h-4 w-4" /> Link Code (
          {document.link_count || 0})
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Link Code to: {document.filename}</DialogTitle>
          <DialogDescription>
            Select code components to associate with this document.
          </DialogDescription>
        </DialogHeader>
        {isLoading && <p>Loading...</p>}
        {error && <p className="text-sm text-red-500">{error}</p>}
        {!isLoading && !error && (
          <div className="max-h-80 overflow-y-auto p-1">
            <ul className="space-y-2">
              {allCodeComponents.map((comp) => (
                <li
                  key={comp.id}
                  className="flex items-center justify-between p-2 rounded-md hover:bg-gray-100"
                >
                  <div>
                    <p className="font-semibold">{comp.name}</p>
                    <p className="text-sm text-gray-500">
                      {comp.component_type} - v{comp.version}
                    </p>
                  </div>
                  <Button
                    variant={
                      linkedComponentIds.has(comp.id)
                        ? "destructive"
                        : "default"
                    }
                    size="sm"
                    onClick={() => handleLinkToggle(comp)}
                  >
                    {linkedComponentIds.has(comp.id) ? (
                      <Unlink className="h-4 w-4" />
                    ) : (
                      <LinkIcon className="h-4 w-4" />
                    )}
                  </Button>
                </li>
              ))}
            </ul>
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
            `http://localhost:8000/api/v1/documents/${doc.id}/status`,
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
      const response = await fetch("http://localhost:8000/api/v1/documents/", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to fetch documents.");
      }
      const data: Document[] = await response.json();

      // Fetch link counts
      const documentsWithLinkCounts = await Promise.all(
        data.map(async (doc) => {
          try {
            const linksResponse = await fetch(
              `http://localhost:8000/api/v1/links/document/${doc.id}`,
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
    fetch(`http://localhost:8000/api/v1/documents/${docId}/download`, {
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
        `http://localhost:8000/api/v1/documents/${id}`,
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
