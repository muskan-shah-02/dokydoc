// This is the updated content for your file at:
// frontend/app/dashboard/code/page.tsx

"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Code2,
  Plus,
  FileCode,
  Globe,
  GitBranch,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  Search,
  Filter,
  RefreshCw,
  AlertCircle,
  Trash2,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useRouter } from "next/navigation";

interface CodeComponent {
  id: number;
  name: string;
  component_type: string;
  location: string;
  version: string;
  analysis_status: "pending" | "processing" | "completed" | "failed";
}

export default function CodePage() {
  const [components, setComponents] = useState<CodeComponent[]>([]);
  const [filteredComponents, setFilteredComponents] = useState<CodeComponent[]>(
    []
  );
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [newComponent, setNewComponent] = useState({
    name: "",
    component_type: "File",
    location: "",
    version: "",
  });
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  const router = useRouter();

  const fetchComponents = async (showRefreshing = false) => {
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setIsLoading(false);
      return;
    }
    if (showRefreshing) setIsRefreshing(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/code-components/", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setComponents(data);
      } else {
        setComponents([]);
      }
    } catch (error) {
      console.error("Failed to fetch components:", error);
      setComponents([]);
    } finally {
      setIsLoading(false);
      if (showRefreshing) setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchComponents();
    const interval = setInterval(() => fetchComponents(), 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    let filtered = components;
    if (searchTerm) {
      filtered = filtered.filter(
        (c) =>
          c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          c.location.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    if (statusFilter !== "all") {
      filtered = filtered.filter((c) => c.analysis_status === statusFilter);
    }
    setFilteredComponents(filtered);
  }, [components, searchTerm, statusFilter]);

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setNewComponent((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmissionError(null);
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setSubmissionError("Authentication error. Please log in again.");
      setIsSubmitting(false);
      return;
    }
    try {
      const res = await fetch("http://localhost:8000/api/v1/code-components/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(newComponent),
      });
      if (res.ok) {
        await fetchComponents(true);
        setIsDialogOpen(false);
        setNewComponent({
          name: "",
          component_type: "File",
          location: "",
          version: "",
        });
      } else {
        const errorData = await res.json();
        const errorMessage =
          errorData.detail?.[0]?.msg ||
          errorData.detail ||
          "Failed to create component.";
        throw new Error(errorMessage);
      }
    } catch (error: any) {
      setSubmissionError(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  // --- NEW: Delete Handler for the main dashboard ---
  const handleDelete = async (id: number) => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    try {
      const res = await fetch(
        `http://localhost:8000/api/v1/code-components/${id}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (res.ok) {
        // Refresh the component list on successful deletion
        fetchComponents(true);
      } else {
        console.error("Failed to delete component");
      }
    } catch (error) {
      console.error("Error deleting component:", error);
    }
  };

  const getStatusBadgeVariant = (status: CodeComponent["analysis_status"]) => {
    switch (status) {
      case "completed":
        return "success";
      case "processing":
        return "default";
      case "failed":
        return "destructive";
      default:
        return "secondary";
    }
  };

  const getStatusIcon = (status: CodeComponent["analysis_status"]) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      case "processing":
        return <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />;
      case "failed":
        return <XCircle className="w-4 h-4 text-red-600" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const handleRowClick = (id: number) => {
    router.push(`/dashboard/code/${id}`);
  };

  const statusCounts = {
    total: components.length,
    completed: components.filter((c) => c.analysis_status === "completed")
      .length,
    processing: components.filter((c) => c.analysis_status === "processing")
      .length,
    failed: components.filter((c) => c.analysis_status === "failed").length,
    pending: components.filter((c) => c.analysis_status === "pending").length,
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header and Stats Cards remain the same */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
            <Code2 className="w-6 h-6 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Code Component Library</h1>
            <p className="text-muted-foreground">
              Manage and analyze your code components
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchComponents(true)}
            disabled={isRefreshing}
          >
            <RefreshCw
              className={`w-4 h-4 mr-2 ${isRefreshing ? "animate-spin" : ""}`}
            />{" "}
            Refresh
          </Button>
          <Dialog
            open={isDialogOpen}
            onOpenChange={(open) => {
              setIsDialogOpen(open);
              setSubmissionError(null);
            }}
          >
            <DialogTrigger asChild>
              <Button
                onClick={() => setIsDialogOpen(true)}
                className="bg-blue-600 hover:bg-blue-700"
              >
                <Plus className="w-4 h-4 mr-2" /> Add Component
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle className="flex items-center space-x-2">
                  <FileCode className="w-5 h-5" />
                  <span>Register New Component</span>
                </DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <Label htmlFor="name" className="text-sm font-medium">
                    Component Name
                  </Label>
                  <Input
                    id="name"
                    name="name"
                    value={newComponent.name}
                    onChange={handleInputChange}
                    placeholder="e.g., Authentication Service"
                    className="mt-1"
                    required
                  />
                </div>
                <div>
                  <Label
                    htmlFor="component_type"
                    className="text-sm font-medium"
                  >
                    Component Type
                  </Label>
                  <select
                    id="component_type"
                    name="component_type"
                    value={newComponent.component_type}
                    onChange={handleInputChange}
                    className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm mt-1"
                  >
                    <option value="File">File</option>
                    <option value="Repository">Repository</option>
                    <option value="Class">Class</option>
                    <option value="Function">Function</option>
                  </select>
                </div>
                <div>
                  <Label htmlFor="location" className="text-sm font-medium">
                    Location URL
                  </Label>
                  <div className="relative mt-1">
                    <Globe className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                    <Input
                      id="location"
                      name="location"
                      value={newComponent.location}
                      onChange={handleInputChange}
                      placeholder="https://..."
                      className="pl-10"
                      required
                    />
                  </div>
                </div>
                <div>
                  <Label htmlFor="version" className="text-sm font-medium">
                    Version / Git Hash
                  </Label>
                  <div className="relative mt-1">
                    <GitBranch className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                    <Input
                      id="version"
                      name="version"
                      value={newComponent.version}
                      onChange={handleInputChange}
                      placeholder="v1.0.0 or commit hash"
                      className="pl-10"
                      required
                    />
                  </div>
                </div>
                {submissionError && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Registration Failed</AlertTitle>
                    <AlertDescription>{submissionError}</AlertDescription>
                  </Alert>
                )}
                <div className="flex space-x-2 pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsDialogOpen(false)}
                    className="flex-1"
                    disabled={isSubmitting}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    className="flex-1 bg-blue-600 hover:bg-blue-700"
                    disabled={isSubmitting}
                  >
                    {isSubmitting && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    {isSubmitting ? "Registering..." : "Register Component"}
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{statusCounts.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-green-600">
              Completed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {statusCounts.completed}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-blue-600">
              Processing
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {statusCounts.processing}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-red-600">
              Failed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {statusCounts.failed}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              Pending
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-500">
              {statusCounts.pending}
            </div>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search components..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-muted-foreground" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="all">All Statuses</option>
                <option value="completed">Completed</option>
                <option value="processing">Processing</option>
                <option value="failed">Failed</option>
                <option value="pending">Pending</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Components ({filteredComponents.length})</CardTitle>
          <CardDescription>
            Manage your registered code components
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredComponents.length === 0 ? (
            <div className="text-center py-8">
              <Code2 className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">
                {components.length === 0
                  ? "No components registered yet"
                  : "No components match your filters"}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredComponents.map((component) => (
                  <TableRow key={component.id} className="group">
                    <TableCell
                      onClick={() => handleRowClick(component.id)}
                      className="font-medium cursor-pointer"
                    >
                      {component.name}
                    </TableCell>
                    <TableCell
                      onClick={() => handleRowClick(component.id)}
                      className="cursor-pointer"
                    >
                      <div className="flex items-center space-x-2">
                        <FileCode className="w-4 h-4 text-muted-foreground" />
                        <span>{component.component_type}</span>
                      </div>
                    </TableCell>
                    <TableCell
                      onClick={() => handleRowClick(component.id)}
                      className="max-w-xs truncate cursor-pointer"
                      title={component.location}
                    >
                      {component.location}
                    </TableCell>
                    <TableCell
                      onClick={() => handleRowClick(component.id)}
                      className="font-mono text-sm cursor-pointer"
                    >
                      {component.version}
                    </TableCell>
                    <TableCell
                      onClick={() => handleRowClick(component.id)}
                      className="cursor-pointer"
                    >
                      <div className="flex items-center space-x-2">
                        {getStatusIcon(component.analysis_status)}
                        <Badge
                          variant={getStatusBadgeVariant(
                            component.analysis_status
                          )}
                        >
                          {component.analysis_status}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      {/* --- NEW: Delete Button with Confirmation --- */}
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="opacity-0 group-hover:opacity-100"
                          >
                            <Trash2 className="w-4 h-4 text-destructive" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>
                              Are you absolutely sure?
                            </AlertDialogTitle>
                            <AlertDialogDescription>
                              This will permanently delete the "{component.name}
                              " component and its analysis data.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => handleDelete(component.id)}
                            >
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
