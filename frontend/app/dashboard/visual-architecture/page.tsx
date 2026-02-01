"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  GitBranch,
  FileText,
  Code,
  Link as LinkIcon,
  RefreshCw,
  Loader2,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Download,
} from "lucide-react";

interface ArchitectureNode {
  id: number;
  name: string;
  type: "document" | "code";
  links: number[];
}

export default function VisualArchitecturePage() {
  const [nodes, setNodes] = useState<ArchitectureNode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [zoomLevel, setZoomLevel] = useState(100);

  useEffect(() => {
    // Simulated data - in production, fetch from API
    const fetchData = async () => {
      const token = localStorage.getItem("accessToken");
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        // Fetch documents and code components to build the graph
        const [docsRes, codeRes] = await Promise.all([
          fetch("http://localhost:8000/api/v1/documents/", {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch("http://localhost:8000/api/v1/code-components/", {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);

        if (docsRes.ok && codeRes.ok) {
          const docs = await docsRes.json();
          const code = await codeRes.json();

          const docNodes: ArchitectureNode[] = docs.map((d: any) => ({
            id: d.id,
            name: d.filename,
            type: "document" as const,
            links: [],
          }));

          const codeNodes: ArchitectureNode[] = code.map((c: any) => ({
            id: c.id + 1000, // Offset to avoid ID collision
            name: c.name,
            type: "code" as const,
            links: [],
          }));

          setNodes([...docNodes, ...codeNodes]);
        }
      } catch (error) {
        console.error("Failed to fetch architecture data:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  const documentNodes = nodes.filter((n) => n.type === "document");
  const codeNodes = nodes.filter((n) => n.type === "code");

  if (isLoading) {
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
          <div className="p-2 bg-purple-100 dark:bg-purple-900 rounded-lg">
            <GitBranch className="w-6 h-6 text-purple-600 dark:text-purple-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold">Visual Architecture</h1>
              <Badge variant="secondary" className="bg-green-100 text-green-700">
                New
              </Badge>
            </div>
            <p className="text-muted-foreground">
              Visualize relationships between documents and code components
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
          <Button variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Documents</p>
                <p className="text-2xl font-bold">{documentNodes.length}</p>
              </div>
              <FileText className="h-8 w-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Code Components</p>
                <p className="text-2xl font-bold">{codeNodes.length}</p>
              </div>
              <Code className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Links</p>
                <p className="text-2xl font-bold">0</p>
              </div>
              <LinkIcon className="h-8 w-8 text-purple-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Zoom Controls */}
      <div className="flex items-center justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setZoomLevel(Math.max(50, zoomLevel - 10))}
        >
          <ZoomOut className="h-4 w-4" />
        </Button>
        <span className="text-sm font-medium w-16 text-center">{zoomLevel}%</span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setZoomLevel(Math.min(150, zoomLevel + 10))}
        >
          <ZoomIn className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="sm" onClick={() => setZoomLevel(100)}>
          <Maximize2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Architecture Visualization */}
      <Card className="min-h-[500px]">
        <CardHeader>
          <CardTitle>Dependency Graph</CardTitle>
          <CardDescription>
            Visual representation of document-to-code relationships
          </CardDescription>
        </CardHeader>
        <CardContent>
          {nodes.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-96 text-center">
              <GitBranch className="h-16 w-16 text-muted-foreground mb-4" />
              <h3 className="text-xl font-semibold">No Data Available</h3>
              <p className="text-muted-foreground mt-2 max-w-md">
                Upload documents and register code components to visualize the
                architecture of your project.
              </p>
            </div>
          ) : (
            <div
              className="relative border rounded-lg bg-gray-50 dark:bg-gray-900 min-h-[400px] overflow-hidden"
              style={{ transform: `scale(${zoomLevel / 100})`, transformOrigin: "top left" }}
            >
              {/* Document Nodes - Left Side */}
              <div className="absolute left-8 top-8 space-y-4">
                <h4 className="text-sm font-semibold text-gray-500 mb-2">Documents</h4>
                {documentNodes.map((node, idx) => (
                  <div
                    key={node.id}
                    className="flex items-center gap-2 px-4 py-3 bg-white dark:bg-gray-800 rounded-lg shadow-sm border hover:border-blue-400 cursor-pointer transition-colors"
                    style={{ marginTop: idx * 10 }}
                  >
                    <FileText className="h-4 w-4 text-blue-600" />
                    <span className="text-sm font-medium truncate max-w-[150px]">
                      {node.name}
                    </span>
                  </div>
                ))}
              </div>

              {/* Code Nodes - Right Side */}
              <div className="absolute right-8 top-8 space-y-4">
                <h4 className="text-sm font-semibold text-gray-500 mb-2">Code Components</h4>
                {codeNodes.map((node, idx) => (
                  <div
                    key={node.id}
                    className="flex items-center gap-2 px-4 py-3 bg-white dark:bg-gray-800 rounded-lg shadow-sm border hover:border-green-400 cursor-pointer transition-colors"
                    style={{ marginTop: idx * 10 }}
                  >
                    <Code className="h-4 w-4 text-green-600" />
                    <span className="text-sm font-medium truncate max-w-[150px]">
                      {node.name}
                    </span>
                  </div>
                ))}
              </div>

              {/* Center Instruction */}
              {documentNodes.length > 0 && codeNodes.length > 0 && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center text-muted-foreground">
                    <LinkIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">
                      Link documents to code components to see connections
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
