"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { API_BASE_URL } from "@/lib/api";
import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ShieldCheck,
  Loader2,
  AlertTriangle,
  FileText,
  Code,
  Zap,
  CheckCircle,
  XCircle,
  Info,
  Search,
  Filter,
  RefreshCw,
  ScanLine,
  Users,
  Settings,
  Eye,
  Sparkles,
  GitBranch,
  TicketCheck,
  CircleCheck,
  CircleDot,
  CircleX,
  Link as LinkIcon,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// --- Data Structures ---
interface Document {
  id: number;
  filename: string;
  version: string;
  status: string;
  last_scanned?: string;
  mismatch_count?: number;
  document_type?: string;
  file_size_kb?: number;
}

interface MismatchDetails {
  expected: string;
  actual: string;
  evidence_document: string;
  evidence_code: string;
  suggested_action: string;
  classification?: "SCOPE_CREEP" | "IMPLICIT_REQUIREMENT" | "UNDOCUMENTED";
}

interface Mismatch {
  id: number;
  mismatch_type: string;
  description: string;
  severity: "High" | "Medium" | "Low";
  confidence: "High" | "Medium" | "Low";
  status: string;
  details: MismatchDetails;
  direction?: "forward" | "reverse";
  requirement_atom_id?: number | null;
  document: { id: number; name: string };
  code_component: { id: number; name: string };
}

interface CoverageSuggestion {
  component_id: number;
  component_name: string;
  relevance_score: number;
  reason: string;
  gaps_addressed: string[];
}

interface DocSuggestions {
  doc_id: number;
  doc_name: string;
  items: CoverageSuggestion[];
}

