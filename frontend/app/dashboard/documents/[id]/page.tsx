"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
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
  Activity,
  FileCode,
  BookOpen,
  Settings,
  Database,
  Shield,
  Zap,
  Palette,
  TestTube,
  HelpCircle,
  Loader2,
  History,
  Timer,
  PlayCircle,
  PauseCircle,
  CheckCircle,
  XCircle,
  Globe,
  Layers,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

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

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger className="w-full">
        <div
          className={`bg-white p-6 rounded-xl border-2 shadow-sm hover:shadow-lg transition-all duration-300 ${colorClasses} ${
            isOpen ? "border-blue-300 shadow-md" : "hover:border-gray-300"
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div
                className={`p-3 rounded-lg ${
                  colorClasses.includes("bg-blue")
                    ? "bg-blue-100"
                    : colorClasses.includes("bg-green")
                    ? "bg-green-100"
                    : "bg-gray-100"
                }`}
              >
                <IconComponent className="h-7 w-7" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-xl text-gray-900 mb-1">
                  {segment.segment_type.replace(/_/g, " ")}
                </h3>
                <div className="flex items-center space-x-3 text-sm text-gray-600">
                  <span className="flex items-center">
                    <span className="font-medium">Range:</span>
                    <span className="ml-1">
                      {segment.start_char_index.toLocaleString()} -{" "}
                      {segment.end_char_index.toLocaleString()}
                    </span>
                  </span>
                  <span className="bg-gray-100 px-3 py-1 rounded-full text-xs font-medium">
                    {(
                      segment.end_char_index - segment.start_char_index
                    ).toLocaleString()}{" "}
                    chars
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <Badge
                variant="outline"
                className={`px-3 py-1 font-medium ${
                  isLoading
                    ? "bg-yellow-100 text-yellow-800 border-yellow-300"
                    : analysisResult
                    ? "bg-green-100 text-green-800 border-green-300"
                    : "bg-gray-100 text-gray-600 border-gray-300"
                }`}
              >
                {isLoading ? (
                  <span className="flex items-center">
                    <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-yellow-800 mr-2"></div>
                    Analyzing...
                  </span>
                ) : analysisResult ? (
                  "✓ Analyzed"
                ) : (
                  "Pending"
                )}
              </Badge>
              <div
                className={`p-2 rounded-lg transition-transform duration-200 ${
                  isOpen ? "rotate-180 bg-blue-100" : "hover:bg-gray-100"
                }`}
              >
                <ChevronDown className="h-5 w-5 text-gray-500" />
              </div>
            </div>
          </div>
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-4">
        <div className="bg-gradient-to-br from-gray-50 to-white p-6 rounded-xl border border-gray-200 shadow-sm">
          {analysisResult ? (
            <div className="space-y-6">
              <div className="flex items-center justify-between pb-4 border-b border-gray-200">
                <h4 className="font-bold text-gray-900 text-xl flex items-center">
                  <span className="w-3 h-3 bg-blue-500 rounded-full mr-3"></span>
                  Analysis Results
                </h4>
                <div className="flex items-center space-x-2">
                  <Badge
                    variant="secondary"
                    className="bg-blue-100 text-blue-800 px-3 py-1"
                  >
                    {Object.keys(analysisResult.structured_data || {}).length}{" "}
                    fields
                  </Badge>
                  <Badge
                    variant="outline"
                    className="bg-green-50 text-green-700 border-green-200"
                  >
                    ✓ Complete
                  </Badge>
                </div>
              </div>
              <div className="max-h-96 overflow-y-auto">
                {renderStructuredData(analysisResult.structured_data)}
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <div className="bg-gray-100 rounded-full p-4 w-20 h-20 mx-auto mb-4 flex items-center justify-center">
                <BrainCircuit className="h-10 w-10 text-gray-400" />
              </div>
              <h4 className="text-lg font-semibold text-gray-700 mb-2">
                No Analysis Available
              </h4>
              <p className="text-sm text-gray-600">
                This segment hasn't been analyzed yet or the analysis failed.
              </p>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};

// Smart data renderer for user-friendly display
const renderStructuredData = (data: any) => {
  if (!data || typeof data !== "object") {
    return (
      <div className="text-gray-500 italic">No structured data available</div>
    );
  }

  // Smart renderer that creates user-friendly displays based on content type
  const renderSmartContent = (obj: any): React.JSX.Element => {
    // Handle endpoints specifically for API_DOCS
    if (obj.endpoints && Array.isArray(obj.endpoints)) {
      return (
        <div className="space-y-4">
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg p-4">
            <h4 className="font-semibold text-green-900 mb-2 flex items-center">
              <Globe className="w-4 h-4 mr-2" />
              API Endpoints
            </h4>
            <p className="text-green-800 text-sm">
              This section contains {obj.endpoints.length} API endpoint(s) with
              their specifications.
            </p>
          </div>

          <div className="grid gap-4">
            {obj.endpoints.map((endpoint: any, index: number) => (
              <div
                key={index}
                className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm"
              >
                <div className="flex items-center space-x-3 mb-3">
                  <Badge className="bg-blue-100 text-blue-800">
                    {endpoint.method || "GET"}
                  </Badge>
                  <code className="bg-gray-100 px-2 py-1 rounded text-sm font-mono">
                    {endpoint.path || endpoint.url || "No path specified"}
                  </code>
                </div>

                {endpoint.description && (
                  <p className="text-gray-700 mb-3">{endpoint.description}</p>
                )}

                {endpoint.parameters && endpoint.parameters.length > 0 && (
                  <div className="mb-3">
                    <h6 className="font-medium text-gray-800 mb-2">
                      Parameters:
                    </h6>
                    <div className="space-y-1">
                      {endpoint.parameters.map((param: any, i: number) => (
                        <div
                          key={i}
                          className="flex items-center space-x-2 text-sm"
                        >
                          <code className="bg-gray-100 px-2 py-1 rounded">
                            {param.name || param}
                          </code>
                          {param.type && (
                            <span className="text-gray-500">
                              ({param.type})
                            </span>
                          )}
                          {param.required && (
                            <Badge variant="outline" className="text-xs">
                              Required
                            </Badge>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {endpoint.response && (
                  <div>
                    <h6 className="font-medium text-gray-800 mb-1">
                      Response:
                    </h6>
                    <p className="text-sm text-gray-600">{endpoint.response}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      );
    }

    // Handle architecture for TECHNICAL_SPECS
    if (obj.architecture && typeof obj.architecture === "object") {
      return (
        <div className="space-y-4">
          <div className="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-lg p-4">
            <h4 className="font-semibold text-purple-900 mb-2 flex items-center">
              <Layers className="w-4 h-4 mr-2" />
              System Architecture
            </h4>
            <p className="text-purple-800 text-sm">
              Technical architecture and system design specifications.
            </p>
          </div>

          {obj.architecture.core_services && (
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
              <h5 className="font-medium text-gray-800 mb-3">Core Services</h5>
              <div className="grid gap-3">
                {obj.architecture.core_services.map(
                  (service: any, index: number) => (
                    <div
                      key={index}
                      className="border-l-4 border-blue-200 pl-4 py-2"
                    >
                      <div className="flex items-center space-x-2 mb-1">
                        <h6 className="font-medium text-blue-900">
                          {service.name}
                        </h6>
                        {service.technology && (
                          <Badge variant="outline" className="text-xs">
                            {service.technology}
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-gray-700">
                        {service.description}
                      </p>
                    </div>
                  )
                )}
              </div>
            </div>
          )}
        </div>
      );
    }

    // Handle security requirements
    if (obj.security_requirements && Array.isArray(obj.security_requirements)) {
      return (
        <div className="space-y-4">
          <div className="bg-gradient-to-r from-red-50 to-orange-50 border border-red-200 rounded-lg p-4">
            <h4 className="font-semibold text-red-900 mb-2 flex items-center">
              <Shield className="w-4 h-4 mr-2" />
              Security Requirements
            </h4>
            <p className="text-red-800 text-sm">
              Security specifications and compliance requirements.
            </p>
          </div>

          <div className="space-y-3">
            {obj.security_requirements.map((req: any, index: number) => (
              <div
                key={index}
                className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm"
              >
                <h6 className="font-medium text-gray-800 mb-2">
                  {req.requirement || `Requirement ${index + 1}`}
                </h6>
                {req.details && typeof req.details === "object" && (
                  <div className="space-y-2">
                    {Object.entries(req.details).map(([key, value]) => (
                      <div
                        key={key}
                        className="border-l-4 border-orange-200 pl-3"
                      >
                        <div className="font-medium text-sm text-orange-900 capitalize">
                          {key.replace(/_/g, " ")}
                        </div>
                        <div className="text-sm text-gray-700">
                          {String(value)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      );
    }

    // Handle UI/UX specifications
    if (obj.modules && Array.isArray(obj.modules)) {
      return (
        <div className="space-y-4">
          <div className="bg-gradient-to-r from-pink-50 to-rose-50 border border-pink-200 rounded-lg p-4">
            <h4 className="font-semibold text-pink-900 mb-2 flex items-center">
              <Palette className="w-4 h-4 mr-2" />
              UI/UX Specifications
            </h4>
            <p className="text-pink-800 text-sm">
              User interface and user experience design specifications.
            </p>
          </div>

          <div className="grid gap-4">
            {obj.modules.map((module: any, index: number) => (
              <div
                key={index}
                className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm"
              >
                <h6 className="font-medium text-gray-800 mb-2">
                  {module.module_name || `Module ${index + 1}`}
                </h6>
                {module.features && Array.isArray(module.features) && (
                  <div>
                    <p className="text-sm text-gray-600 mb-2">Features:</p>
                    <div className="flex flex-wrap gap-2">
                      {module.features.map((feature: string, i: number) => (
                        <Badge key={i} variant="outline" className="text-xs">
                          {feature}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      );
    }

    // Generic fallback for other data types
    return renderGenericContent(obj);
  };

  // Generic content renderer for unstructured data
  const renderGenericContent = (obj: any): React.JSX.Element => {
    return (
      <div className="space-y-4">
        {Object.entries(obj).map(([key, value]) => (
          <div
            key={key}
            className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm"
          >
            <h6 className="font-medium text-gray-800 mb-3 capitalize flex items-center">
              <span className="w-2 h-2 bg-gray-400 rounded-full mr-2"></span>
              {key.replace(/_/g, " ")}
            </h6>

            {Array.isArray(value) ? (
              <div className="space-y-2">
                {value.map((item, index) => (
                  <div
                    key={index}
                    className="border-l-4 border-gray-200 pl-3 py-1"
                  >
                    <div className="text-sm text-gray-700">
                      {typeof item === "object"
                        ? JSON.stringify(item, null, 2)
                        : String(item)}
                    </div>
                  </div>
                ))}
              </div>
            ) : typeof value === "object" && value !== null ? (
              <div className="bg-gray-50 p-3 rounded">
                <pre className="text-sm text-gray-700 whitespace-pre-wrap">
                  {JSON.stringify(value, null, 2)}
                </pre>
              </div>
            ) : (
              <p className="text-sm text-gray-700">{String(value)}</p>
            )}
          </div>
        ))}
      </div>
    );
  };

  // Extract summary if available
  const summary = data.summary;
  const remainingData = { ...data };
  delete remainingData.summary;

  return (
    <div className="space-y-6">
      {/* Summary Section */}
      {summary && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
          <h4 className="font-semibold text-blue-900 mb-2 flex items-center">
            <span className="w-2 h-2 bg-blue-500 rounded-full mr-2"></span>
            Summary
          </h4>
          <p className="text-blue-800 text-sm leading-relaxed">{summary}</p>
        </div>
      )}

      {/* Smart Content Rendering */}
      {Object.keys(remainingData).length > 0 ? (
        renderSmartContent(remainingData)
      ) : (
        <div className="text-gray-500 italic text-center py-8">
          No detailed analysis data available
        </div>
      )}
    </div>
  );
};

// Helper function to format elapsed time
const formatElapsedTime = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
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
  const [analysisRuns, setAnalysisRuns] = useState<any[]>([]);
  const [activeRun, setActiveRun] = useState<any>(null);
  const [isLoadingRuns, setIsLoadingRuns] = useState(false);
  const [analysisStartTime, setAnalysisStartTime] = useState<Date | null>(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [showRunHistory, setShowRunHistory] = useState(false);

  // Memoize progress calculation to prevent unnecessary re-renders
  const progressPercentage = useMemo(() => {
    return Math.min(100, Math.round((elapsedTime / 300) * 100));
  }, [elapsedTime]);

  // Get the document ID from the URL
  useEffect(() => {
    if (typeof window !== "undefined") {
      const pathParts = window.location.pathname.split("/");
      const id = pathParts.pop() || "";
      setDocumentId(id);
    }
  }, []);

  // Timer effect for tracking analysis progress
  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (isAnalyzing && analysisStartTime) {
      interval = setInterval(() => {
        const now = new Date();
        const elapsed = Math.floor(
          (now.getTime() - analysisStartTime.getTime()) / 1000
        );
        // Only update if the elapsed time has actually changed (reduces unnecessary re-renders)
        setElapsedTime((prevElapsed) =>
          prevElapsed !== elapsed ? elapsed : prevElapsed
        );
      }, 1000);
    } else {
      setElapsedTime(0);
    }

    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [isAnalyzing, analysisStartTime]);

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

  // Fetch analysis runs for this document
  const fetchAnalysisRuns = useCallback(async () => {
    if (!documentId) return;

    setIsLoadingRuns(true);
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setIsLoadingRuns(false);
      return;
    }

    try {
      // Fetch all runs
      const runsResponse = await fetch(
        `http://localhost:8000/api/v1/analysis/document/${documentId}/runs`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (runsResponse.ok) {
        try {
          const runsData = await runsResponse.json();
          setAnalysisRuns(runsData.runs || []);
        } catch {
          setAnalysisRuns([]);
        }
      } else {
        setAnalysisRuns([]);
      }

      // Fetch active run
      try {
        const activeResponse = await fetch(
          `http://localhost:8000/api/v1/analysis/document/${documentId}/runs/active`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );

        if (activeResponse.ok) {
          try {
            const activeData = await activeResponse.json();
            setActiveRun(activeData.active_run || null);
          } catch {
            setActiveRun(null);
          }
        } else {
          setActiveRun(null);
        }
      } catch (activeErr) {
        // Swallow network/server errors for the active endpoint to avoid UI crashes
        setActiveRun(null);
      }
    } catch (err) {
      console.error("Error fetching analysis runs:", err);
    } finally {
      setIsLoadingRuns(false);
    }
  }, [documentId]);

  useEffect(() => {
    fetchData();
    fetchAnalysisRuns();
  }, [fetchData, fetchAnalysisRuns]);

  const handleRunAnalysis = async () => {
    if (!documentId) return;

    setIsAnalyzing(true);
    setError(null);
    setAnalysisStartTime(new Date());

    const token = localStorage.getItem("accessToken");

    if (!token) {
      setError("Authentication token not found.");
      setIsAnalyzing(false);
      setAnalysisStartTime(null);
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

      // Start periodic polling for updates (optimized to reduce page blinking)
      const pollInterval = setInterval(async () => {
        try {
          // Only check if analysis is complete, don't refetch all data every time
          const activeRunResponse = await fetch(
            `http://localhost:8000/api/v1/analysis/document/${documentId}/runs/active`,
            { headers: { Authorization: `Bearer ${token}` } }
          );

          if (activeRunResponse.ok) {
            const activeRunData = await activeRunResponse.json();
            if (!activeRunData || activeRunData.length === 0) {
              // No active run, analysis is complete - now fetch updated data
              setIsAnalyzing(false);
              setAnalysisStartTime(null);
              clearInterval(pollInterval);

              // Only fetch data when analysis is actually complete
              await fetchData();
              await fetchAnalysisRuns();
            }
          }
        } catch (pollErr) {
          console.error("Error polling for updates:", pollErr);
        }
      }, 3000); // Reduced frequency from 2s to 3s

      // Stop polling after 10 minutes maximum
      setTimeout(() => {
        clearInterval(pollInterval);
        setIsAnalyzing(false);
        setAnalysisStartTime(null);
      }, 600000);
    } catch (err) {
      setError((err as Error).message);
      setIsAnalyzing(false);
      setAnalysisStartTime(null);
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
              {isAnalyzing ? (
                <div className="flex items-center">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing...
                </div>
              ) : (
                "Run Multi-Pass Analysis"
              )}
            </Button>
          </div>
        </div>

        {/* Processing Status Section */}
        {isAnalyzing && (
          <Card className="border-blue-200 bg-blue-50">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className="bg-blue-100 p-2 rounded-full">
                    <Timer className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-blue-900">
                      Analysis in Progress
                    </h3>
                    <p className="text-sm text-blue-700">
                      Multi-pass document analysis is running. This typically
                      takes 3-5 minutes.
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-blue-900">
                    {formatElapsedTime(elapsedTime)}
                  </div>
                  <div className="text-xs text-blue-600">Elapsed Time</div>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-blue-700">
                    Estimated completion time:
                  </span>
                  <span className="font-medium text-blue-900">3-5 minutes</span>
                </div>

                <div className="w-full bg-blue-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                    style={{
                      width: `${progressPercentage}%`,
                    }}
                  ></div>
                </div>

                <div className="flex items-center justify-between text-xs text-blue-600">
                  <span>0 min</span>
                  <span className="flex items-center">
                    <PlayCircle className="h-3 w-3 mr-1" />
                    Processing segments...
                  </span>
                  <span>5 min</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Analysis Runs Section */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5" />
                  Analysis Runs
                </CardTitle>
                <CardDescription>
                  Track the progress and history of analysis runs for this
                  document
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowRunHistory(!showRunHistory)}
                className="flex items-center gap-2"
              >
                <History className="h-4 w-4" />
                {showRunHistory ? "Hide History" : "Show History"}
                <ChevronDown
                  className={`h-4 w-4 transition-transform ${
                    showRunHistory ? "rotate-180" : ""
                  }`}
                />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isLoadingRuns ? (
              <div className="flex items-center justify-center p-4">
                <Loader2 className="h-6 w-6 animate-spin" />
                <span className="ml-2">Loading analysis runs...</span>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Active Run */}
                {activeRun && (
                  <div className="border rounded-lg p-4 bg-blue-50 border-blue-200">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-medium text-blue-900">
                          Active Analysis
                        </h4>
                        <p className="text-sm text-blue-700">
                          Run #{activeRun.id} - {activeRun.status}
                        </p>
                      </div>
                      <div className="text-right">
                        <div className="text-sm text-blue-700">
                          {activeRun.completed_segments || 0} /{" "}
                          {activeRun.total_segments || 0} segments
                        </div>
                        <div className="text-xs text-blue-600">
                          {activeRun.progress_percentage?.toFixed(1) || 0}%
                          complete
                        </div>
                      </div>
                    </div>
                    {activeRun.total_segments > 0 && (
                      <div className="mt-2">
                        <div className="w-full bg-blue-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                            style={{
                              width: `${activeRun.progress_percentage || 0}%`,
                            }}
                          ></div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Run History */}
                {showRunHistory && analysisRuns.length > 0 && (
                  <div>
                    <h4 className="font-medium mb-2">Previous Runs</h4>
                    <div className="space-y-2">
                      {analysisRuns.slice(0, 5).map((run) => (
                        <div
                          key={run.id}
                          className={`border rounded-lg p-3 ${
                            run.status === "COMPLETED"
                              ? "bg-green-50 border-green-200"
                              : run.status === "FAILED"
                              ? "bg-red-50 border-red-200"
                              : "bg-gray-50 border-gray-200"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <span className="font-medium">Run #{run.id}</span>
                              <span
                                className={`ml-2 px-2 py-1 rounded text-xs ${
                                  run.status === "COMPLETED"
                                    ? "bg-green-100 text-green-800"
                                    : run.status === "FAILED"
                                    ? "bg-red-100 text-red-800"
                                    : "bg-gray-100 text-gray-800"
                                }`}
                              >
                                {run.status}
                              </span>
                            </div>
                            <div className="text-sm text-gray-600">
                              {run.completed_segments || 0} /{" "}
                              {run.total_segments || 0} segments
                              {run.failed_segments > 0 && (
                                <span className="text-red-600 ml-2">
                                  ({run.failed_segments} failed)
                                </span>
                              )}
                            </div>
                          </div>
                          {run.error_message && (
                            <div className="mt-2 text-sm text-red-600">
                              Error: {run.error_message}
                            </div>
                          )}
                          <div className="mt-1 text-xs text-gray-500">
                            {run.status === "COMPLETED" && run.completed_at
                              ? `Completed: ${new Date(
                                  run.completed_at
                                ).toLocaleString()}`
                              : run.status === "RUNNING" && run.started_at
                              ? `Started: ${new Date(
                                  run.started_at
                                ).toLocaleString()}`
                              : run.status === "FAILED" && run.started_at
                              ? `Failed: ${new Date(
                                  run.started_at
                                ).toLocaleString()}`
                              : run.created_at
                              ? `Created: ${new Date(
                                  run.created_at
                                ).toLocaleString()}`
                              : "No timestamp available"}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {analysisRuns.length === 0 && !activeRun && (
                  <div className="text-center py-4 text-gray-500">
                    No analysis runs found. Click "Run Multi-Pass Analysis" to
                    start.
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

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
            <div className="bg-gradient-to-br from-indigo-50 to-purple-50 p-8 rounded-xl border border-indigo-200 shadow-lg">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-2xl font-bold text-indigo-900 flex items-center mb-2">
                    <BrainCircuit className="mr-3 h-7 w-7 text-indigo-600" />
                    Unified Document Analysis
                  </h3>
                  <p className="text-indigo-700 text-sm">
                    Complete analysis combining all document segments into a
                    comprehensive overview
                  </p>
                </div>
                <div className="flex items-center space-x-2">
                  <Badge
                    variant="secondary"
                    className="bg-indigo-100 text-indigo-800 px-3 py-1"
                  >
                    {Object.keys(consolidatedAnalysis).length} sections
                  </Badge>
                  <Badge
                    variant="outline"
                    className="bg-white text-indigo-700 border-indigo-300"
                  >
                    ✓ Complete
                  </Badge>
                </div>
              </div>

              <div className="max-h-96 overflow-y-auto">
                {renderStructuredData(consolidatedAnalysis)}
              </div>
            </div>
          ) : (
            <div className="text-center py-12 bg-gradient-to-br from-gray-50 to-blue-50 rounded-xl border border-gray-200">
              <div className="bg-blue-100 rounded-full p-4 w-20 h-20 mx-auto mb-6 flex items-center justify-center">
                <BrainCircuit className="h-10 w-10 text-blue-600" />
              </div>
              <h4 className="text-xl font-bold text-gray-900 mb-3">
                Consolidated View Ready
              </h4>
              <p className="text-gray-600 mb-4 max-w-md mx-auto">
                Generate a unified analysis that combines insights from all
                analyzed document segments into a comprehensive overview.
              </p>
              <div className="flex items-center justify-center space-x-2 text-sm text-blue-600">
                <CheckCircle className="h-4 w-4" />
                <span>All segments analyzed and ready for consolidation</span>
              </div>
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
