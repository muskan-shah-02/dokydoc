/*
  This is the content for your NEW file at:
  frontend/app/dashboard/documents/[id]/page.tsx
*/
"use client";

import React, { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { FileText, Tag, GitCommit, Clock, AlertCircle } from "lucide-react";

// Define the shape of a single document object for TypeScript
interface Document {
  id: number;
  filename: string;
  document_type: string;
  version: string;
  created_at: string;
  content: string | null;
  status: string | null;
  file_size_kb: number | null;
}

export default function DocumentDetailPage() {
  const [document, setDocument] = useState<Document | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);

  // Get the document ID from the URL on the client side
  useEffect(() => {
    if (typeof window !== "undefined") {
      const pathParts = window.location.pathname.split("/");
      const id = pathParts.pop() || "";
      setDocumentId(id);
    }
  }, []);

  // Fetch the document data when the ID is available
  useEffect(() => {
    if (!documentId) return;

    const fetchDocument = async () => {
      setIsLoading(true);
      setError(null);
      const token = localStorage.getItem("accessToken");

      if (!token) {
        setError("Authentication token not found.");
        setIsLoading(false);
        return;
      }

      try {
        const response = await fetch(
          `http://localhost:8000/api/v1/documents/${documentId}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(
            errData.detail || "Failed to fetch document details."
          );
        }
        const data: Document = await response.json();
        setDocument(data);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDocument();
  }, [documentId]);

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

      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <h2 className="text-xl font-semibold mb-4">Extracted Content</h2>
        <div className="prose max-w-none bg-gray-50 p-4 rounded-md h-96 overflow-y-auto border">
          <pre className="whitespace-pre-wrap break-words">
            {document.content ||
              "No content was extracted, or parsing is still in progress."}
          </pre>
        </div>
      </div>
    </div>
  );
}
