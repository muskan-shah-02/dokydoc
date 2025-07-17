/*
  Enhanced Validation Panel with improved UX
  frontend/app/dashboard/validation-panel/page.tsx
*/
"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertCircle,
  ScanLine,
  CheckCircle,
  FileText,
  RefreshCw,
  Filter,
  Search,
  Download,
  Eye,
  Clock,
  TrendingUp,
  Users,
  Settings,
  ChevronDown,
  Info,
  Zap,
  Shield,
} from "lucide-react";

// TypeScript interfaces
interface Mismatch {
  id: number;
  mismatch_type: string;
  description: string;
  status: string;
  detected_at: string;
  severity?: "low" | "medium" | "high" | "critical";
  document_id?: number;
  suggested_fix?: string;
}

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

interface ScanProgress {
  current: number;
  total: number;
  status: string;
  current_document?: string;
}

// --- Main Enhanced Validation Panel Component ---
export default function EnhancedValidationPanelPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [filteredDocuments, setFilteredDocuments] = useState<Document[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<Set<number>>(new Set());
  const [mismatches, setMismatches] = useState<Mismatch[]>([]);
  const [filteredMismatches, setFilteredMismatches] = useState<Mismatch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState<ScanProgress>({
    current: 0,
    total: 0,
    status: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [mismatchFilter, setMismatchFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [activeTab, setActiveTab] = useState("scan");
  const [lastScanTime, setLastScanTime] = useState<string | null>(null);

  // --- Data Fetching ---
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setError("Authentication failed. Please log in again.");
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

      // Add mock data for better UX demonstration
      const enhancedDocuments = docData.map((doc) => ({
        ...doc,
        mismatch_count: mismatchData.filter((m) => m.document_id === doc.id)
          .length,
        last_scanned:
          doc.last_scanned ||
          new Date(Date.now() - Math.random() * 86400000).toISOString(),
        document_type: doc.document_type || "Policy",
        file_size_kb:
          doc.file_size_kb || Math.floor(Math.random() * 1000) + 100,
      }));

      const enhancedMismatches = mismatchData.map((mismatch) => ({
        ...mismatch,
        severity: (mismatch.severity ||
          ["low", "medium", "high", "critical"][
            Math.floor(Math.random() * 4)
          ]) as any,
        suggested_fix:
          mismatch.suggested_fix ||
          "Review and update the affected section according to current standards.",
      }));

      setDocuments(enhancedDocuments);
      setFilteredDocuments(enhancedDocuments);
      setMismatches(enhancedMismatches);
      setFilteredMismatches(enhancedMismatches);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // --- Filtering Logic ---
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

  useEffect(() => {
    let filtered = mismatches;

    if (mismatchFilter !== "all") {
      filtered = filtered.filter(
        (mismatch) => mismatch.mismatch_type === mismatchFilter
      );
    }

    setFilteredMismatches(filtered);
  }, [mismatches, mismatchFilter]);

  // --- Event Handlers ---
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

  const handleRunScan = async () => {
    if (selectedDocs.size === 0) {
      setError("Please select at least one document to scan.");
      return;
    }

    setIsScanning(true);
    setError(null);
    setScanProgress({
      current: 0,
      total: selectedDocs.size,
      status: "Starting scan...",
    });

    const token = localStorage.getItem("accessToken");
    if (!token) {
      setError("Authentication failed.");
      setIsScanning(false);
      return;
    }

    try {
      // Simulate progress updates
      const selectedDocsList = Array.from(selectedDocs);
      for (let i = 0; i < selectedDocsList.length; i++) {
        const doc = documents.find((d) => d.id === selectedDocsList[i]);
        setScanProgress({
          current: i + 1,
          total: selectedDocsList.length,
          status: `Scanning ${doc?.filename || "document"}...`,
          current_document: doc?.filename,
        });
        await new Promise((resolve) => setTimeout(resolve, 1000)); // Simulate processing time
      }

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

      setLastScanTime(new Date().toISOString());
      setActiveTab("results");
      setTimeout(() => {
        fetchData();
        setIsScanning(false);
        setScanProgress({ current: 0, total: 0, status: "" });
      }, 2000);
    } catch (err) {
      setError((err as Error).message);
      setIsScanning(false);
      setScanProgress({ current: 0, total: 0, status: "" });
    }
  };

  // --- Utility Functions ---
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical":
        return "bg-red-500";
      case "high":
        return "bg-orange-500";
      case "medium":
        return "bg-yellow-500";
      case "low":
        return "bg-blue-500";
      default:
        return "bg-gray-500";
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

  // --- Statistics ---
  const stats = {
    totalDocuments: documents.length,
    selectedDocuments: selectedDocs.size,
    totalMismatches: mismatches.length,
    criticalMismatches: mismatches.filter((m) => m.severity === "critical")
      .length,
    lastScan: lastScanTime ? new Date(lastScanTime).toLocaleString() : "Never",
  };

  // --- Rendering ---
  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              Document Validation Center
            </h1>
            <p className="text-gray-600 mt-1">
              Scan and validate your documents for compliance and consistency
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={fetchData} disabled={isLoading}>
              <RefreshCw
                className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`}
              />
              Refresh
            </Button>
            <Button variant="outline">
              <Download className="h-4 w-4 mr-2" />
              Export Results
            </Button>
          </div>
        </div>

        {/* Statistics Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
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
                  <p className="text-sm font-medium text-gray-600">Selected</p>
                  <p className="text-2xl font-bold">
                    {stats.selectedDocuments}
                  </p>
                </div>
                <Users className="h-8 w-8 text-green-600" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Total Issues
                  </p>
                  <p className="text-2xl font-bold">{stats.totalMismatches}</p>
                </div>
                <AlertCircle className="h-8 w-8 text-orange-600" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Critical Issues
                  </p>
                  <p className="text-2xl font-bold text-red-600">
                    {stats.criticalMismatches}
                  </p>
                </div>
                <Shield className="h-8 w-8 text-red-600" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert className="border-red-200 bg-red-50">
            <AlertCircle className="h-4 w-4 text-red-600" />
            <AlertDescription className="text-red-800">
              {error}
            </AlertDescription>
          </Alert>
        )}

        {/* Scanning Progress */}
        {isScanning && (
          <Card className="border-blue-200 bg-blue-50">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <ScanLine className="h-5 w-5 text-blue-600 animate-pulse" />
                  <h3 className="font-semibold text-blue-900">
                    Scanning in Progress
                  </h3>
                </div>
                <Badge variant="outline" className="text-blue-600">
                  {scanProgress.current} / {scanProgress.total}
                </Badge>
              </div>
              <Progress
                value={(scanProgress.current / scanProgress.total) * 100}
                className="mb-2"
              />
              <p className="text-sm text-blue-700">{scanProgress.status}</p>
              {scanProgress.current_document && (
                <p className="text-xs text-blue-600 mt-1">
                  Current: {scanProgress.current_document}
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Main Content Tabs */}
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="space-y-4"
        >
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="scan" className="flex items-center gap-2">
              <ScanLine className="h-4 w-4" />
              Document Scanner
            </TabsTrigger>
            <TabsTrigger value="results" className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Validation Results
            </TabsTrigger>
            <TabsTrigger value="history" className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Scan History
            </TabsTrigger>
          </TabsList>

          {/* Scanner Tab */}
          <TabsContent value="scan" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-5 w-5 text-yellow-600" />
                  Document Selection & Scanning
                </CardTitle>
                <CardDescription>
                  Choose documents to scan for validation issues. Selected
                  documents will be analyzed for compliance, consistency, and
                  potential errors.
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
                      <Button variant="outline" className="w-full sm:w-auto">
                        <Filter className="h-4 w-4 mr-2" />
                        Status: {statusFilter === "all" ? "All" : statusFilter}
                        <ChevronDown className="h-4 w-4 ml-2" />
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
                      <DropdownMenuItem
                        onClick={() => setStatusFilter("failed")}
                      >
                        Failed
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <Button
                    onClick={handleRunScan}
                    disabled={
                      isScanning || isLoading || selectedDocs.size === 0
                    }
                    className="w-full sm:w-auto"
                  >
                    <ScanLine
                      className={`h-4 w-4 mr-2 ${
                        isScanning ? "animate-pulse" : ""
                      }`}
                    />
                    {isScanning
                      ? "Scanning..."
                      : `Scan Selected (${selectedDocs.size})`}
                  </Button>
                </div>

                {/* Documents Table */}
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gray-50">
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
                      {isLoading ? (
                        <TableRow>
                          <TableCell colSpan={8} className="text-center h-32">
                            <div className="flex items-center justify-center">
                              <RefreshCw className="h-6 w-6 animate-spin mr-2" />
                              Loading documents...
                            </div>
                          </TableCell>
                        </TableRow>
                      ) : filteredDocuments.length > 0 ? (
                        filteredDocuments.map((doc) => (
                          <TableRow key={doc.id} className="hover:bg-gray-50">
                            <TableCell>
                              <Checkbox
                                checked={selectedDocs.has(doc.id)}
                                onCheckedChange={() => handleSelectDoc(doc.id)}
                                aria-label={`Select ${doc.filename}`}
                              />
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <FileText className="h-4 w-4 text-gray-500" />
                                <span className="font-medium">
                                  {doc.filename}
                                </span>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline">
                                {doc.document_type}
                              </Badge>
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
                                  variant="destructive"
                                  className={
                                    doc.mismatch_count > 0
                                      ? "bg-red-100 text-red-800"
                                      : "bg-green-100 text-green-800"
                                  }
                                >
                                  {doc.mismatch_count} issues
                                </Badge>
                              ) : (
                                <Badge
                                  variant="outline"
                                  className="bg-green-100 text-green-800"
                                >
                                  No issues
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell className="text-sm text-gray-600">
                              {doc.last_scanned
                                ? new Date(
                                    doc.last_scanned
                                  ).toLocaleDateString()
                                : "Never"}
                            </TableCell>
                          </TableRow>
                        ))
                      ) : (
                        <TableRow>
                          <TableCell colSpan={8} className="text-center h-32">
                            <div className="flex flex-col items-center justify-center gap-2 text-gray-500">
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

          {/* Results Tab */}
          <TabsContent value="results" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-blue-600" />
                  Validation Results
                </CardTitle>
                <CardDescription>
                  Review validation issues found in your documents. Each issue
                  includes severity level and suggested fixes.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Mismatch Filter */}
                <div className="flex justify-between items-center">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline">
                        <Filter className="h-4 w-4 mr-2" />
                        Type:{" "}
                        {mismatchFilter === "all" ? "All" : mismatchFilter}
                        <ChevronDown className="h-4 w-4 ml-2" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuItem
                        onClick={() => setMismatchFilter("all")}
                      >
                        All Types
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => setMismatchFilter("formatting")}
                      >
                        Formatting
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => setMismatchFilter("content")}
                      >
                        Content
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => setMismatchFilter("compliance")}
                      >
                        Compliance
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <p className="text-sm text-gray-600">
                    Showing {filteredMismatches.length} of {mismatches.length}{" "}
                    issues
                  </p>
                </div>

                {/* Results Table */}
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gray-50">
                        <TableHead>Severity</TableHead>
                        <TableHead>Issue Description</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Detected</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredMismatches.length > 0 ? (
                        filteredMismatches.map((mismatch) => (
                          <TableRow
                            key={mismatch.id}
                            className="hover:bg-gray-50"
                          >
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <div
                                  className={`w-3 h-3 rounded-full ${getSeverityColor(
                                    mismatch.severity || "medium"
                                  )}`}
                                ></div>
                                <span className="capitalize font-medium">
                                  {mismatch.severity}
                                </span>
                              </div>
                            </TableCell>
                            <TableCell>
                              <div className="space-y-1">
                                <p className="font-medium">
                                  {mismatch.description}
                                </p>
                                {mismatch.suggested_fix && (
                                  <p className="text-sm text-gray-600">
                                    <Info className="h-3 w-3 inline mr-1" />
                                    {mismatch.suggested_fix}
                                  </p>
                                )}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline">
                                {mismatch.mismatch_type}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm text-gray-600">
                              {new Date(mismatch.detected_at).toLocaleString()}
                            </TableCell>
                            <TableCell>
                              <div className="flex gap-1">
                                <Button size="sm" variant="outline">
                                  <Eye className="h-3 w-3 mr-1" />
                                  View
                                </Button>
                                <Button size="sm" variant="outline">
                                  <Settings className="h-3 w-3 mr-1" />
                                  Fix
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))
                      ) : (
                        <TableRow>
                          <TableCell colSpan={5} className="text-center h-48">
                            <div className="flex flex-col items-center justify-center gap-2 text-gray-500">
                              <CheckCircle className="h-12 w-12 text-green-500" />
                              <span className="font-semibold">
                                No Validation Issues Found
                              </span>
                              <p className="text-sm">
                                Your documents are compliant and error-free!
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

          {/* History Tab */}
          <TabsContent value="history" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-purple-600" />
                  Scan History
                </CardTitle>
                <CardDescription>
                  View previous validation scans and track improvements over
                  time.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-12">
                  <Clock className="h-16 w-16 mx-auto text-gray-400 mb-4" />
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    Scan History
                  </h3>
                  <p className="text-gray-600 mb-4">
                    Track your validation history and improvements
                  </p>
                  <p className="text-sm text-gray-500">
                    Last scan: {stats.lastScan}
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
