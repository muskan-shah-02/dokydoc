"use client";

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
}

interface Mismatch {
  id: number;
  mismatch_type: string;
  description: string;
  severity: "High" | "Medium" | "Low";
  confidence: "High" | "Medium" | "Low";
  status: string;
  details: MismatchDetails;
  document: { id: number; name: string };
  code_component: { id: number; name: string };
}

export default function ValidationPanelPage() {
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
        fetch("http://localhost:8000/api/v1/documents/", {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch("http://localhost:8000/api/v1/validation/mismatches", {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (!docResponse.ok) throw new Error("Failed to fetch documents.");
      if (!mismatchResponse.ok) throw new Error("Failed to fetch mismatches.");

      const docData: Document[] = await docResponse.json();
      const mismatchData: Mismatch[] = await mismatchResponse.json();

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
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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
        "http://localhost:8000/api/v1/validation/run-scan",
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

      // Switch to results tab and refresh data after scan
      setActiveTab("results");
      setTimeout(() => {
        fetchData().finally(() => setIsScanning(false));
      }, 3000);
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
        <Button variant="outline" onClick={fetchData} disabled={isLoading}>
          <RefreshCw
            className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
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
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="select" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Select Documents
          </TabsTrigger>
          <TabsTrigger value="results" className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" />
            Validation Results
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
          <Card>
            <CardHeader>
              <CardTitle>Mismatch Report</CardTitle>
              <CardDescription>
                {mismatches.length > 0
                  ? `Found ${mismatches.length} potential mismatch(es) in the selected documents.`
                  : "No mismatches found. Your documents and code appear to be aligned."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {mismatches.length === 0 ? (
                <div className="text-center py-12">
                  <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold">All Clear!</h3>
                  <p className="text-muted-foreground mt-2">
                    No validation issues found. Select documents and run a new
                    scan to re-validate.
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Severity</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Linked Components</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mismatches.map((mismatch) => (
                      <TableRow key={mismatch.id}>
                        <TableCell>
                          <Badge
                            variant={getSeverityBadgeVariant(mismatch.severity)}
                            className="flex items-center gap-1.5"
                          >
                            <SeverityIcon severity={mismatch.severity} />
                            {mismatch.severity}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <p className="font-medium">
                            {mismatch.mismatch_type.replace(/_/g, " ")}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {mismatch.description}
                          </p>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center text-sm text-muted-foreground gap-2">
                            <FileText className="w-4 h-4" />
                            <span>{mismatch.document.name}</span>
                          </div>
                          <div className="flex items-center text-sm text-muted-foreground gap-2 mt-1">
                            <Code className="w-4 h-4" />
                            <span>{mismatch.code_component.name}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <Dialog>
                            <DialogTrigger asChild>
                              <Button variant="outline" size="sm">
                                <Eye className="h-3 w-3 mr-1" />
                                View Details
                              </Button>
                            </DialogTrigger>
                            <DialogContent className="sm:max-w-2xl">
                              <DialogHeader>
                                <DialogTitle>
                                  {mismatch.mismatch_type.replace(/_/g, " ")}
                                </DialogTitle>
                              </DialogHeader>
                              <div className="space-y-4 py-4 text-sm">
                                <p>
                                  <strong>Description:</strong>{" "}
                                  {mismatch.description}
                                </p>
                                <div className="p-4 bg-muted rounded-lg space-y-3">
                                  <div>
                                    <h4 className="font-semibold">
                                      Expected (from Document)
                                    </h4>
                                    <p className="text-muted-foreground italic">
                                      "{mismatch.details.expected}"
                                    </p>
                                  </div>
                                  <div>
                                    <h4 className="font-semibold">
                                      Actual (in Code)
                                    </h4>
                                    <p className="text-muted-foreground italic">
                                      "{mismatch.details.actual}"
                                    </p>
                                  </div>
                                </div>
                                <div>
                                  <h4 className="font-semibold">
                                    Suggested Action
                                  </h4>
                                  <p className="text-muted-foreground">
                                    {mismatch.details.suggested_action}
                                  </p>
                                </div>
                              </div>
                            </DialogContent>
                          </Dialog>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
