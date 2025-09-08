"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  FileText,
  Tag,
  GitCommit,
  Clock,
  AlertCircle,
  BrainCircuit,
  ListChecks,
  ChevronDown,
  ChevronRight,
  FileCode,
  BookOpen,
  Settings,
  Database,
  Shield,
  Zap,
  Palette,
  TestTube,
  HelpCircle,
} from "lucide-react";

// --- Interface Definitions ---
interface Document {
  id: number;
  filename: string;
  document_type: string;
  version: string;
  created_at: string;
  raw_text: string | null;
  composition_analysis: Record<string, number> | null;
  status: string | null;
  file_size_kb?: number | null;
}

interface DocumentSegment {
  id: number;
  segment_type: string;
  start_char_index: number;
  end_char_index: number;
  document_id: number;
}

interface AnalysisResult {
  id: number;
  segment_id: number;
  document_id: number;
  structured_data: Record<string, any>;
  created_at: string;
}

// --- Segment Type Icons ---
const getSegmentTypeIcon = (segmentType: string) => {
  switch (segmentType) {
    case "BRD":
      return BookOpen;
    case "SRS":
      return FileCode;
    case "API_DOCS":
      return Database;
    case "USER_STORIES":
      return FileText;
    case "TECHNICAL_SPECS":
      return Settings;
    case "PROCESS_FLOWS":
      return Zap;
    case "DATA_MODELS":
      return Database;
    case "SECURITY_REQUIREMENTS":
      return Shield;
    case "PERFORMANCE_REQUIREMENTS":
      return Zap;
    case "UI_UX_SPECS":
      return Palette;
    case "TEST_CASES":
      return TestTube;
    default:
      return HelpCircle;
  }
};

const getSegmentTypeColor = (segmentType: string) => {
  switch (segmentType) {
    case "BRD":
      return "bg-blue-100 text-blue-800 border-blue-200";
    case "SRS":
      return "bg-green-100 text-green-800 border-green-200";
    case "API_DOCS":
      return "bg-purple-100 text-purple-800 border-purple-200";
    case "USER_STORIES":
      return "bg-orange-100 text-orange-800 border-orange-200";
    case "TECHNICAL_SPECS":
      return "bg-indigo-100 text-indigo-800 border-indigo-200";
    case "PROCESS_FLOWS":
      return "bg-yellow-100 text-yellow-800 border-yellow-200";
    case "DATA_MODELS":
      return "bg-teal-100 text-teal-800 border-teal-200";
    case "SECURITY_REQUIREMENTS":
      return "bg-red-100 text-red-800 border-red-200";
    case "PERFORMANCE_REQUIREMENTS":
      return "bg-pink-100 text-pink-800 border-pink-200";
    case "UI_UX_SPECS":
      return "bg-cyan-100 text-cyan-800 border-cyan-200";
    case "TEST_CASES":
      return "bg-lime-100 text-lime-800 border-lime-200";
    default:
      return "bg-gray-100 text-gray-800 border-gray-200";
  }
};

