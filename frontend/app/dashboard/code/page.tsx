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
} from "lucide-react";
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
    component_type: "Repository",
    location: "",
    version: "",
  });
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const router = useRouter();

  const fetchComponents = async (showRefreshing = false) => {
    if (showRefreshing) setIsRefreshing(true);

    try {
      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("accessToken")
          : null;
      if (!token) {
        console.warn("No access token found");
        setComponents([]);
        setFilteredComponents([]);
        setIsLoading(false);
        return;
      }

      const res = await fetch("http://localhost:8000/api/v1/code-components/", {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        const data = await res.json();
        setComponents(data);
        setFilteredComponents(data);
      } else {
        console.error("API request failed:", res.status, res.statusText);
        const errorData = await res.json().catch(() => ({}));
        console.error("Error details:", errorData);
        setComponents([]);
        setFilteredComponents([]);
      }
    } catch (error) {
      console.error("Failed to fetch components:", error);
      setComponents([]);
      setFilteredComponents([]);
    } finally {
      setIsLoading(false);
      if (showRefreshing) setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchComponents();
    const interval = setInterval(() => fetchComponents(), 10000);

    // Set a timeout to force loading to false if it takes too long
    const timeout = setTimeout(() => {
      if (isLoading) {
        console.warn("Loading timeout reached");
        setIsLoading(false);
      }
    }, 5000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, []);

  // Filter components based on search and status
  useEffect(() => {
    let filtered = components;

    if (searchTerm) {
      filtered = filtered.filter(
        (component) =>
          component.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          component.location.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    if (statusFilter !== "all") {
      filtered = filtered.filter(
        (component) => component.analysis_status === statusFilter
      );
    }

    setFilteredComponents(filtered);
  }, [components, searchTerm, statusFilter]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setNewComponent((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate all fields are filled
    if (!newComponent.name || !newComponent.location || !newComponent.version) {
      console.error("All fields are required");
      return;
    }

    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("accessToken")
        : null;
    if (!token) {
      console.error("No access token found");
      return;
    }

    try {
      console.log("Submitting component:", newComponent);

      const res = await fetch("http://localhost:8000/api/v1/code-components/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(newComponent),
      });

      console.log("Response status:", res.status);

      if (res.ok) {
        const responseData = await res.json();
        console.log("Component registered successfully:", responseData);
        await fetchComponents();
        setIsDialogOpen(false);
        setNewComponent({
          name: "",
          component_type: "Repository",
          location: "",
          version: "",
        });
      } else {
        const errorData = await res.json().catch(() => ({}));
        console.error("Failed to create component:", res.status, errorData);
      }
    } catch (error) {
      console.error("Error creating component:", error);
    }
  };

  const getStatusBadgeVariant = (status: CodeComponent["analysis_status"]) => {
    switch (status) {
      case "completed":
        return "default";
      case "processing":
        return "secondary";
      case "failed":
        return "destructive";
      case "pending":
      default:
        return "outline";
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
      case "pending":
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const handleRowClick = (id: number) => {
    router.push(`/dashboard/code/${id}`);
  };

  const getStatusCounts = () => {
    return {
      total: components.length,
      completed: components.filter((c) => c.analysis_status === "completed")
        .length,
      processing: components.filter((c) => c.analysis_status === "processing")
        .length,
      failed: components.filter((c) => c.analysis_status === "failed").length,
      pending: components.filter((c) => c.analysis_status === "pending").length,
    };
  };

  const statusCounts = getStatusCounts();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center space-x-2">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span className="text-muted-foreground">Loading components...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header Section */}
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
            />
            Refresh
          </Button>

          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button
                onClick={() => setIsDialogOpen(true)}
                className="bg-blue-600 hover:bg-blue-700"
              >
                <Plus className="w-4 h-4 mr-2" />
                Add Component
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
                  <Label htmlFor="location" className="text-sm font-medium">
                    Repository URL
                  </Label>
                  <div className="relative mt-1">
                    <Globe className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                    <Input
                      id="location"
                      name="location"
                      value={newComponent.location}
                      onChange={handleInputChange}
                      placeholder="https://github.com/username/repo"
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
                    onChange={(e) =>
                      setNewComponent((prev) => ({
                        ...prev,
                        component_type: e.target.value,
                      }))
                    }
                    className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm mt-1"
                  >
                    <option value="Repository">Repository</option>
                    <option value="File">File</option>
                    <option value="Class">Class</option>
                    <option value="Function">Function</option>
                  </select>
                </div>
                <div className="flex space-x-2 pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsDialogOpen(false)}
                    className="flex-1"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    className="flex-1 bg-blue-600 hover:bg-blue-700"
                  >
                    Register Component
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Stats Cards */}
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

      {/* Filters */}
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
                <option value="all">All Status</option>
                <option value="completed">Completed</option>
                <option value="processing">Processing</option>
                <option value="failed">Failed</option>
                <option value="pending">Pending</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Components Table */}
      <Card>
        <CardHeader>
          <CardTitle>Components ({filteredComponents.length})</CardTitle>
          <CardDescription>
            Click on any row to view detailed analysis
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
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredComponents.map((component) => (
                  <TableRow
                    key={component.id}
                    onClick={() => handleRowClick(component.id)}
                    className="cursor-pointer hover:bg-muted/50 transition-colors"
                  >
                    <TableCell className="font-medium">
                      {component.name}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        <FileCode className="w-4 h-4 text-muted-foreground" />
                        <span>{component.component_type}</span>
                      </div>
                    </TableCell>
                    <TableCell
                      className="max-w-xs truncate"
                      title={component.location}
                    >
                      {component.location}
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {component.version}
                    </TableCell>
                    <TableCell>
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
