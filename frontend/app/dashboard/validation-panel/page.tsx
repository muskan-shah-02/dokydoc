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

import { MismatchFeedback } from "@/components/feedback/MismatchFeedback";
import { MismatchSuggestedFix } from "@/components/validation/MismatchSuggestedFix";
import { MismatchClarificationPanel } from "@/components/validation/MismatchClarificationPanel";
import { ComplianceTrendChart } from "@/components/validation/ComplianceTrendChart";
import { TestSuiteDownload } from "@/components/validation/TestSuiteDownload";
import { UATChecklist } from "@/components/validation/UATChecklist";

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
  training_example_id?: number | null;  // Phase 1: Data Flywheel
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

// --- Phase 5B Interfaces ---
interface ComplianceData {
  document_id: number;
  overall_score: number;
  weighted_score: number;
  grade: string;
  by_type: Record<string, { weight: number; covered: number; total: number; score: number }>;
  total_atoms: number;
  covered_atoms: number;
}

interface EvidenceData {
  mismatch_id: number;
  brd_requirement: { atom_id: number; atom_type: string; content: string; regulatory_tags: string[] };
  code_analyzed: { component_id: number; component_name: string; snippet: string };
  ai_conclusion: { verdict: string; confidence: string; confidence_reasoning: string; evidence: string };
}

interface CoverageMatrixData {
  document_id: number;
  atoms: Array<{ id: number; atom_type: string; content: string }>;
  components: Array<{ id: number; name: string }>;
  matrix: Record<string, string>;
  summary: { total_cells: number; covered: number; partial: number; missing: number; not_linked: number };
}

const VALID_TRANSITIONS: Record<string, string[]> = {
  new: ["open", "in_progress", "false_positive"],
  open: ["in_progress", "resolved", "false_positive", "auto_closed"],
  in_progress: ["open", "resolved", "false_positive"],
  resolved: ["verified", "open"],
  verified: ["open"],
  false_positive: ["disputed", "open"],
  disputed: ["open", "false_positive"],
  auto_closed: ["open"],
};