// --- Enhanced Segment Analysis Display Component ---
const SegmentAnalysisCard = ({
  segment,
  analysisResult,
  isLoading,
}: {
  segment: DocumentSegment;
  analysisResult: AnalysisResult | null;
  isLoading: boolean;
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const IconComponent = getSegmentTypeIcon(segment.segment_type);
  const colorClasses = getSegmentTypeColor(segment.segment_type);

  if (isLoading) {
    return (
      <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/3 mb-2"></div>
          <div className="h-3 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    );
  }

  const renderStructuredData = (data: any) => {
    if (!data || typeof data !== "object") {
      return (
        <div className="text-gray-500 italic">No structured data available</div>
      );
    }

    // Pull common metadata fields to a concise header
    const metaKeys = [
      "date",
      "file",
      "author",
      "version",
      "document_title",
      "title",
    ];
    const meta: Record<string, any> = {};
    const rest: Record<string, any> = {};
    Object.entries(data).forEach(([k, v]) => {
      if (metaKeys.includes(k)) meta[k] = v;
      else rest[k] = v;
    });

    return (
      <div className="space-y-6">
        {Object.keys(meta).length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Object.entries(meta).map(([k, v]) => (
              <div key={k} className="bg-white border rounded p-3">
                <div className="text-xs uppercase text-gray-500">
                  {k.replace(/_/g, " ")}
                </div>
                <div className="text-sm text-gray-800 break-words">
                  {String(v)}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="space-y-4">
          {Object.entries(rest).map(([key, value]) => (
            <div key={key} className="border-l-4 border-blue-200 pl-4">
              <h5 className="font-semibold text-gray-800 capitalize mb-2">
                {key.replace(/_/g, " ")}
              </h5>
              {Array.isArray(value) ? (
                <ul className="space-y-1 list-disc ml-4">
                  {value.map((item, index) => (
                    <li
                      key={index}
                      className="text-sm text-gray-700 bg-gray-50 p-2 rounded"
                    >
                      {typeof item === "object"
                        ? JSON.stringify(item, null, 2)
                        : String(item)}
                    </li>
                  ))}
                </ul>
              ) : typeof value === "object" ? (
                <div className="bg-gray-50 p-3 rounded text-sm">
                  <pre className="whitespace-pre-wrap">
                    {JSON.stringify(value, null, 2)}
                  </pre>
                </div>
              ) : (
                <p className="text-sm text-gray-700 bg-gray-50 p-2 rounded">
                  {String(value)}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger className="w-full">
        <div
          className={`bg-white p-4 rounded-lg border shadow-sm hover:shadow-md transition-all duration-200 ${colorClasses}`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <IconComponent className="h-6 w-6" />
              <div>
                <h3 className="font-semibold text-lg text-gray-900">
                  {segment.segment_type.replace(/_/g, " ")}
                </h3>
                <p className="text-sm text-gray-600">
                  Characters {segment.start_char_index.toLocaleString()} -{" "}
                  {segment.end_char_index.toLocaleString()}
                  <span className="ml-2 text-xs bg-gray-100 px-2 py-1 rounded">
                    {(
                      segment.end_char_index - segment.start_char_index
                    ).toLocaleString()}{" "}
                    chars
                  </span>
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Badge
                variant="outline"
                className="bg-green-100 text-green-800 border-green-200"
              >
                {isLoading ? "Analyzing..." : "Analyzed"}
              </Badge>
              {isOpen ? (
                <ChevronDown className="h-5 w-5 text-gray-500" />
              ) : (
                <ChevronRight className="h-5 w-5 text-gray-500" />
              )}
            </div>
          </div>
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2">
        <div className="bg-gray-50 p-6 rounded-lg border">
          {analysisResult ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="font-semibold text-gray-900 text-lg">
                  Analysis Results
                </h4>
                <Badge variant="secondary" className="text-xs">
                  {Object.keys(analysisResult.structured_data || {}).length}{" "}
                  fields
                </Badge>
              </div>
              {renderStructuredData(analysisResult.structured_data)}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <BrainCircuit className="h-12 w-12 mx-auto mb-3 text-gray-400" />
              <p className="text-lg font-medium">No analysis data available</p>
              <p className="text-sm">This segment hasn't been analyzed yet.</p>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};

// --- Main Document Detail Page Component ---
export default function DocumentDetailPage() {
  const [document, setDocument] = useState<Document | null>(null);
  const [segments, setSegments] = useState<DocumentSegment[]>([]);
  const [analysisResults, setAnalysisResults] = useState<
    Record<number, AnalysisResult>
  >({});
  const [loadingSegments, setLoadingSegments] = useState<
    Record<number, boolean>
  >({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [analysisStats, setAnalysisStats] = useState({
    successful: 0,
    failed: 0,
    notAttempted: 0,
  });
  const [viewMode, setViewMode] = useState<"separated" | "consolidated">(
    "separated"
  );
  const [consolidatedAnalysis, setConsolidatedAnalysis] = useState<any>(null);
  const [isGeneratingConsolidated, setIsGeneratingConsolidated] =
    useState(false);

  // Get the document ID from the URL
  useEffect(() => {
    if (typeof window !== "undefined") {
      const pathParts = window.location.pathname.split("/");
      const id = pathParts.pop() || "";
      setDocumentId(id);
    }
  }, []);

  // Fetch document details and segments
  const fetchData = useCallback(async () => {
    if (!documentId) return;

    setIsLoading(true);
    setError(null);

    const token = localStorage.getItem("accessToken");

    if (!token) {
      setError("Authentication token not found.");
      setIsLoading(false);
      return;
    }

    try {
      // Use the new combined analysis endpoint - single request gets everything!
      const analysisRes = await fetch(
        `http://localhost:8000/api/v1/documents/${documentId}/analysis`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!analysisRes.ok) {
        const errData = await analysisRes.json();
        throw new Error(errData.detail || "Failed to fetch document analysis.");
      }

      const analysisData = await analysisRes.json();

      // Set document data
      setDocument(analysisData.document);

      // Extract segments and analysis results from the combined response
      const segmentsWithAnalysis = analysisData.segments || [];
      const segments: DocumentSegment[] = [];
      const newAnalysisResults: Record<number, AnalysisResult> = {};

      // Process the combined data - no more N+1 queries or 404s!
      segmentsWithAnalysis.forEach((item: any) => {
        segments.push(item.segment);
        if (item.analysis_result) {
          newAnalysisResults[item.segment.id] = item.analysis_result;
        }
      });

      setSegments(segments);
      setAnalysisResults(newAnalysisResults);

      // Set analysis stats from the backend response
      const stats = analysisData.stats || { analyzed: 0, failed: 0, total: 0 };
      setAnalysisStats({
        successful: stats.analyzed,
        failed: stats.failed,
        notAttempted: stats.total - stats.analyzed - stats.failed,
      });

      console.log(
        `Analysis Statistics: ${stats.analyzed} successful, ${
          stats.failed
        } failed, ${stats.total - stats.analyzed - stats.failed} not attempted`
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Note: loadSegmentAnalysis function removed - we now get all data in one request!

  const handleRunAnalysis = async () => {
    if (!documentId) return;

    setIsAnalyzing(true);
    setError(null);

    const token = localStorage.getItem("accessToken");

    if (!token) {
      setError("Authentication token not found.");
      setIsAnalyzing(false);
      return;
    }

    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/analysis/document/${documentId}/run`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to start analysis.");
      }

      alert(
        "Multi-pass analysis has been triggered! Results will appear here shortly. Please refresh the page in a moment."
      );

      // Refresh the data after a short delay
      setTimeout(() => {
        fetchData();
      }, 3000);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const loadConsolidatedAnalysis = async (): Promise<boolean> => {
    if (!documentId) return false;
    const token = localStorage.getItem("accessToken");
    if (!token) return false;
    try {
      const resp = await fetch(
        `http://localhost:8000/api/v1/analysis/document/${documentId}/consolidated`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!resp.ok) return false;
      const data = await resp.json();
      setConsolidatedAnalysis(data);
      return true;
    } catch {
      return false;
    }
  };

  const generateConsolidatedAnalysis = async () => {
    if (!documentId || Object.keys(analysisResults).length === 0) return;

    setIsGeneratingConsolidated(true);
    setError(null);

    const token = localStorage.getItem("accessToken");
    if (!token) {
      setError("Authentication token not found.");
      setIsGeneratingConsolidated(false);
      return;
    }

    try {
      // Collect all analysis results
      const allAnalysisData = Object.values(analysisResults).map((result) => ({
        segment_type: segments.find((s) => s.id === result.segment_id)
          ?.segment_type,
        structured_data: result.structured_data,
      }));

      const response = await fetch(
        `http://localhost:8000/api/v1/analysis/document/${documentId}/consolidate`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ analysis_data: allAnalysisData, save: true }),
        }
      );

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(
          errData.detail || "Failed to generate consolidated analysis."
        );
      }

      const consolidatedData = await response.json();
      setConsolidatedAnalysis(consolidatedData);
      setViewMode("consolidated");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsGeneratingConsolidated(false);
    }
  };

  if (isLoading) {
    return <div className="p-6">Loading document details...</div>;
  }

  if (error) {
    return (
      <div className="p-6 text-red-500 bg-red-100 rounded-lg flex items-center">
        <AlertCircle className="mr-2" /> Error: {error}
      </div>
    );
  }

  if (!document) {
    return <div className="p-6">Document not found.</div>;
  }

  return (
    <div className="p-2 sm:p-4 space-y-6">
      {/* Document Header */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center">
              <FileText className="mr-3 h-8 w-8 text-gray-500" />
              {document.filename}
            </h1>
            <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
              <span className="flex items-center">
                <Tag className="mr-1.5 h-4 w-4" /> {document.document_type}
              </span>
              <span className="flex items-center">
                <GitCommit className="mr-1.5 h-4 w-4" /> Version{" "}
                {document.version}
              </span>
              <span className="flex items-center">
                <Clock className="mr-1.5 h-4 w-4" /> Uploaded on{" "}
                {new Date(document.created_at).toLocaleDateString()}
              </span>
              {document.file_size_kb && (
                <span className="flex items-center">
                  <FileText className="mr-1.5 h-4 w-4" />{" "}
                  {document.file_size_kb} KB
                </span>
              )}
            </div>
          </div>
          <Badge
            variant={document.status === "completed" ? "default" : "secondary"}
            className={
              document.status === "completed"
                ? "bg-green-100 text-green-800"
                : ""
            }
          >
            Status: {document.status}
          </Badge>
        </div>
      </div>

      {/* Composition Analysis Summary */}
      {document.composition_analysis && (
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <BrainCircuit className="mr-3 h-6 w-6 text-blue-600" />
            Document Composition Analysis
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {document.composition_analysis.composition &&
              Object.entries(document.composition_analysis.composition).map(
                ([type, percentage]) => (
                  <div
                    key={type}
                    className="text-center p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="text-2xl font-bold text-blue-600">
                      {percentage}%
                    </div>
                    <div className="text-sm text-gray-600">{type}</div>
                  </div>
                )
              )}
          </div>
          {document.composition_analysis.confidence && (
            <div className="mt-4 p-3 bg-blue-50 rounded-lg">
              <div className="text-sm text-blue-800">
                <strong>Confidence:</strong>{" "}
                {document.composition_analysis.confidence}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Document Segments Section */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold flex items-center">
              <FileCode className="mr-3 h-6 w-6 text-green-600" />
              Document Analysis
            </h2>
            {segments.length > 0 && (
              <div className="mt-2 text-sm text-gray-600">
                {analysisStats.successful} of{" "}
                {analysisStats.successful +
                  analysisStats.failed +
                  analysisStats.notAttempted}{" "}
                segments analyzed
                {analysisStats.failed > 0 && (
                  <span className="text-red-600 ml-2">
                    ({analysisStats.failed} failed)
                  </span>
                )}
                {analysisStats.notAttempted > 0 && (
                  <span className="text-gray-500 ml-2">
                    ({analysisStats.notAttempted} not attempted)
                  </span>
                )}
              </div>
            )}
            {document?.composition_analysis?.composition && (
              <div className="mt-2 text-xs text-gray-500">
                Document composition:{" "}
                {Object.entries(document.composition_analysis.composition)
                  .filter(([_, percentage]) => percentage > 0)
                  .map(([type, percentage]) => `${type}: ${percentage}%`)
                  .join(", ")}
              </div>
            )}
          </div>
          <div className="flex items-center space-x-3">
            {Object.keys(analysisResults).length > 0 && (
              <div className="flex items-center space-x-2">
                <Button
                  variant={viewMode === "separated" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setViewMode("separated")}
                >
                  <FileCode className="mr-2 h-4 w-4" />
                  Separated View
                </Button>
                <Button
                  variant={viewMode === "consolidated" ? "default" : "outline"}
                  size="sm"
                  onClick={async () => {
                    // Try loading saved consolidated first; if not found, generate and save
                    const loaded = await loadConsolidatedAnalysis();
                    if (!loaded) {
                      await generateConsolidatedAnalysis();
                    } else {
                      setViewMode("consolidated");
                    }
                  }}
                  disabled={isGeneratingConsolidated}
                >
                  <BrainCircuit className="mr-2 h-4 w-4" />
                  {isGeneratingConsolidated
                    ? "Generating..."
                    : "Consolidated View"}
                </Button>
              </div>
            )}
            <Button
              onClick={handleRunAnalysis}
              disabled={isAnalyzing}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {isAnalyzing
                ? "Running Multi-Pass Analysis..."
                : "Run Multi-Pass Analysis"}
            </Button>
          </div>
        </div>

        <div className="space-y-4">
          {viewMode === "separated" ? (
            // Separated View - Individual segment cards
            segments.length > 0 ? (
              segments.map((segment) => {
                const hasAnalysis = analysisResults[segment.id];
                const isLoading = loadingSegments[segment.id] || false;

                // Only show segments that have successful analysis or are currently loading
                // Hide segments that failed analysis or were not attempted
                if (!hasAnalysis && !isLoading) {
                  return null;
                }

                return (
                  <SegmentAnalysisCard
                    key={segment.id}
                    segment={segment}
                    analysisResult={hasAnalysis || null}
                    isLoading={isLoading}
                  />
                );
              })
            ) : (
              <div className="text-center py-8 text-gray-500">
                <FileCode className="h-12 w-12 mx-auto mb-3 text-gray-400" />
                <p>
                  No segments have been created yet. Run the multi-pass analysis
                  to generate document segments.
                </p>
              </div>
            )
          ) : // Consolidated View - Single unified analysis
          consolidatedAnalysis ? (
            <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 flex items-center">
                  <BrainCircuit className="mr-2 h-5 w-5 text-blue-600" />
                  Consolidated Analysis
                </h3>
                <Badge variant="secondary" className="text-xs">
                  {Object.keys(consolidatedAnalysis).length} sections
                </Badge>
              </div>
              <div className="space-y-6">
                {Object.entries(consolidatedAnalysis).map(([key, value]) => (
                  <div key={key} className="border-l-4 border-blue-200 pl-4">
                    <h4 className="font-semibold text-gray-800 capitalize mb-3 text-lg">
                      {key.replace(/_/g, " ")}
                    </h4>
                    {Array.isArray(value) ? (
                      <ul className="space-y-2">
                        {value.map((item, index) => (
                          <li
                            key={index}
                            className="text-sm text-gray-600 bg-gray-50 p-3 rounded border"
                          >
                            {typeof item === "object" ? (
                              <pre className="whitespace-pre-wrap text-xs">
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            ) : (
                              String(item)
                            )}
                          </li>
                        ))}
                      </ul>
                    ) : typeof value === "object" ? (
                      <div className="bg-gray-50 p-4 rounded border">
                        <pre className="whitespace-pre-wrap text-sm">
                          {JSON.stringify(value, null, 2)}
                        </pre>
                      </div>
                    ) : (
                      <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded border">
                        {String(value)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <BrainCircuit className="h-12 w-12 mx-auto mb-3 text-gray-400" />
              <p className="text-lg font-medium">
                No consolidated analysis available
              </p>
              <p className="text-sm">
                Click "Consolidated View" to generate a unified analysis.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Raw Text Section */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <h2 className="text-xl font-semibold mb-4">Raw Document Text</h2>
        <div className="prose max-w-none bg-gray-50 p-4 rounded-md h-96 overflow-y-auto border">
          <pre className="whitespace-pre-wrap break-words text-sm">
            {document.raw_text ||
              "No content was extracted, or parsing is still in progress."}
          </pre>
        </div>
      </div>
    </div>
  );
}
