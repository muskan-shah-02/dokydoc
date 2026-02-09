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
import { Checkbox } from "@/components/ui/checkbox";
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
} from "lucide-react";

interface ExportableItem {
  id: number;
  name: string;
  type: "document" | "code";
  size?: string;
}

type ExportFormat = "json" | "csv" | "pdf" | "markdown";

export default function ExportPage() {
  const [items, setItems] = useState<ExportableItem[]>([]);
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>("json");
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState(false);

  const exportFormats = [
    {
      id: "json" as ExportFormat,
      name: "JSON",
      icon: FileJson,
      description: "Machine-readable format for data interchange",
    },
    {
      id: "csv" as ExportFormat,
      name: "CSV",
      icon: FileSpreadsheet,
      description: "Spreadsheet-compatible format",
    },
    {
      id: "pdf" as ExportFormat,
      name: "PDF",
      icon: File,
      description: "Printable document format",
    },
    {
      id: "markdown" as ExportFormat,
      name: "Markdown",
      icon: FileText,
      description: "Documentation-friendly format",
    },
  ];

  useEffect(() => {
    const fetchExportableItems = async () => {
      const token = localStorage.getItem("accessToken");
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const [docsRes, codeRes] = await Promise.all([
          fetch("http://localhost:8000/api/v1/documents/", {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch("http://localhost:8000/api/v1/code-components/", {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);

        const exportableItems: ExportableItem[] = [];

        if (docsRes.ok) {
          const docs = await docsRes.json();
          docs.forEach((doc: any) => {
            exportableItems.push({
              id: doc.id,
              name: doc.filename,
              type: "document",
              size: `${Math.floor(Math.random() * 500) + 50} KB`,
            });
          });
        }

        if (codeRes.ok) {
          const code = await codeRes.json();
          code.forEach((comp: any) => {
            exportableItems.push({
              id: comp.id + 10000,
              name: comp.name,
              type: "code",
              size: `${Math.floor(Math.random() * 200) + 20} KB`,
            });
          });
        }

        setItems(exportableItems);
      } catch (error) {
        console.error("Failed to fetch exportable items:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchExportableItems();
  }, []);

  const handleSelectItem = (id: number) => {
    const newSelection = new Set(selectedItems);
    if (newSelection.has(id)) {
      newSelection.delete(id);
    } else {
      newSelection.add(id);
    }
    setSelectedItems(newSelection);
  };

  const handleSelectAll = () => {
    if (selectedItems.size === items.length) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set(items.map((item) => item.id)));
    }
  };

  const handleExport = async () => {
    if (selectedItems.size === 0) return;

    setIsExporting(true);
    setExportSuccess(false);

    // Simulate export process
    await new Promise((resolve) => setTimeout(resolve, 2000));

    setIsExporting(false);
    setExportSuccess(true);

    // Reset success message after 3 seconds
    setTimeout(() => setExportSuccess(false), 3000);
  };

  const documentItems = items.filter((i) => i.type === "document");
  const codeItems = items.filter((i) => i.type === "code");

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
          <div className="p-2 bg-indigo-100 dark:bg-indigo-900 rounded-lg">
            <Download className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Export Center</h1>
            <p className="text-muted-foreground">
              Export your documents and analysis results
            </p>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Documents</p>
                <p className="text-2xl font-bold">{documentItems.length}</p>
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
                <p className="text-2xl font-bold">{codeItems.length}</p>
              </div>
              <Code className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Selected</p>
                <p className="text-2xl font-bold">{selectedItems.size}</p>
              </div>
              <Package className="h-8 w-8 text-purple-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Item Selection */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Select Items to Export</CardTitle>
                  <CardDescription>
                    Choose documents and code components for export
                  </CardDescription>
                </div>
                <Button variant="outline" size="sm" onClick={handleSelectAll}>
                  {selectedItems.size === items.length ? "Deselect All" : "Select All"}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {items.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Package className="h-16 w-16 text-muted-foreground mb-4" />
                  <h3 className="text-xl font-semibold">No Items Available</h3>
                  <p className="text-muted-foreground mt-2">
                    Upload documents or register code components to export.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Documents Section */}
                  {documentItems.length > 0 && (
                    <div>
                      <h4 className="font-medium mb-2 flex items-center gap-2">
                        <FileText className="h-4 w-4 text-blue-600" />
                        Documents
                      </h4>
                      <div className="space-y-2">
                        {documentItems.map((item) => (
                          <div
                            key={item.id}
                            className={`flex items-center justify-between p-3 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors ${
                              selectedItems.has(item.id) ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20" : ""
                            }`}
                            onClick={() => handleSelectItem(item.id)}
                          >
                            <div className="flex items-center gap-3">
                              <Checkbox
                                checked={selectedItems.has(item.id)}
                                onCheckedChange={() => handleSelectItem(item.id)}
                              />
                              <FileText className="h-4 w-4 text-blue-600" />
                              <span className="font-medium">{item.name}</span>
                            </div>
                            <span className="text-sm text-muted-foreground">{item.size}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Code Components Section */}
                  {codeItems.length > 0 && (
                    <div>
                      <h4 className="font-medium mb-2 flex items-center gap-2">
                        <Code className="h-4 w-4 text-green-600" />
                        Code Components
                      </h4>
                      <div className="space-y-2">
                        {codeItems.map((item) => (
                          <div
                            key={item.id}
                            className={`flex items-center justify-between p-3 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors ${
                              selectedItems.has(item.id) ? "border-green-500 bg-green-50 dark:bg-green-900/20" : ""
                            }`}
                            onClick={() => handleSelectItem(item.id)}
                          >
                            <div className="flex items-center gap-3">
                              <Checkbox
                                checked={selectedItems.has(item.id)}
                                onCheckedChange={() => handleSelectItem(item.id)}
                              />
                              <Code className="h-4 w-4 text-green-600" />
                              <span className="font-medium">{item.name}</span>
                            </div>
                            <span className="text-sm text-muted-foreground">{item.size}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Export Options */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                Export Options
              </CardTitle>
              <CardDescription>Configure your export settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Format Selection */}
              <div>
                <Label className="mb-2 block">Export Format</Label>
                <div className="space-y-2">
                  {exportFormats.map((format) => {
                    const Icon = format.icon;
                    return (
                      <div
                        key={format.id}
                        className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                          selectedFormat === format.id
                            ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                            : "hover:bg-gray-50 dark:hover:bg-gray-800"
                        }`}
                        onClick={() => setSelectedFormat(format.id)}
                      >
                        <Icon className="h-5 w-5 text-muted-foreground mt-0.5" />
                        <div>
                          <p className="font-medium">{format.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {format.description}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Export Button */}
              <Button
                className="w-full"
                size="lg"
                onClick={handleExport}
                disabled={selectedItems.size === 0 || isExporting}
              >
                {isExporting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Exporting...
                  </>
                ) : exportSuccess ? (
                  <>
                    <CheckCircle className="h-4 w-4 mr-2" />
                    Exported Successfully
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4 mr-2" />
                    Export {selectedItems.size} Item(s)
                  </>
                )}
              </Button>

              {selectedItems.size === 0 && (
                <p className="text-sm text-muted-foreground text-center">
                  Select at least one item to export
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
