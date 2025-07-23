// This is the updated content for your file at:
// frontend/app/dashboard/code/[id]/page.tsx

"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  Trash2,
} from "lucide-react";

// --- NEW: Import our specialized analysis view components ---
import { RepositoryAnalysisView } from "@/components/analysis/RepositoryAnalysisView";
import { FileAnalysisView } from "@/components/analysis/FileAnalysisView";

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
  const router = useRouter();
  const id = params.id;

  const [component, setComponent] = useState<CodeComponentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

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

  const handleDelete = async () => {
    setIsDeleting(true);
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setError("Authentication token not found.");
      setIsDeleting(false);
      return;
    }
    try {
      const res = await fetch(
        `http://localhost:8000/api/v1/code-components/${id}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to delete component.");
      }
      router.push("/dashboard/code");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsDeleting(false);
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

  // --- NEW: Component to intelligently render the correct analysis view ---
  const AnalysisResult = () => {
    if (
      component?.analysis_status !== "completed" ||
      !component?.structured_analysis
    ) {
      return (
        <Card>
          <CardHeader>
            <CardTitle>Analysis In Progress</CardTitle>
            <CardDescription>
              The AI analysis for this component is not yet complete. The status
              is currently: {component?.analysis_status}. This page will
              automatically refresh when the analysis is done.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center p-8">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          </CardContent>
        </Card>
      );
    }

    switch (component.component_type) {
      case "Repository":
        return (
          <RepositoryAnalysisView analysis={component.structured_analysis} />
        );
      case "File":
      case "Class":
      case "Function":
        return (
          <FileAnalysisView
            analysis={component.structured_analysis}
            fileName={component.name}
          />
        );
      default:
        return (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Unsupported Component Type</AlertTitle>
            <AlertDescription>
              A detailed view for component type "{component.component_type}"
              has not been implemented yet.
            </AlertDescription>
          </Alert>
        );
    }
  };

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
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 p-2 bg-muted rounded-lg">
            {getStatusIcon(component.analysis_status)}
            <span className="font-semibold capitalize">
              {component.analysis_status}
            </span>
          </div>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="icon">
                <Trash2 className="w-4 h-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                <AlertDialogDescription>
                  This action cannot be undone. This will permanently delete the
                  code component and all of its associated data.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleDelete} disabled={isDeleting}>
                  {isDeleting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Continue
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>AI-Generated Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground italic">
            {component.summary ||
              "No summary available. Analysis may be pending or failed."}
          </p>
        </CardContent>
      </Card>

      {/* --- RENDER THE INTELLIGENT ANALYSIS COMPONENT --- */}
      <AnalysisResult />
    </div>
  );
}