export default function ValidationPanelPage() {
  const router = useRouter();

  // State management
  const [documents, setDocuments] = useState<Document[]>([]);
  const [filteredDocuments, setFilteredDocuments] = useState<Document[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<Set<number>>(new Set());
  const [mismatches, setMismatches] = useState<Mismatch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [activeTab, setActiveTab] = useState("select");

  // Coverage suggestion state
  const [suggestions, setSuggestions] = useState<DocSuggestions[]>([]);
  const [dismissedDocs, setDismissedDocs] = useState<Set<number>>(new Set());
  const [expandedMismatchTypes, setExpandedMismatchTypes] = useState<Set<string>>(new Set());

  // Two-sided report: "developer" (forward mismatches) or "ba" (reverse mismatches)
  const [reportSide, setReportSide] = useState<"developer" | "ba">("developer");

  // Atom counts per document for coverage score (document_id → total_atoms)
  const [atomCounts, setAtomCounts] = useState<Record<number, number>>({});

  // Fetch documents and mismatches
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setError("Authentication token not found.");
      setIsLoading(false);
      return;
    }

    try {
      const [docResponse, mismatchResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/documents/`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`${API_BASE_URL}/validation/mismatches`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (!docResponse.ok) throw new Error(`Unable to load documents (HTTP ${docResponse.status}). Check that the backend is running.`);
      if (!mismatchResponse.ok) throw new Error(`Unable to load validation results (HTTP ${mismatchResponse.status}).`);

      // /documents/ returns a paginated object {items:[...]} not a plain array
      const rawDoc = await docResponse.json();
      const docData: Document[] = rawDoc.items ?? rawDoc.documents ?? (Array.isArray(rawDoc) ? rawDoc : []);
      const rawMismatch = await mismatchResponse.json();
      const mismatchData: Mismatch[] = rawMismatch.items ?? rawMismatch.mismatches ?? (Array.isArray(rawMismatch) ? rawMismatch : []);

      // Enhance documents with mismatch counts
      const enhancedDocuments = docData.map((doc) => ({
        ...doc,
        mismatch_count: mismatchData.filter((m) => m.document.id === doc.id)
          .length,
        last_scanned:
          doc.last_scanned ||
          new Date(Date.now() - Math.random() * 86400000).toISOString(),
        document_type: doc.document_type || "Policy",
        file_size_kb:
          doc.file_size_kb || Math.floor(Math.random() * 1000) + 100,
      }));

      setDocuments(enhancedDocuments);
      setFilteredDocuments(enhancedDocuments);
      setMismatches(mismatchData);
    } catch (err: any) {
      // Show a clean, readable message — not a raw JS TypeError
      const raw: string = err?.message ?? String(err);
      if (raw.includes("is not a function") || raw.includes("is undefined") || raw.includes("Cannot read")) {
        setError("Unexpected data format received from the server. Please refresh the page or contact support.");
      } else if (raw.includes("NetworkError") || raw.includes("Failed to fetch")) {
        setError("Cannot connect to the backend. Make sure the server is running on port 8000.");
      } else {
        setError(raw);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const fetchSuggestions = useCallback(async (docIds: number[], currentDocs: Document[]) => {
    const token = localStorage.getItem("accessToken");
    if (!token || docIds.length === 0) return;
    try {
      const results = await Promise.all(
        docIds
          .filter((id) => !dismissedDocs.has(id))
          .map(async (docId) => {
            const res = await fetch(`${API_BASE_URL}/validation/suggest-links`, {
              method: "POST",
              headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
              body: JSON.stringify({ document_id: docId }),
            });
            if (!res.ok) return null;
            const data = await res.json();
            if (!data.suggestions?.length) return null;
            const doc = currentDocs.find((d) => d.id === docId);
            return { doc_id: docId, doc_name: doc?.filename ?? `Doc #${docId}`, items: data.suggestions } as DocSuggestions;
          })
      );
      setSuggestions(results.filter(Boolean) as DocSuggestions[]);
    } catch {
      // Non-critical, fail silently
    }
  }, [dismissedDocs]);

  const fetchAtomCounts = useCallback(async (docIds: number[]) => {
    const token = localStorage.getItem("accessToken");
    if (!token || docIds.length === 0) return;
    try {
      const results = await Promise.all(
        docIds.map(async (docId) => {
          const res = await fetch(`${API_BASE_URL}/validation/atom-count/${docId}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!res.ok) return null;
          const data = await res.json();
          return { docId, total: data.total_atoms ?? 0 };
        })
      );
      const counts: Record<number, number> = {};
      for (const r of results) {
        if (r) counts[r.docId] = r.total;
      }
      setAtomCounts((prev) => ({ ...prev, ...counts }));
    } catch {
      // Non-critical
    }
  }, []);

  // Filter documents based on search and status
  useEffect(() => {
    let filtered = documents.filter(
      (doc) =>
        doc.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.document_type?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    if (statusFilter !== "all") {
      filtered = filtered.filter((doc) => doc.status === statusFilter);
    }

    setFilteredDocuments(filtered);
  }, [documents, searchTerm, statusFilter]);

  // Document selection handlers
  const handleSelectDoc = (docId: number) => {
    const newSelection = new Set(selectedDocs);
    if (newSelection.has(docId)) {
      newSelection.delete(docId);
    } else {
      newSelection.add(docId);
    }
    setSelectedDocs(newSelection);
  };

  const handleSelectAll = () => {
    if (selectedDocs.size === filteredDocuments.length) {
      setSelectedDocs(new Set());
    } else {
      setSelectedDocs(new Set(filteredDocuments.map((doc) => doc.id)));
    }
  };

  // Run validation scan on selected documents
  const handleRunScan = async () => {
    if (selectedDocs.size === 0) {
      setError("Please select at least one document to scan.");
      return;
    }

    setIsScanning(true);
    setError(null);
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setError("Authentication token not found.");
      setIsScanning(false);
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/validation/run-scan`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(Array.from(selectedDocs)),
        }
      );

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to start validation scan.");
      }

      // BUG-01 FIX: Poll for fresh mismatches after scan completes.
      // Capture the count BEFORE the scan to detect changes (avoids stale closure).
      // Scans take 10-30s+ depending on document count and Gemini API latency.
      setActiveTab("results");
      const initialCount = mismatches.length;
      const pollForResults = async () => {
        const maxAttempts = 15;  // up to 45 seconds
        const minAttempts = 3;   // wait at least 9 seconds before early exit
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
          await new Promise((r) => setTimeout(r, 3000));
          try {
            const mismatchRes = await fetch(
              `${API_BASE_URL}/validation/mismatches`,
              { headers: { Authorization: `Bearer ${token}` } }
            );
            if (mismatchRes.ok) {
              const freshMismatches: Mismatch[] = await mismatchRes.json();
              setMismatches(freshMismatches);
              // Only stop early if results changed AND we've waited the minimum time
              if (freshMismatches.length !== initialCount && attempt >= minAttempts) {
                break;
              }
            }
          } catch {
            // Silently retry on network errors
          }
        }
        // Final full refresh to sync documents + mismatches
        await fetchData();
        // Auto-expand High severity mismatch type groups
        setExpandedMismatchTypes(new Set(["API Endpoint Missing", "Business Logic Missing", "General Consistency Check"]));
        // Fetch coverage suggestions and atom counts for scanned documents
        await fetchSuggestions(Array.from(selectedDocs), documents);
        await fetchAtomCounts(Array.from(selectedDocs));
        setIsScanning(false);
      };
      pollForResults();
    } catch (err: any) {
      setError(err.message);
      setIsScanning(false);
    }
  };

  // Utility functions
  const getSeverityBadgeVariant = (severity: Mismatch["severity"]) => {
    switch (severity) {
      case "High":
        return "destructive";
      case "Medium":
        return "default";
      case "Low":
        return "secondary";
      default:
        return "outline";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "default";
      case "processing":
        return "secondary";
      case "failed":
        return "destructive";
      default:
        return "outline";
    }
  };

  const formatFileSize = (sizeKb: number) => {
    if (sizeKb < 1024) return `${sizeKb} KB`;
    return `${(sizeKb / 1024).toFixed(1)} MB`;
  };

  const SeverityIcon = ({ severity }: { severity: Mismatch["severity"] }) => {
    switch (severity) {
      case "High":
        return <XCircle className="w-4 h-4 text-destructive" />;
      case "Medium":
        return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
      case "Low":
        return <Info className="w-4 h-4 text-blue-500" />;
      default:
        return null;
    }
  };

  // ── JIRA Validation state ──
  const [jiraRepos, setJiraRepos] = useState<Array<{ id: number; name: string }>>([]);
  const [jiraSelectedRepo, setJiraSelectedRepo] = useState<number | null>(null);
  const [jiraProjectKey, setJiraProjectKey] = useState("");
  const [jiraEpicKey, setJiraEpicKey] = useState("");
  const [jiraSprintName, setJiraSprintName] = useState("");
  const [jiraItems, setJiraItems] = useState<any[]>([]);
  const [jiraItemsLoading, setJiraItemsLoading] = useState(false);
  const [jiraScanRunning, setJiraScanRunning] = useState(false);
  const [jiraScanResults, setJiraScanResults] = useState<any | null>(null);
  const [jiraMismatches, setJiraMismatches] = useState<any[]>([]);

  const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : "";

  // Fetch repositories for JIRA validation
  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE_URL}/repositories/`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((d) => {
        const repos = d.items ?? d.repositories ?? (Array.isArray(d) ? d : []);
        setJiraRepos(repos.map((r: any) => ({ id: r.id, name: r.name || `Repo #${r.id}` })));
      })
      .catch(() => {});
  }, [token]);

  // Preview JIRA items when filters change
  const fetchJiraItems = async () => {
    if (!jiraProjectKey && !jiraEpicKey && !jiraSprintName) return;
    setJiraItemsLoading(true);
    try {
      const params = new URLSearchParams();
      if (jiraProjectKey) params.set("project_key", jiraProjectKey);
      if (jiraEpicKey) params.set("epic_key", jiraEpicKey);
      if (jiraSprintName) params.set("sprint_name", jiraSprintName);
      params.set("limit", "50");
      const resp = await fetch(`${API_BASE_URL}/integrations/jira/items?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (resp.ok) {
        const d = await resp.json();
        setJiraItems(d.items || []);
      }
    } catch {} finally {
      setJiraItemsLoading(false);
    }
  };

  const handleRunJiraScan = async () => {
    if (!jiraSelectedRepo) { setError("Please select a repository."); return; }
    if (!jiraProjectKey && !jiraEpicKey && !jiraSprintName) {
      setError("Please specify a project key, epic key, or sprint name.");
      return;
    }
    setJiraScanRunning(true);
    setError(null);
    setJiraScanResults(null);
    try {
      const body: any = { repository_id: jiraSelectedRepo };
      if (jiraProjectKey) body.project_key = jiraProjectKey;
      if (jiraEpicKey) body.epic_key = jiraEpicKey;
      if (jiraSprintName) body.sprint_name = jiraSprintName;

      const resp = await fetch(`${API_BASE_URL}/validation/run-jira-scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "JIRA validation failed.");
      }
      const result = await resp.json();
      setJiraScanResults(result.results);

      // Fetch jira-category mismatches
      const mResp = await fetch(
        `${API_BASE_URL}/validation/mismatches?limit=200`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (mResp.ok) {
        const mData = await mResp.json();
        const all = mData.items ?? mData.mismatches ?? (Array.isArray(mData) ? mData : []);
        setJiraMismatches(all.filter((m: any) => m.category === "jira_acceptance_criteria"));
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setJiraScanRunning(false);
    }
  };

  const stats = {
    totalDocuments: documents.length,
    selectedDocuments: selectedDocs.size,
    totalMismatches: mismatches.length,
    criticalMismatches: mismatches.filter((m) => m.severity === "High").length,
  };

  if (isLoading && documents.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-green-100 dark:bg-green-900 rounded-lg">
            <ShieldCheck className="w-6 h-6 text-green-600 dark:text-green-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Validation Panel</h1>
            <p className="text-muted-foreground">
              Select documents and scan for mismatches with code
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard/chat"
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-purple-600 bg-purple-50 hover:bg-purple-100 rounded-lg transition-colors"
          >
            <Sparkles className="h-4 w-4" />
            Explain mismatches
          </Link>
        <Button variant="outline" onClick={fetchData} disabled={isLoading}>
          <RefreshCw
            className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Total Documents
                </p>
                <p className="text-2xl font-bold">{stats.totalDocuments}</p>
              </div>
              <FileText className="h-8 w-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Selected
                </p>
                <p className="text-2xl font-bold">{stats.selectedDocuments}</p>
              </div>
              <Users className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Total Issues
                </p>
                <p className="text-2xl font-bold">{stats.totalMismatches}</p>
              </div>
              <AlertTriangle className="h-8 w-8 text-orange-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  High Severity
                </p>
                <p className="text-2xl font-bold text-red-600">
                  {stats.criticalMismatches}
                </p>
              </div>
              <XCircle className="h-8 w-8 text-red-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Scanning Progress */}
      {isScanning && (
        <Alert>
          <ScanLine className="h-4 w-4 animate-pulse" />
          <AlertTitle>Scanning in Progress</AlertTitle>
          <AlertDescription>
            Validating {selectedDocs.size} selected document(s). This may take a
            few moments...
          </AlertDescription>
        </Alert>
      )}

      {/* Main Content Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="space-y-4"
      >
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="select" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Select Documents
          </TabsTrigger>
          <TabsTrigger value="results" className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" />
            Validation Results
          </TabsTrigger>
          <TabsTrigger value="jira" className="flex items-center gap-2">
            <TicketCheck className="h-4 w-4" />
            JIRA Validation
          </TabsTrigger>
        </TabsList>

        {/* Document Selection Tab */}
        <TabsContent value="select" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-yellow-600" />
                Document Selection & Scanning
              </CardTitle>
              <CardDescription>
                Choose specific documents to validate. Selected documents will
                be scanned for mismatches with your codebase.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Controls */}
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="flex-1">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <Input
                      placeholder="Search documents..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline">
                      <Filter className="h-4 w-4 mr-2" />
                      Status: {statusFilter === "all" ? "All" : statusFilter}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuItem onClick={() => setStatusFilter("all")}>
                      All Statuses
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setStatusFilter("completed")}
                    >
                      Completed
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setStatusFilter("processing")}
                    >
                      Processing
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setStatusFilter("failed")}>
                      Failed
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <Button
                  onClick={handleRunScan}
                  disabled={isScanning || isLoading || selectedDocs.size === 0}
                  className="bg-green-600 hover:bg-green-700"
                >
                  {isScanning ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Zap className="h-4 w-4 mr-2" />
                  )}
                  {isScanning
                    ? "Scanning..."
                    : `Validate Selected (${selectedDocs.size})`}
                </Button>
              </div>

              {/* Documents Table */}
              <div className="border rounded-lg overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/50">
                      <TableHead className="w-[50px]">
                        <Checkbox
                          checked={
                            selectedDocs.size === filteredDocuments.length &&
                            filteredDocuments.length > 0
                          }
                          onCheckedChange={handleSelectAll}
                          aria-label="Select all documents"
                        />
                      </TableHead>
                      <TableHead>Document</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Version</TableHead>
                      <TableHead>Size</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Issues</TableHead>
                      <TableHead>Last Scan</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredDocuments.length > 0 ? (
                      filteredDocuments.map((doc) => (
                        <TableRow key={doc.id} className="hover:bg-muted/50">
                          <TableCell>
                            <Checkbox
                              checked={selectedDocs.has(doc.id)}
                              onCheckedChange={() => handleSelectDoc(doc.id)}
                              aria-label={`Select ${doc.filename}`}
                            />
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <FileText className="h-4 w-4 text-muted-foreground" />
                              <span className="font-medium">
                                {doc.filename}
                              </span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{doc.document_type}</Badge>
                          </TableCell>
                          <TableCell>{doc.version}</TableCell>
                          <TableCell>
                            {formatFileSize(doc.file_size_kb || 0)}
                          </TableCell>
                          <TableCell>
                            <Badge variant={getStatusColor(doc.status)}>
                              {doc.status}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {doc.mismatch_count ? (
                              <Badge
                                variant={
                                  doc.mismatch_count > 0
                                    ? "destructive"
                                    : "default"
                                }
                              >
                                {doc.mismatch_count} issues
                              </Badge>
                            ) : (
                              <Badge
                                variant="outline"
                                className="text-green-600"
                              >
                                No issues
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {doc.last_scanned
                              ? new Date(doc.last_scanned).toLocaleDateString()
                              : "Never"}
                          </TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={8} className="text-center h-32">
                          <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground">
                            <FileText className="h-12 w-12" />
                            <span className="font-semibold">
                              No documents found
                            </span>
                            <p className="text-sm">
                              Try adjusting your search or filter criteria
                            </p>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Validation Results Tab */}
        <TabsContent value="results" className="space-y-4">

          {/* Coverage Suggestion Banners */}
          {suggestions.map((suggestion) => (
            <div
              key={suggestion.doc_id}
              className="border border-amber-200 bg-amber-50 rounded-lg p-4 space-y-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-amber-600 shrink-0" />
                  <div>
                    <p className="font-semibold text-amber-900 text-sm">
                      Coverage Hint — {suggestion.doc_name}
                    </p>
                    <p className="text-xs text-amber-700 mt-0.5">
                      Linking {suggestion.items.length} additional file{suggestion.items.length > 1 ? "s" : ""} could improve validation coverage for this document.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setDismissedDocs((prev) => new Set(prev).add(suggestion.doc_id));
                    setSuggestions((prev) => prev.filter((s) => s.doc_id !== suggestion.doc_id));
                  }}
                  className="text-amber-500 hover:text-amber-700 text-xs shrink-0"
                >
                  Dismiss
                </button>
              </div>

              {/* Suggested file cards */}
              <div className="space-y-2">
                {suggestion.items.map((item) => (
                  <div
                    key={item.component_id}
                    className="bg-white border border-amber-100 rounded-md px-3 py-2 flex items-start justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Code className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                        <span className="text-sm font-medium text-gray-800">{item.component_name}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200 font-medium">
                          {Math.round(item.relevance_score * 100)}% relevant
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mt-1">{item.reason}</p>
                      {item.gaps_addressed?.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {item.gaps_addressed.slice(0, 3).map((gap, i) => (
                            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
                              {gap}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Link Files button */}
              <div className="flex gap-2 pt-1">
                <Button
                  size="sm"
                  className="bg-amber-600 hover:bg-amber-700 text-white h-7 text-xs"
                  onClick={() => {
                    const ids = suggestion.items.map((i) => i.component_id).join(",");
                    router.push(`/dashboard/documents?suggest_doc=${suggestion.doc_id}&suggest_files=${ids}`);
                  }}
                >
                  <LinkIcon className="h-3 w-3 mr-1.5" />
                  Link Suggested Files
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs border-amber-300 text-amber-700 hover:bg-amber-50"
                  onClick={() => {
                    setDismissedDocs((prev) => new Set(prev).add(suggestion.doc_id));
                    setSuggestions((prev) => prev.filter((s) => s.doc_id !== suggestion.doc_id));
                  }}
                >
                  Not now
                </Button>
              </div>
            </div>
          ))}

          {/* Two-sided Report Card */}
          {mismatches.length > 0 && (() => {
            const forwardMismatches = mismatches.filter((m) => m.direction !== "reverse");
            const reverseMismatches = mismatches.filter((m) => m.direction === "reverse");
            // Coverage score: how many documents have atomisation data?
            const totalAtoms = Object.values(atomCounts).reduce((s, n) => s + n, 0);
            const atomsWithGaps = new Set(
              forwardMismatches.filter((m) => m.requirement_atom_id).map((m) => m.requirement_atom_id)
            ).size;
            const coveragePct = totalAtoms > 0
              ? Math.round(((totalAtoms - atomsWithGaps) / totalAtoms) * 100)
              : null;

            return (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-2">
                {/* Developer Accountability score */}
                <div className="border border-red-200 bg-red-50 rounded-lg px-4 py-3 flex items-center gap-3">
                  <XCircle className="h-8 w-8 text-red-500 shrink-0" />
                  <div>
                    <p className="text-xs text-red-700 font-medium">Developer Gaps</p>
                    <p className="text-2xl font-bold text-red-900">{forwardMismatches.length}</p>
                    <p className="text-[10px] text-red-600">requirements not implemented</p>
                  </div>
                </div>
                {/* Coverage score */}
                {coveragePct !== null && (
                  <div className="border border-green-200 bg-green-50 rounded-lg px-4 py-3 flex items-center gap-3">
                    <CircleCheck className="h-8 w-8 text-green-500 shrink-0" />
                    <div>
                      <p className="text-xs text-green-700 font-medium">BRD Coverage</p>
                      <p className="text-2xl font-bold text-green-900">{coveragePct}%</p>
                      <p className="text-[10px] text-green-600">{totalAtoms - atomsWithGaps}/{totalAtoms} atoms satisfied</p>
                    </div>
                  </div>
                )}
                {/* BA Accountability score */}
                <div className="border border-amber-200 bg-amber-50 rounded-lg px-4 py-3 flex items-center gap-3">
                  <AlertTriangle className="h-8 w-8 text-amber-500 shrink-0" />
                  <div>
                    <p className="text-xs text-amber-700 font-medium">BRD Gaps (BA)</p>
                    <p className="text-2xl font-bold text-amber-900">{reverseMismatches.length}</p>
                    <p className="text-[10px] text-amber-600">undocumented capabilities</p>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* Report side selector */}
          {mismatches.length > 0 && (
            <div className="flex gap-2 mb-2">
              <button
                onClick={() => setReportSide("developer")}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  reportSide === "developer"
                    ? "bg-red-100 text-red-800 border border-red-300"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                Developer Accountability
                <span className="ml-2 text-xs font-bold">
                  ({mismatches.filter((m) => m.direction !== "reverse").length})
                </span>
              </button>
              <button
                onClick={() => setReportSide("ba")}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  reportSide === "ba"
                    ? "bg-amber-100 text-amber-800 border border-amber-300"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                BA Accountability
                <span className="ml-2 text-xs font-bold">
                  ({mismatches.filter((m) => m.direction === "reverse").length})
                </span>
              </button>
            </div>
          )}

          {/* Mismatch Report — Grouped by type */}
          <Card>
            <CardHeader>
              <CardTitle>
                {reportSide === "developer" ? "Developer Accountability — Requirement Gaps" : "BA Accountability — Undocumented Capabilities"}
              </CardTitle>
              <CardDescription>
                {reportSide === "developer"
                  ? (() => {
                      const fwd = mismatches.filter((m) => m.direction !== "reverse");
                      return fwd.length > 0
                        ? `${fwd.length} BRD requirement(s) not fully implemented across ${new Set(fwd.map((m) => m.mismatch_type)).size} categories.`
                        : "All documented requirements appear to be implemented.";
                    })()
                  : (() => {
                      const rev = mismatches.filter((m) => m.direction === "reverse");
                      return rev.length > 0
                        ? `${rev.length} code capability/capabilities have no corresponding BRD requirement. BA should review.`
                        : "All code capabilities have corresponding BRD requirements.";
                    })()
                }
              </CardDescription>
            </CardHeader>
            <CardContent>
              {(() => {
                const visible = reportSide === "developer"
                  ? mismatches.filter((m) => m.direction !== "reverse")
                  : mismatches.filter((m) => m.direction === "reverse");
                return visible.length === 0;
              })() ? (
                <div className="text-center py-12">
                  <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold">All Clear!</h3>
                  <p className="text-muted-foreground mt-2">
                    {reportSide === "developer"
                      ? "No validation issues found. Select documents and run a new scan to re-validate."
                      : "No undocumented capabilities found. Your BRD covers all implemented code."}
                  </p>
                </div>
              ) : (() => {
                // Filter by active report side
                const visibleMismatches = reportSide === "developer"
                  ? mismatches.filter((m) => m.direction !== "reverse")
                  : mismatches.filter((m) => m.direction === "reverse");

                // Group mismatches by type
                const grouped = new Map<string, Mismatch[]>();
                for (const m of visibleMismatches) {
                  const key = m.mismatch_type;
                  if (!grouped.has(key)) grouped.set(key, []);
                  grouped.get(key)!.push(m);
                }
                // Sort groups: most high-severity first
                const sortedGroups = [...grouped.entries()].sort(([, a], [, b]) => {
                  const highA = a.filter((m) => m.severity === "High").length;
                  const highB = b.filter((m) => m.severity === "High").length;
                  return highB - highA;
                });

                return (
                  <div className="space-y-3">
                    {sortedGroups.map(([type, items]) => {
                      const isExpanded = expandedMismatchTypes.has(type);
                      const highCount = items.filter((m) => m.severity === "High").length;
                      const medCount = items.filter((m) => m.severity === "Medium").length;
                      const lowCount = items.filter((m) => m.severity === "Low").length;

                      return (
                        <div key={type} className="border rounded-lg overflow-hidden">
                          {/* Group header */}
                          <button
                            className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 text-left"
                            onClick={() => {
                              setExpandedMismatchTypes((prev) => {
                                const next = new Set(prev);
                                next.has(type) ? next.delete(type) : next.add(type);
                                return next;
                              });
                            }}
                          >
                            <div className="flex items-center gap-3">
                              <span className="font-medium text-sm text-gray-800">
                                {type.replace(/_/g, " ")}
                              </span>
                              <div className="flex items-center gap-1.5">
                                {highCount > 0 && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-700 font-semibold">
                                    {highCount} High
                                  </span>
                                )}
                                {medCount > 0 && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-yellow-100 text-yellow-700 font-semibold">
                                    {medCount} Med
                                  </span>
                                )}
                                {lowCount > 0 && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500 font-semibold">
                                    {lowCount} Low
                                  </span>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-2 text-xs text-gray-400">
                              <span>{items.length} finding{items.length !== 1 ? "s" : ""}</span>
                              <span>{isExpanded ? "▲" : "▼"}</span>
                            </div>
                          </button>

                          {/* Findings list */}
                          {isExpanded && (
                            <div className="divide-y">
                              {items.map((mismatch) => (
                                <div key={mismatch.id} className="px-4 py-3 hover:bg-gray-50">
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="flex items-start gap-3 min-w-0 flex-1">
                                      <Badge
                                        variant={getSeverityBadgeVariant(mismatch.severity)}
                                        className="shrink-0 flex items-center gap-1 mt-0.5"
                                      >
                                        <SeverityIcon severity={mismatch.severity} />
                                        {mismatch.severity}
                                      </Badge>
                                      <div className="min-w-0">
                                        <p className="text-sm text-gray-700 leading-snug">
                                          {mismatch.description}
                                        </p>
                                        <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                                          <span className="flex items-center gap-1 text-[11px] text-gray-400">
                                            <FileText className="w-3 h-3" />
                                            {mismatch.document?.name ?? "—"}
                                          </span>
                                          <span className="flex items-center gap-1 text-[11px] text-gray-400">
                                            <Code className="w-3 h-3" />
                                            {mismatch.code_component?.name ?? "—"}
                                          </span>
                                          {mismatch.direction === "reverse" && mismatch.details?.classification && (
                                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${
                                              mismatch.details.classification === "SCOPE_CREEP"
                                                ? "bg-red-100 text-red-700"
                                                : mismatch.details.classification === "IMPLICIT_REQUIREMENT"
                                                ? "bg-blue-100 text-blue-700"
                                                : "bg-gray-100 text-gray-600"
                                            }`}>
                                              {mismatch.details.classification.replace(/_/g, " ")}
                                            </span>
                                          )}
                                          {mismatch.requirement_atom_id && (
                                            <span className="text-[10px] text-purple-600 font-mono">
                                              atom #{mismatch.requirement_atom_id}
                                            </span>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                    <Dialog>
                                      <DialogTrigger asChild>
                                        <Button variant="outline" size="sm" className="shrink-0 h-7 text-xs">
                                          <Eye className="h-3 w-3 mr-1" />
                                          Details
                                        </Button>
                                      </DialogTrigger>
                                      <DialogContent className="sm:max-w-2xl">
                                        <DialogHeader>
                                          <DialogTitle>
                                            {mismatch.mismatch_type.replace(/_/g, " ")}
                                          </DialogTitle>
                                        </DialogHeader>
                                        <div className="space-y-4 py-4 text-sm">
                                          <p><strong>Description:</strong> {mismatch.description}</p>
                                          <div className="p-4 bg-muted rounded-lg space-y-3">
                                            <div>
                                              <h4 className="font-semibold">Expected (from Document)</h4>
                                              <p className="text-muted-foreground italic mt-1">
                                                "{mismatch.details?.expected ?? "N/A"}"
                                              </p>
                                            </div>
                                            <div>
                                              <h4 className="font-semibold">Actual (in Code)</h4>
                                              <p className="text-muted-foreground italic mt-1">
                                                "{mismatch.details?.actual ?? "N/A"}"
                                              </p>
                                            </div>
                                          </div>
                                          {mismatch.details?.evidence_document && (
                                            <div>
                                              <h4 className="font-semibold">Evidence from Document</h4>
                                              <p className="text-muted-foreground text-xs mt-1 bg-blue-50 p-2 rounded">
                                                {mismatch.details.evidence_document}
                                              </p>
                                            </div>
                                          )}
                                          {mismatch.details?.evidence_code && (
                                            <div>
                                              <h4 className="font-semibold">Evidence from Code</h4>
                                              <p className="text-muted-foreground text-xs mt-1 bg-green-50 p-2 rounded font-mono">
                                                {mismatch.details.evidence_code}
                                              </p>
                                            </div>
                                          )}
                                          {mismatch.details?.suggested_action && (
                                            <div>
                                              <h4 className="font-semibold">Suggested Action</h4>
                                              <p className="text-muted-foreground mt-1">
                                                {mismatch.details.suggested_action}
                                              </p>
                                            </div>
                                          )}
                                        </div>
                                      </DialogContent>
                                    </Dialog>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </CardContent>
          </Card>
        </TabsContent>
        {/* JIRA Validation Tab */}
        <TabsContent value="jira" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TicketCheck className="h-5 w-5 text-blue-600" />
                JIRA-Aware Validation
              </CardTitle>
              <CardDescription>
                Select a JIRA scope and a code repository. The engine checks whether the code
                satisfies each acceptance criterion in the selected tickets.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Repository selector */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1.5">
                    <GitBranch className="w-3.5 h-3.5 inline mr-1" />
                    Code Repository
                  </label>
                  <select
                    value={jiraSelectedRepo ?? ""}
                    onChange={(e) => setJiraSelectedRepo(e.target.value ? Number(e.target.value) : null)}
                    className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
                  >
                    <option value="">Select repository…</option>
                    {jiraRepos.map((r) => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </select>
                </div>

                {/* Project key */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1.5">
                    Jira Project Key
                  </label>
                  <Input
                    value={jiraProjectKey}
                    onChange={(e) => setJiraProjectKey(e.target.value.toUpperCase())}
                    placeholder="e.g. PROJ"
                    className="font-mono"
                  />
                </div>

                {/* Epic key (optional) */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1.5">
                    Epic Key <span className="text-gray-400 font-normal">(optional)</span>
                  </label>
                  <Input
                    value={jiraEpicKey}
                    onChange={(e) => setJiraEpicKey(e.target.value.toUpperCase())}
                    placeholder="e.g. PROJ-42"
                    className="font-mono"
                  />
                </div>

                {/* Sprint name (optional) */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1.5">
                    Sprint Name <span className="text-gray-400 font-normal">(optional)</span>
                  </label>
                  <Input
                    value={jiraSprintName}
                    onChange={(e) => setJiraSprintName(e.target.value)}
                    placeholder="e.g. Sprint 14"
                  />
                </div>
              </div>

              {/* Preview + Run actions */}
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  className="text-xs h-8 gap-1.5"
                  onClick={fetchJiraItems}
                  disabled={jiraItemsLoading || (!jiraProjectKey && !jiraEpicKey && !jiraSprintName)}
                >
                  {jiraItemsLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                  Preview Tickets
                </Button>
                <Button
                  className="bg-green-600 hover:bg-green-700 text-xs h-8 gap-1.5"
                  disabled={jiraScanRunning || !jiraSelectedRepo || (!jiraProjectKey && !jiraEpicKey && !jiraSprintName)}
                  onClick={handleRunJiraScan}
                >
                  {jiraScanRunning ? (
                    <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Validating…</>
                  ) : (
                    <><Zap className="w-3.5 h-3.5" /> Validate against JIRA</>
                  )}
                </Button>
              </div>

              {/* Ticket preview */}
              {jiraItems.length > 0 && !jiraScanResults && (
                <div className="border rounded-lg overflow-hidden">
                  <div className="bg-gray-50 px-4 py-2 text-xs font-semibold text-gray-600 border-b">
                    {jiraItems.length} tickets in scope
                  </div>
                  <div className="divide-y max-h-48 overflow-y-auto">
                    {jiraItems.map((item) => (
                      <div key={item.id} className="flex items-center justify-between px-4 py-2.5">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-xs font-mono text-blue-600 flex-shrink-0">{item.external_key}</span>
                          <span className="text-xs text-gray-700 truncate">{item.title}</span>
                        </div>
                        <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                          <Badge variant="outline" className="text-xs">{item.item_type}</Badge>
                          {item.has_acceptance_criteria && (
                            <Badge className="bg-green-100 text-green-700 text-xs">AC</Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Scan results summary */}
              {jiraScanResults && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                      { label: "Checked", value: jiraScanResults.checked ?? 0, color: "text-gray-800", icon: <TicketCheck className="w-5 h-5 text-gray-500" /> },
                      { label: "Satisfied", value: jiraScanResults.satisfied ?? 0, color: "text-green-700", icon: <CircleCheck className="w-5 h-5 text-green-500" /> },
                      { label: "Partial", value: jiraScanResults.partial ?? 0, color: "text-yellow-700", icon: <CircleDot className="w-5 h-5 text-yellow-500" /> },
                      { label: "Missing", value: jiraScanResults.missing ?? 0, color: "text-red-700", icon: <CircleX className="w-5 h-5 text-red-500" /> },
                    ].map((s) => (
                      <div key={s.label} className="bg-white border rounded-lg p-3 flex items-center gap-3">
                        {s.icon}
                        <div>
                          <p className="text-xs text-gray-500">{s.label}</p>
                          <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Per-criterion results */}
                  {jiraMismatches.length > 0 && (
                    <div className="border rounded-lg overflow-hidden">
                      <div className="bg-gray-50 px-4 py-2 text-xs font-semibold text-gray-600 border-b">
                        Acceptance Criteria Results
                      </div>
                      <div className="divide-y max-h-80 overflow-y-auto">
                        {jiraMismatches.map((m: any) => {
                          const details = m.details || {};
                          const verdict = details.verdict || (m.status === "resolved" ? "satisfied" : "missing");
                          const verdictColors: Record<string, string> = {
                            satisfied: "bg-green-100 text-green-700",
                            partial: "bg-yellow-100 text-yellow-700",
                            missing: "bg-red-100 text-red-700",
                          };
                          const VIcon = verdict === "satisfied" ? CircleCheck : verdict === "partial" ? CircleDot : CircleX;
                          return (
                            <div key={m.id} className="px-4 py-3">
                              <div className="flex items-start justify-between gap-3">
                                <div className="flex items-start gap-2 min-w-0">
                                  <VIcon className={`w-4 h-4 flex-shrink-0 mt-0.5 ${
                                    verdict === "satisfied" ? "text-green-500" :
                                    verdict === "partial" ? "text-yellow-500" : "text-red-500"
                                  }`} />
                                  <div className="min-w-0">
                                    {details.jira_key && (
                                      <span className="text-xs font-mono text-blue-600 mr-2">{details.jira_key}</span>
                                    )}
                                    <p className="text-xs text-gray-700">{details.criterion || m.description}</p>
                                    {details.evidence && (
                                      <p className="text-xs text-gray-400 mt-1 italic">{details.evidence}</p>
                                    )}
                                  </div>
                                </div>
                                <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${verdictColors[verdict] || "bg-gray-100 text-gray-600"}`}>
                                  {verdict}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
