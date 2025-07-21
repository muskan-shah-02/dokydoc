// This is the new content for your file at:
// frontend/app/dashboard/code/[id]/page.tsx

"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
// --- FIX: Import AlertCircle from lucide-react ---
import {
  Terminal,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  Globe,
  GitBranch,
  AlertCircle,
} from "lucide-react";

// The full interface for a single component, including the new analysis fields.
interface CodeComponentDetail {
  id: number;
  name: string;
  component_type: string;
  location: string;
  version: string;
  summary: string | null;
  structured_analysis: Record<string, any> | null;
  analysis_status: "pending" | "processing" | "completed" | "failed";
}

export default function CodeComponentDetailPage() {
  const params = useParams();
  const id = params.id;

  const [component, setComponent] = useState<CodeComponentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const getStatusIcon = (status: CodeComponentDetail["analysis_status"]) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case "processing":
        return <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />;
      case "failed":
        return <XCircle className="w-5 h-5 text-red-600" />;
      default:
        return <Clock className="w-5 h-5 text-gray-500" />;
    }
  };

  useEffect(() => {
    if (!id) return;

    const fetchComponentDetail = async () => {
      const token = localStorage.getItem("accessToken");
      if (!token) {
        setError("Authentication token not found. Please log in again.");
        setLoading(false);
        return;
      }

      try {
        const res = await fetch(
          `http://localhost:8000/api/v1/code-components/${id}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );

        if (!res.ok) {
          const errorData = await res.json();
          throw new Error(
            errorData.detail ||
              `Failed to fetch component details: ${res.statusText}`
          );
        }
        const data = await res.json();
        setComponent(data);
        setError(null);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchComponentDetail();

    const interval = setInterval(() => {
      if (
        component &&
        (component.analysis_status === "pending" ||
          component.analysis_status === "processing")
      ) {
        fetchComponentDetail();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [id, component?.analysis_status]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!component) {
    return <div className="p-6">Component not found.</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">{component.name}</h1>
          <p className="text-lg text-muted-foreground">
            {component.component_type}
          </p>
        </div>
        <div className="flex items-center space-x-2 p-2 bg-muted rounded-lg">
          {getStatusIcon(component.analysis_status)}
          <span className="font-semibold capitalize">
            {component.analysis_status}
          </span>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>AI-Generated Summary</CardTitle>
            <CardDescription>
              A high-level overview of the code's purpose and functionality.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground italic">
              {component.summary ||
                "No summary available. Analysis may be pending or failed."}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Component Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="flex items-center">
              <Globe className="w-4 h-4 mr-3 text-muted-foreground" />
              <span className="truncate" title={component.location}>
                {component.location}
              </span>
            </div>
            <div className="flex items-center">
              <GitBranch className="w-4 h-4 mr-3 text-muted-foreground" />
              <span className="font-mono">{component.version}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Structured Analysis</CardTitle>
          <CardDescription>
            Detailed insights extracted from the source code by the AI.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {component.structured_analysis ? (
            <pre className="p-4 bg-secondary rounded-md overflow-x-auto text-sm">
              {JSON.stringify(component.structured_analysis, null, 2)}
            </pre>
          ) : (
            <Alert>
              <Terminal className="h-4 w-4" />
              <AlertTitle>No Structured Data</AlertTitle>
              <AlertDescription>
                Structured analysis data is not available for this component.
                The analysis might be pending or may have failed.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
