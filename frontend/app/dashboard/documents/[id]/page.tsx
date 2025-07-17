"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  FileText,
  Tag,
  GitCommit,
  Clock,
  AlertCircle,
  BrainCircuit,
  ListChecks,
} from "lucide-react";

// --- Interface Definitions ---
interface Document {
  id: number;
  filename: string;
  document_type: string;
  version: string;
  created_at: string;
  content: string | null;
  status: string | null;
  file_size_kb?: number | null; // Added from new version
}

interface AnalysisResult {
  id: number;
  analysis_type: string;
  // The result_data is expected to be a JSON object.
  // For "functional_requirements", it should have a "requirements" key.
  result_data: {
    requirements?: string[];
    [key: string]: any; // Allow for other types of analysis results
  };
  created_at: string;
}

// --- AI Analysis Display Component ---
const AnalysisResultCard = ({ result }: { result: AnalysisResult }) => {
  // Specifically handle the "functional_requirements" analysis type
  if (result.analysis_type !== "functional_requirements") {
    return null; // Don't render cards for other analysis types for now
  }

  const requirements = result.result_data?.requirements || [];

  return (
    <div className="bg-blue-50/50 p-4 rounded-lg border border-blue-200">
      <h3 className="font-semibold text-blue-900 flex items-center mb-2">
        <ListChecks className="h-5 w-5 mr-2" />
        Functional Requirements
      </h3>
      {requirements.length > 0 ? (
        <ul className="list-disc pl-5 space-y-1 text-sm text-gray-700">
          {requirements.map((req, index) => (
            <li key={index}>{req}</li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-gray-500">
          No specific functional requirements were extracted by the AI.
        </p>
      )}
    </div>
  );
};

// --- Main Document Detail Page Component ---
export default function DocumentDetailPage() {
  const [document, setDocument] = useState<Document | null>(null);
  const [analysisResults, setAnalysisResults] = useState<AnalysisResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [documentId, setDocumentId] = useState<string | null>(null);

  // Get the document ID from the URL
  useEffect(() => {
    if (typeof window !== "undefined") {
      const pathParts = window.location.pathname.split("/");
      const id = pathParts.pop() || "";
      setDocumentId(id);
    }
  }, []);

  // Fetch both document details and any existing analysis results
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
      // Fetch document details
      const docRes = await fetch(
        `http://localhost:8000/api/v1/documents/${documentId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!docRes.ok) {
        const errData = await docRes.json();
        throw new Error(errData.detail || "Failed to fetch document details.");
      }

      const docData: Document = await docRes.json();
      setDocument(docData);

      // Fetch analysis results
      const analysisRes = await fetch(
        `http://localhost:8000/api/v1/analysis/document/${documentId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!analysisRes.ok) {
        // If analysis endpoint fails, just log it but don't throw error
        console.warn("Failed to fetch analysis results");
        setAnalysisResults([]);
      } else {
        const analysisData: AnalysisResult[] = await analysisRes.json();
        setAnalysisResults(analysisData);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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
        "Analysis has been triggered! Results will appear here shortly. Please refresh the page in a moment."
      );

      // Optionally, refresh the data after a short delay
      setTimeout(() => {
        fetchData();
      }, 2000);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsAnalyzing(false);
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

      {/* AI Analysis Section */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center">
            <BrainCircuit className="mr-3 h-6 w-6 text-blue-600" />
            AI Analysis
          </h2>
          <Button
            onClick={handleRunAnalysis}
            disabled={isAnalyzing}
            className="bg-blue-600 hover:bg-blue-700"
          >
            {isAnalyzing
              ? "Analyzing..."
              : "Run Functional Requirement Analysis"}
          </Button>
        </div>
        <div className="space-y-4">
          {analysisResults.length > 0 ? (
            analysisResults.map((result) => (
              <AnalysisResultCard key={result.id} result={result} />
            ))
          ) : (
            <div className="text-center py-8 text-gray-500">
              <BrainCircuit className="h-12 w-12 mx-auto mb-3 text-gray-400" />
              <p>
                No analysis has been run yet. Click the button above to generate
                AI insights.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Extracted Content Section */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <h2 className="text-xl font-semibold mb-4">Raw Extracted Content</h2>
        <div className="prose max-w-none bg-gray-50 p-4 rounded-md h-96 overflow-y-auto border">
          <pre className="whitespace-pre-wrap break-words text-sm">
            {document.content ||
              "No content was extracted, or parsing is still in progress."}
          </pre>
        </div>
      </div>
    </div>
  );
}
