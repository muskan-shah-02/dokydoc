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
import { Label } from "@/components/ui/label";
import {
  Download,
  FileText,
  Code,
  FileJson,
  FileSpreadsheet,
  File,
  Loader2,
  CheckCircle,
  Package,
  Settings,
  BarChart3,
  Brain,
  AlertCircle,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

type ExportCategory = "documents" | "code" | "ontology" | "report";
type ExportFormat = "json" | "csv";

interface ExportOption {
  id: ExportCategory;
  name: string;
  description: string;
  icon: any;
  formats: ExportFormat[];
}

const EXPORT_OPTIONS: ExportOption[] = [
  {
    id: "documents",
    name: "Documents",
    description: "Export document analysis data including summaries and metadata",
    icon: FileText,
    formats: ["json", "csv"],
  },
  {
    id: "code",
    name: "Code Components",
    description: "Export code analysis results, costs, and component details",
    icon: Code,
    formats: ["json", "csv"],
  },
  {
    id: "ontology",
    name: "Ontology Graph",
    description: "Export concepts and relationships from the knowledge graph",
    icon: Brain,
    formats: ["json", "csv"],
  },
  {
    id: "report",
    name: "Full Report",
    description: "Generate a comprehensive analysis report with all data",
    icon: BarChart3,
    formats: ["json"],
  },
];

export default function ExportPage() {
  const [selectedCategory, setSelectedCategory] = useState<ExportCategory>("documents");
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>("json");
  const [isExporting, setIsExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [stats, setStats] = useState({ documents: 0, code: 0, concepts: 0, repos: 0 });

  useEffect(() => {
    const fetchStats = async () => {
      const token = localStorage.getItem("accessToken");
      if (!token) return;

      try {
        const [docsRes, reposRes] = await Promise.all([
          fetch(`${API_BASE_URL}/documents/`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch(`${API_BASE_URL}/repositories/`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);

        let docCount = 0;
        let repoCount = 0;

        if (docsRes.ok) {
          const docs = await docsRes.json();
          docCount = docs.length;
        }
        if (reposRes.ok) {
          const repos = await reposRes.json();
          repoCount = repos.length;
        }

        setStats({
          documents: docCount,
          code: repoCount,
          concepts: 0,
          repos: repoCount,
        });
      } catch (error) {
        console.error("Failed to fetch stats:", error);
      }
    };

    fetchStats();
  }, []);

  const handleExport = async () => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;

    setIsExporting(true);
    setExportSuccess(null);
    setExportError(null);

    try {
      let url: string;
      let filename: string;

      switch (selectedCategory) {
        case "documents":
          url = `${API_BASE_URL}/exports/documents?format=${selectedFormat}`;
          filename = `documents_export.${selectedFormat}`;
          break;
        case "code":
          url = `${API_BASE_URL}/exports/code?format=${selectedFormat}`;
          filename = `code_export.${selectedFormat}`;
          break;
        case "ontology":
          url = `${API_BASE_URL}/exports/ontology?format=${selectedFormat}`;
          filename = `ontology_export.${selectedFormat}`;
          break;
        case "report":
          url = `${API_BASE_URL}/exports/report`;
          filename = `dokydoc_report.json`;
          break;
        default:
          return;
      }

      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Export failed" }));
        throw new Error(err.detail || err.message || "Export failed");
      }

      // Handle CSV responses (streaming)
      if (selectedFormat === "csv" && selectedCategory !== "report") {
        const blob = await res.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = downloadUrl;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(downloadUrl);
      } else {
        // JSON response
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: "application/json",
        });
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = downloadUrl;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(downloadUrl);
      }

      setExportSuccess(`Exported ${selectedCategory} as ${selectedFormat.toUpperCase()}`);
      setTimeout(() => setExportSuccess(null), 5000);
    } catch (error: any) {
      setExportError(error.message || "Export failed");
      setTimeout(() => setExportError(null), 5000);
    } finally {
      setIsExporting(false);
    }
  };

  const selectedOption = EXPORT_OPTIONS.find((o) => o.id === selectedCategory);

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-indigo-100 dark:bg-indigo-900 rounded-lg">
            <Download className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Export Center</h1>
            <p className="text-muted-foreground">
              Export your documents, code analysis, ontology, and reports
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Documents</p>
                <p className="text-2xl font-bold">{stats.documents}</p>
              </div>
              <FileText className="h-8 w-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Repositories</p>
                <p className="text-2xl font-bold">{stats.repos}</p>
              </div>
              <Code className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Export Types</p>
                <p className="text-2xl font-bold">4</p>
              </div>
              <Package className="h-8 w-8 text-purple-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Formats</p>
                <p className="text-2xl font-bold">JSON, CSV</p>
              </div>
              <FileJson className="h-8 w-8 text-orange-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {exportSuccess && (
        <div className="flex items-center gap-2 p-4 rounded-lg border border-green-200 bg-green-50 dark:bg-green-950 dark:border-green-800">
          <CheckCircle className="h-5 w-5 text-green-600" />
          <span className="text-green-800 dark:text-green-200">{exportSuccess}</span>
        </div>
      )}

      {exportError && (
        <div className="flex items-center gap-2 p-4 rounded-lg border border-red-200 bg-red-50 dark:bg-red-950 dark:border-red-800">
          <AlertCircle className="h-5 w-5 text-red-600" />
          <span className="text-red-800 dark:text-red-200">{exportError}</span>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>What to Export</CardTitle>
              <CardDescription>
                Choose the data category you want to export
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {EXPORT_OPTIONS.map((option) => {
                  const Icon = option.icon;
                  const isSelected = selectedCategory === option.id;
                  return (
                    <div
                      key={option.id}
                      className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                        isSelected
                          ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20 shadow-sm"
                          : "border-gray-200 dark:border-gray-700 hover:border-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                      }`}
                      onClick={() => {
                        setSelectedCategory(option.id);
                        if (!option.formats.includes(selectedFormat)) {
                          setSelectedFormat(option.formats[0]);
                        }
                      }}
                    >
                      <div className="flex items-start gap-3">
                        <div className={`p-2 rounded-lg ${isSelected ? "bg-blue-100 dark:bg-blue-900" : "bg-gray-100 dark:bg-gray-800"}`}>
                          <Icon className={`h-5 w-5 ${isSelected ? "text-blue-600" : "text-gray-600"}`} />
                        </div>
                        <div>
                          <h3 className="font-medium">{option.name}</h3>
                          <p className="text-sm text-muted-foreground mt-1">
                            {option.description}
                          </p>
                          <div className="flex gap-1 mt-2">
                            {option.formats.map((f) => (
                              <Badge
                                key={f}
                                variant="secondary"
                                className="text-xs"
                              >
                                {f.toUpperCase()}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>

        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                Export Settings
              </CardTitle>
              <CardDescription>Configure export format</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedOption && selectedOption.formats.length > 1 && (
                <div>
                  <Label className="mb-2 block">Format</Label>
                  <div className="space-y-2">
                    {selectedOption.formats.map((format) => (
                      <div
                        key={format}
                        className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                          selectedFormat === format
                            ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                            : "hover:bg-gray-50 dark:hover:bg-gray-800"
                        }`}
                        onClick={() => setSelectedFormat(format)}
                      >
                        {format === "json" ? (
                          <FileJson className="h-5 w-5 text-muted-foreground" />
                        ) : (
                          <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
                        )}
                        <div>
                          <p className="font-medium">{format.toUpperCase()}</p>
                          <p className="text-xs text-muted-foreground">
                            {format === "json"
                              ? "Structured data format"
                              : "Spreadsheet-compatible"}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <Button
                className="w-full"
                size="lg"
                onClick={handleExport}
                disabled={isExporting}
              >
                {isExporting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Exporting...
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4 mr-2" />
                    Export {selectedOption?.name || ""} as{" "}
                    {selectedFormat.toUpperCase()}
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