const STATUS_COLORS: Record<string, string> = {
  open: "bg-red-100 text-red-700",
  in_progress: "bg-yellow-100 text-yellow-700",
  resolved: "bg-green-100 text-green-700",
  verified: "bg-blue-100 text-blue-700",
  false_positive: "bg-gray-100 text-gray-500",
  disputed: "bg-orange-100 text-orange-700",
  auto_closed: "bg-slate-100 text-slate-500",
  new: "bg-red-100 text-red-700",
};

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

  // Phase 5B state
  const [focusedDocId, setFocusedDocId] = useState<number | null>(null);
  const [complianceData, setComplianceData] = useState<ComplianceData | null>(null);
  const [atomDiffSummary, setAtomDiffSummary] = useState<Record<string, number> | null>(null);
  const [coverageMatrix, setCoverageMatrix] = useState<CoverageMatrixData | null>(null);
  const [coverageMatrixDocId, setCoverageMatrixDocId] = useState<number | null>(null);
  const [coverageMatrixLoading, setCoverageMatrixLoading] = useState(false); // ARC-FE-04
  const [evidenceMap, setEvidenceMap] = useState<Record<number, EvidenceData>>({});
  const [expandedEvidence, setExpandedEvidence] = useState<Set<number>>(new Set());
  const [fpModal, setFpModal] = useState<{ open: boolean; mismatchId: number | null }>({ open: false, mismatchId: null });
  const [fpReason, setFpReason] = useState("");
  const [fpSubmitting, setFpSubmitting] = useState(false);
  const [statusUpdating, setStatusUpdating] = useState<number | null>(null);
  const [signOffNotes, setSignOffNotes] = useState("");
  const [signOffSubmitting, setSignOffSubmitting] = useState(false);
  const [signOffResult, setSignOffResult] = useState<{ sign_off_id: number; certificate_id: string; certificate_hash: string; message: string } | null>(null);
  const [signOffHistory, setSignOffHistory] = useState<any[]>([]);

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

  // Phase 5B: fetch compliance score for a document
  const fetchComplianceData = useCallback(async (docId: number) => {
    const tok = localStorage.getItem("accessToken");
    if (!tok) return;
    try {
      const res = await fetch(`${API_BASE_URL}/validation/${docId}/compliance-score`, {
        headers: { Authorization: `Bearer ${tok}` },
      });
      if (res.ok) setComplianceData(await res.json());
      // ARC-FE-01: surface non-2xx compliance errors as inline warning
      else if (res.status !== 404) setError(`Compliance score unavailable (HTTP ${res.status})`);
    } catch (e: any) { console.warn("[fetchComplianceData]", e?.message); }
  }, []);

  // Phase 5B: fetch atom diff summary for a document
  const fetchAtomDiff = useCallback(async (docId: number) => {
    const tok = localStorage.getItem("accessToken");
    if (!tok) return;
    try {
      const res = await fetch(`${API_BASE_URL}/documents/${docId}/atom-diff`, {
        headers: { Authorization: `Bearer ${tok}` },
      });
      if (res.ok) {
        const data = await res.json();
        if (data.atom_diff) setAtomDiffSummary(data.atom_diff);
      }
    } catch (e: any) { console.warn("[fetchAtomDiff]", e?.message); }
  }, []);

  // Phase 5B: fetch coverage matrix for a document
  const fetchCoverageMatrix = useCallback(async (docId: number) => {
    const tok = localStorage.getItem("accessToken");
    if (!tok) return;
    setCoverageMatrixDocId(docId);
    setCoverageMatrix(null);
    setCoverageMatrixLoading(true); // ARC-FE-04
    try {
      const res = await fetch(`${API_BASE_URL}/validation/${docId}/coverage-matrix`, {
        headers: { Authorization: `Bearer ${tok}` },
      });
      // ARC-FE-01: surface coverage matrix errors
      if (res.ok) setCoverageMatrix(await res.json());
      else setError(`Coverage matrix unavailable (HTTP ${res.status})`);
    } catch (e: any) {
      console.warn("[fetchCoverageMatrix]", e?.message);
      setError("Coverage matrix failed to load. Check your connection.");
    } finally {
      setCoverageMatrixLoading(false); // ARC-FE-04
    }
  }, []);

  // Phase 5B: fetch evidence for a mismatch
  const fetchEvidence = useCallback(async (mismatchId: number) => {
    if (evidenceMap[mismatchId]) return; // already loaded
    const tok = localStorage.getItem("accessToken");
    if (!tok) return;
    try {
      const res = await fetch(`${API_BASE_URL}/validation/mismatches/${mismatchId}/evidence`, {
        headers: { Authorization: `Bearer ${tok}` },
      });
      if (res.ok) {
        const data: EvidenceData = await res.json();
        setEvidenceMap((prev) => ({ ...prev, [mismatchId]: data }));
      }
      // ARC-FE-01: surface evidence errors inline
      else setEvidenceMap((prev) => ({ ...prev, [mismatchId]: { error: `Evidence unavailable (HTTP ${res.status})` } as any }));
    } catch (e: any) {
      console.warn("[fetchEvidence]", e?.message);
      setEvidenceMap((prev) => ({ ...prev, [mismatchId]: { error: "Evidence failed to load." } as any }));
    }
  }, [evidenceMap]);

  const toggleEvidence = (mismatchId: number) => {
    setExpandedEvidence((prev) => {
      const next = new Set(prev);
      if (next.has(mismatchId)) {
        next.delete(mismatchId);
      } else {
        next.add(mismatchId);
        fetchEvidence(mismatchId);
      }
      return next;
    });
  };

  // Phase 5B: mark mismatch as false positive
  const handleFalsePositive = async () => {
    if (!fpModal.mismatchId || fpReason.length < 10) return;
    setFpSubmitting(true);
    const tok = localStorage.getItem("accessToken");
    try {
      const res = await fetch(`${API_BASE_URL}/validation/mismatches/${fpModal.mismatchId}/false-positive`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify({ reason: fpReason }),
      });
      if (res.ok) {
        setFpModal({ open: false, mismatchId: null });
        setFpReason("");
        await fetchData();
      } else {
        const e = await res.json();
        setError(e.detail || "Failed to mark as false positive.");
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setFpSubmitting(false);
    }
  };

  // Phase 5B: update mismatch status
  const handleStatusUpdate = async (mismatchId: number, newStatus: string) => {
    setStatusUpdating(mismatchId);
    const tok = localStorage.getItem("accessToken");
    // ARC-FE-03: capture previous status for rollback on error
    const previousStatus = mismatches.find((m) => m.id === mismatchId)?.status ?? "open";
    // Optimistic update — UI reflects change immediately
    setMismatches((prev) => prev.map((m) => m.id === mismatchId ? { ...m, status: newStatus } : m));
    try {
      const res = await fetch(`${API_BASE_URL}/validation/mismatches/${mismatchId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify({ new_status: newStatus }),
      });
      if (res.ok) {
        // Already updated optimistically — sync server response fields
        const data = await res.json();
        setMismatches((prev) => prev.map((m) => m.id === mismatchId ? { ...m, status: data.status ?? newStatus } : m));
      } else {
        // ARC-FE-03: revert to previous status on server rejection
        setMismatches((prev) => prev.map((m) => m.id === mismatchId ? { ...m, status: previousStatus } : m));
        const e = await res.json();
        setError(e.detail || "Failed to update status.");
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStatusUpdating(null);
    }
  };

  // Phase 5B: BA sign-off
  const handleSignOff = async () => {
    if (!focusedDocId) return;
    setSignOffSubmitting(true);
    const tok = localStorage.getItem("accessToken");
    try {
      const res = await fetch(`${API_BASE_URL}/validation/${focusedDocId}/sign-off`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify({ notes: signOffNotes, acknowledge_critical: true }),
      });
      if (res.ok) {
        const data = await res.json();
        setSignOffResult(data);
        // Refresh history
        const histRes = await fetch(`${API_BASE_URL}/validation/${focusedDocId}/sign-off-history`, {
          headers: { Authorization: `Bearer ${tok}` },
        });
        if (histRes.ok) {
          const h = await histRes.json();
          setSignOffHistory(h.sign_offs || []);
        }
      } else {
        const e = await res.json();
        setError(e.detail || "Sign-off failed.");
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSignOffSubmitting(false);
    }
  };

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
        // ARC-FE-05: hard cap prevents infinite poll if scan hangs permanently
        const MAX_ATTEMPTS = 40; // 40 × 3s = 2 minutes maximum
        const minAttempts = 3;   // wait at least 9 seconds before early exit
        let networkErrors = 0;
        for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
          await new Promise((r) => setTimeout(r, 3000));
          try {
            const mismatchRes = await fetch(
              `${API_BASE_URL}/validation/mismatches`,
              { headers: { Authorization: `Bearer ${token}` } }
            );
            if (mismatchRes.ok) {
              networkErrors = 0;
              const freshMismatches: Mismatch[] = await mismatchRes.json();
              setMismatches(freshMismatches);
              // Only stop early if results changed AND we've waited the minimum time
              if (freshMismatches.length !== initialCount && attempt >= minAttempts) {
                break;
              }
            }
          } catch {
            // ARC-FE-05: abort after 5 consecutive network errors
            if (++networkErrors >= 5) {
              setError("Scan polling stopped — too many network errors. Refresh to see results.");
              break;
            }
          }
        }
        // ARC-FE-05: notify user if scan is still not done after max wait
        if (isScanning) {
          setError("The scan is taking longer than expected. Refresh the page to check results.");
        }
        // Final full refresh to sync documents + mismatches
        await fetchData();
        // Auto-expand High severity mismatch type groups
        setExpandedMismatchTypes(new Set(["API Endpoint Missing", "Business Logic Missing", "General Consistency Check"]));
        // Fetch coverage suggestions and atom counts for scanned documents
        await fetchSuggestions(Array.from(selectedDocs), documents);
        await fetchAtomCounts(Array.from(selectedDocs));
        // Phase 5B: load compliance + atom-diff for first selected doc
        const firstDocId = Array.from(selectedDocs)[0];
        if (firstDocId) {
          setFocusedDocId(firstDocId);
          await fetchComplianceData(firstDocId);
          await fetchAtomDiff(firstDocId);
        }
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
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="select" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Select Documents
          </TabsTrigger>
          <TabsTrigger value="results" className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" />
            Validation Results
          </TabsTrigger>
          <TabsTrigger value="matrix" className="flex items-center gap-2" onClick={() => { if (focusedDocId) fetchCoverageMatrix(focusedDocId); }}>
            <Code className="h-4 w-4" />
            Coverage Matrix
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

          {/* P5B-01: Atom Diff Banner */}
          {atomDiffSummary && (atomDiffSummary.added > 0 || atomDiffSummary.modified > 0 || atomDiffSummary.deleted > 0) && (
            <div className="flex items-center justify-between border border-amber-300 bg-amber-50 rounded-lg px-4 py-3">
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-amber-600 shrink-0" />
                <span className="text-sm font-medium text-amber-900">BRD Updated —</span>
                {atomDiffSummary.added > 0 && <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-semibold">{atomDiffSummary.added} new</span>}
                {atomDiffSummary.modified > 0 && <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700 font-semibold">{atomDiffSummary.modified} changed</span>}
                {atomDiffSummary.deleted > 0 && <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-semibold">{atomDiffSummary.deleted} removed</span>}
                <span className="text-xs text-amber-600">Requirements since last scan. Re-validate to get fresh results.</span>
              </div>
              <button onClick={() => setAtomDiffSummary(null)} className="text-amber-400 hover:text-amber-600 text-xs ml-4">✕</button>
            </div>
          )}

          {/* P5B-02: Compliance Score Card */}
          {complianceData && (
            <Card className="border-l-4 border-l-blue-500">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className={`text-3xl font-black ${complianceData.grade === "A" ? "text-green-600" : complianceData.grade === "B" ? "text-blue-600" : complianceData.grade === "C" ? "text-yellow-600" : "text-red-600"}`}>
                      {complianceData.grade}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-800">Compliance Score</p>
                      <p className="text-2xl font-bold text-gray-900">{Math.round(complianceData.overall_score)}%</p>
                    </div>
                  </div>
                  <div className="text-right text-xs text-muted-foreground">
                    <p>{complianceData.covered_atoms}/{complianceData.total_atoms} atoms covered</p>
                    <p>Weighted: {Math.round(complianceData.weighted_score)}%</p>
                  </div>
                </div>
                {/* Per-type breakdown bars */}
                <div className="space-y-1.5">
                  {Object.entries(complianceData.by_type).map(([atomType, data]) => (
                    <div key={atomType} className="flex items-center gap-2">
                      <span className="text-[10px] text-gray-500 w-32 shrink-0">{atomType.replace(/_/g, " ")}</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                        <div
                          className={`h-1.5 rounded-full ${data.score >= 80 ? "bg-green-500" : data.score >= 60 ? "bg-yellow-500" : "bg-red-500"}`}
                          style={{ width: `${Math.round(data.score)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-gray-600 w-8 text-right">{Math.round(data.score)}%</span>
                      {data.weight > 1 && <span className="text-[9px] px-1 py-0.5 bg-purple-100 text-purple-600 rounded font-semibold">{data.weight}×</span>}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* P5B-02: Document selector for compliance/sign-off when no scan run yet */}
          {!complianceData && documents.length > 0 && (
            <div className="flex items-center gap-3 p-3 border border-dashed rounded-lg">
              <ShieldCheck className="h-4 w-4 text-muted-foreground shrink-0" />
              <span className="text-sm text-muted-foreground">View compliance score for:</span>
              <select
                className="text-sm border border-gray-200 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={focusedDocId ?? ""}
                onChange={(e) => {
                  const id = Number(e.target.value);
                  setFocusedDocId(id);
                  fetchComplianceData(id);
                  fetchAtomDiff(id);
                }}
              >
                <option value="">Select document…</option>
                {documents.map((d) => <option key={d.id} value={d.id}>{d.filename}</option>)}
              </select>
            </div>
          )}

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
                                <div key={mismatch.id} className="px-4 py-3 hover:bg-gray-50 space-y-2">
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
                                    <div className="flex flex-col items-end gap-1.5 shrink-0">
                                      {/* P5B-10: Status lifecycle badge */}
                                      <DropdownMenu>
                                        <DropdownMenuTrigger asChild>
                                          <button
                                            className={`text-[10px] px-2 py-0.5 rounded-full font-semibold cursor-pointer ${STATUS_COLORS[mismatch.status] ?? "bg-gray-100 text-gray-600"}`}
                                            disabled={statusUpdating === mismatch.id}
                                          >
                                            {statusUpdating === mismatch.id ? "…" : (mismatch.status ?? "open").replace(/_/g, " ")}
                                          </button>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end">
                                          {(VALID_TRANSITIONS[mismatch.status ?? "open"] ?? []).map((s) => (
                                            <DropdownMenuItem key={s} onClick={() => handleStatusUpdate(mismatch.id, s)}>
                                              {s.replace(/_/g, " ")}
                                            </DropdownMenuItem>
                                          ))}
                                        </DropdownMenuContent>
                                      </DropdownMenu>

                                      <div className="flex items-center gap-1">
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
                                    {/* P5B-04: False Positive button */}
                                    {mismatch.status !== "false_positive" && (
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-7 text-xs text-gray-400 hover:text-orange-600"
                                        onClick={() => { setFpModal({ open: true, mismatchId: mismatch.id }); setFpReason(""); }}
                                      >
                                        Not Real
                                      </Button>
                                    )}
                                    </div>
                                    {/* Phase 1: Data Flywheel feedback buttons */}
                                    <MismatchFeedback
                                      mismatchId={mismatch.id}
                                      trainingExampleId={mismatch.training_example_id}
                                    />
                                    {/* P5B-05: Evidence toggle */}
                                    <button
                                      onClick={() => toggleEvidence(mismatch.id)}
                                      className="text-[10px] text-blue-500 hover:text-blue-700 underline"
                                    >
                                      {expandedEvidence.has(mismatch.id) ? "Hide Evidence" : "Show Evidence"}
                                    </button>
                                    </div>
                                  </div>
                                  {/* P5B-05: Evidence panel */}
                                  {expandedEvidence.has(mismatch.id) && (
                                    <div className="mt-1 ml-2 border border-blue-100 bg-blue-50 rounded-lg p-3 text-xs space-y-2">
                                      {!evidenceMap[mismatch.id] ? (
                                        <div className="flex items-center gap-2 text-blue-500">
                                          <Loader2 className="w-3 h-3 animate-spin" /> Loading evidence…
                                        </div>
                                      ) : (
                                        <>
                                          <div>
                                            <p className="font-semibold text-blue-800 mb-1">BRD Requirement</p>
                                            <p className="text-gray-700 italic">"{evidenceMap[mismatch.id].brd_requirement?.content}"</p>
                                            {evidenceMap[mismatch.id].brd_requirement?.regulatory_tags?.length > 0 && (
                                              <div className="flex gap-1 mt-1 flex-wrap">
                                                {evidenceMap[mismatch.id].brd_requirement.regulatory_tags.map((t) => (
                                                  <span key={t} className="px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded text-[9px] font-semibold">{t}</span>
                                                ))}
                                              </div>
                                            )}
                                          </div>
                                          {evidenceMap[mismatch.id].code_analyzed?.snippet && (
                                            <div>
                                              <p className="font-semibold text-blue-800 mb-1">Code Analyzed</p>
                                              <pre className="text-[10px] bg-white border border-blue-100 rounded p-2 overflow-x-auto text-gray-600">{evidenceMap[mismatch.id].code_analyzed.snippet}</pre>
                                            </div>
                                          )}
                                          {evidenceMap[mismatch.id].ai_conclusion?.evidence && (
                                            <div>
                                              <p className="font-semibold text-blue-800 mb-1">AI Reasoning</p>
                                              <p className="text-gray-600">{evidenceMap[mismatch.id].ai_conclusion.evidence}</p>
                                              {evidenceMap[mismatch.id].ai_conclusion.confidence_reasoning && (
                                                <p className="text-gray-400 mt-1 italic">{evidenceMap[mismatch.id].ai_conclusion.confidence_reasoning}</p>
                                              )}
                                            </div>
                                          )}
                                        </>
                                      )}
                                    </div>
                                  )}
                                  {/* P5C-07: AI Suggested Fix */}
                                  <MismatchSuggestedFix mismatchId={mismatch.id} />
                                  {/* P5C-03: Clarification Thread */}
                                  <MismatchClarificationPanel mismatchId={mismatch.id} />
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
          {/* P5C-08: Compliance Trend Chart */}
          {focusedDocId && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Compliance Trend</CardTitle>
              </CardHeader>
              <CardContent>
                <ComplianceTrendChart documentId={focusedDocId} />
              </CardContent>
            </Card>
          )}
          {/* P5C-04: UAT Checklist */}
          {focusedDocId && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">UAT Checklist</CardTitle>
              </CardHeader>
              <CardContent>
                <UATChecklist documentId={focusedDocId} />
              </CardContent>
            </Card>
          )}
          {/* P5C-05: Test Suite Download */}
          {focusedDocId && (
            <div className="flex justify-end">
              <TestSuiteDownload documentId={focusedDocId} />
            </div>
          )}
          {/* P5B-12: BA Sign-Off Panel */}
          {focusedDocId && (
            <Card className="border-t-4 border-t-green-500">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <CircleCheck className="h-5 w-5 text-green-600" />
                  BA Sign-Off — Document #{focusedDocId}
                </CardTitle>
                <CardDescription>
                  Formally acknowledge the validation state and generate a tamper-evident compliance certificate.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {signOffResult ? (
                  <div className="border border-green-200 bg-green-50 rounded-lg p-4 space-y-2">
                    <div className="flex items-center gap-2">
                      <CircleCheck className="h-5 w-5 text-green-600" />
                      <span className="font-semibold text-green-800">Sign-Off Completed</span>
                    </div>
                    <p className="text-sm text-green-700">{signOffResult.message}</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      <div className="bg-white border border-green-100 rounded p-2">
                        <p className="text-gray-500 font-medium">Certificate ID</p>
                        <p className="font-mono text-green-800 font-bold">{signOffResult.certificate_id}</p>
                      </div>
                      <div className="bg-white border border-green-100 rounded p-2">
                        <p className="text-gray-500 font-medium">Certificate Hash (SHA-256)</p>
                        <p className="font-mono text-gray-600 break-all text-[10px]">{signOffResult.certificate_hash}</p>
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs h-7 border-green-300 text-green-700"
                      onClick={() => setSignOffResult(null)}
                    >
                      New Sign-Off
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div>
                      <label className="text-xs font-medium text-gray-600 block mb-1">Sign-Off Notes (optional)</label>
                      <textarea
                        value={signOffNotes}
                        onChange={(e) => setSignOffNotes(e.target.value)}
                        placeholder="e.g. Reviewed all high-severity mismatches. Accepted risk on PROJ-42..."
                        className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 h-20 resize-none focus:outline-none focus:ring-2 focus:ring-green-400"
                      />
                    </div>
                    {complianceData && (
                      <div className="flex items-center gap-3 text-xs text-gray-600 bg-gray-50 rounded p-2">
                        <span>Current compliance: <strong>{Math.round(complianceData.overall_score)}% ({complianceData.grade})</strong></span>
                        <span>•</span>
                        <span>Open mismatches: <strong>{mismatches.filter((m) => m.status === "open" || m.status === "in_progress").length}</strong></span>
                        <span>•</span>
                        <span>High severity: <strong className="text-red-600">{mismatches.filter((m) => m.severity === "High" && m.status !== "resolved" && m.status !== "false_positive").length}</strong></span>
                      </div>
                    )}
                    <Button
                      onClick={handleSignOff}
                      disabled={signOffSubmitting}
                      className="bg-green-600 hover:bg-green-700 text-sm"
                    >
                      {signOffSubmitting ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Generating Certificate…</> : <><CircleCheck className="h-4 w-4 mr-2" />Sign Off & Generate Certificate</>}
                    </Button>
                    {signOffHistory.length > 0 && (
                      <div className="text-xs text-gray-500">
                        Last sign-off: {new Date(signOffHistory[0].signed_at).toLocaleString()} by user #{signOffHistory[0].signed_by_user_id} — cert {signOffHistory[0].certificate_id ?? "—"}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* P5B-07: Coverage Matrix Tab */}
        <TabsContent value="matrix" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Code className="h-5 w-5 text-purple-600" />
                Coverage Matrix
              </CardTitle>
              <CardDescription>
                BRD requirements × code components — see which atoms are covered, partially covered, or missing.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Document selector */}
              <div className="flex items-center gap-3">
                <label className="text-sm font-medium text-gray-600">Document:</label>
                <select
                  className="text-sm border border-gray-200 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-purple-400"
                  value={coverageMatrixDocId ?? ""}
                  onChange={(e) => {
                    const id = Number(e.target.value);
                    if (id) fetchCoverageMatrix(id);
                  }}
                >
                  <option value="">Select document…</option>
                  {documents.map((d) => <option key={d.id} value={d.id}>{d.filename}</option>)}
                </select>
                {/* ARC-FE-04: distinct loading vs empty states */}
                {coverageMatrixLoading && (
                  <div className="flex items-center gap-2 text-purple-600 text-sm">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Loading matrix…</span>
                  </div>
                )}
                {coverageMatrixDocId && !coverageMatrixLoading && !coverageMatrix && (
                  <p className="text-xs text-gray-400 italic">No coverage data yet — click a document to load.</p>
                )}
              </div>

              {coverageMatrix && (
                <>
                  {/* Summary pills */}
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: "Covered", value: coverageMatrix.summary.covered, color: "bg-green-100 text-green-700" },
                      { label: "Partial", value: coverageMatrix.summary.partial, color: "bg-yellow-100 text-yellow-700" },
                      { label: "Missing", value: coverageMatrix.summary.missing, color: "bg-red-100 text-red-700" },
                      { label: "Not Linked", value: coverageMatrix.summary.not_linked, color: "bg-gray-100 text-gray-500" },
                    ].map((s) => (
                      <span key={s.label} className={`px-3 py-1 rounded-full text-xs font-semibold ${s.color}`}>
                        {s.label}: {s.value}
                      </span>
                    ))}
                  </div>

                  {/* Matrix grid — scrollable */}
                  {coverageMatrix.atoms.length > 0 && coverageMatrix.components.length > 0 ? (
                    <div className="overflow-auto max-h-[500px] border rounded-lg">
                      <table className="text-xs w-full">
                        <thead className="sticky top-0 bg-white shadow-sm">
                          <tr>
                            <th className="text-left px-3 py-2 text-gray-600 font-semibold border-b w-48 min-w-[12rem]">Requirement Atom</th>
                            {coverageMatrix.components.map((c) => (
                              <th key={c.id} className="px-2 py-2 text-gray-500 font-medium border-b border-l text-center max-w-[100px]">
                                <span className="block truncate" title={c.name}>{c.name.split("/").pop()}</span>
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {coverageMatrix.atoms.map((atom, i) => (
                            <tr key={atom.id} className={i % 2 === 0 ? "bg-gray-50" : "bg-white"}>
                              <td className="px-3 py-2 border-b text-gray-700 font-medium truncate max-w-[12rem]" title={atom.content}>
                                <span className="text-[9px] text-purple-500 font-mono mr-1">{atom.atom_type.slice(0, 3)}</span>
                                {atom.content.substring(0, 50)}{atom.content.length > 50 ? "…" : ""}
                              </td>
                              {coverageMatrix.components.map((c) => {
                                const key = `${atom.id}::${c.id}`;
                                const status = coverageMatrix.matrix[key] ?? "not_linked";
                                const cellColors: Record<string, string> = {
                                  covered: "bg-green-100 text-green-700",
                                  partial: "bg-yellow-100 text-yellow-700",
                                  missing: "bg-red-100 text-red-600",
                                  not_linked: "bg-gray-50 text-gray-300",
                                };
                                const cellIcons: Record<string, string> = { covered: "✓", partial: "~", missing: "✗", not_linked: "·" };
                                return (
                                  <td key={c.id} className={`border-b border-l text-center py-1 ${cellColors[status]}`} title={`${atom.content.substring(0, 40)} × ${c.name}: ${status}`}>
                                    {cellIcons[status] ?? "?"}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <p>No atoms or components linked to this document yet.</p>
                      <p className="text-sm mt-1">Run a validation scan first to populate the matrix.</p>
                    </div>
                  )}
                </>
              )}

              {!coverageMatrixDocId && (
                <div className="text-center py-12 text-muted-foreground">
                  <Code className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p>Select a document above to view its coverage matrix.</p>
                </div>
              )}
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

      {/* P5B-04: False Positive Modal */}
      {fpModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full mx-4 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-gray-800">Mark as False Positive</h2>
              <button onClick={() => setFpModal({ open: false, mismatchId: null })} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <p className="text-sm text-gray-600">
              Explain why this finding is not a real issue. This helps train the AI to avoid similar false positives.
            </p>
            <div>
              <textarea
                value={fpReason}
                onChange={(e) => setFpReason(e.target.value)}
                placeholder="Reason (minimum 10 characters)…"
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 h-24 resize-none focus:outline-none focus:ring-2 focus:ring-orange-400"
              />
              <p className={`text-xs mt-1 ${fpReason.length < 10 ? "text-red-400" : "text-green-500"}`}>
                {fpReason.length}/10 minimum characters
              </p>
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" size="sm" onClick={() => setFpModal({ open: false, mismatchId: null })}>
                Cancel
              </Button>
              <Button
                size="sm"
                className="bg-orange-600 hover:bg-orange-700"
                disabled={fpReason.length < 10 || fpSubmitting}
                onClick={handleFalsePositive}
              >
                {fpSubmitting ? <><Loader2 className="h-3 w-3 mr-1 animate-spin" />Submitting…</> : "Mark False Positive"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
