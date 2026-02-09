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
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ShieldCheck,
  Search,
  Filter,
  RefreshCw,
  Loader2,
  User,
  FileText,
  Code,
  Settings,
  LogIn,
  LogOut,
  Edit,
  Trash2,
  Plus,
  Eye,
  Download,
  Calendar,
} from "lucide-react";

interface AuditEvent {
  id: number;
  timestamp: string;
  user: {
    email: string;
    role: string;
  };
  action: string;
  actionType: "create" | "read" | "update" | "delete" | "login" | "logout" | "export";
  resource: string;
  resourceType: "document" | "code" | "user" | "settings" | "auth";
  ipAddress: string;
  details?: string;
}

export default function AuditTrailPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [filteredEvents, setFilteredEvents] = useState<AuditEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [actionFilter, setActionFilter] = useState<string>("all");

  useEffect(() => {
    // Simulate fetching audit events
    const fetchAuditEvents = async () => {
      const token = localStorage.getItem("accessToken");
      if (!token) {
        setIsLoading(false);
        return;
      }

      // In production, fetch from /api/v1/audit-logs endpoint
      // For now, generate sample data based on actual user activity
      try {
        const [docsRes, codeRes] = await Promise.all([
          fetch("http://localhost:8000/api/v1/documents/", {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch("http://localhost:8000/api/v1/code-components/", {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);

        const auditEvents: AuditEvent[] = [];
        let eventId = 1;

        // Add login event
        auditEvents.push({
          id: eventId++,
          timestamp: new Date(Date.now() - 60000).toISOString(),
          user: { email: "user@example.com", role: "Admin" },
          action: "User logged in",
          actionType: "login",
          resource: "Authentication",
          resourceType: "auth",
          ipAddress: "192.168.1.100",
        });

        if (docsRes.ok) {
          const docs = await docsRes.json();
          docs.forEach((doc: any) => {
            auditEvents.push({
              id: eventId++,
              timestamp: doc.created_at || new Date().toISOString(),
              user: { email: "user@example.com", role: "Admin" },
              action: `Uploaded document: ${doc.filename}`,
              actionType: "create",
              resource: doc.filename,
              resourceType: "document",
              ipAddress: "192.168.1.100",
              details: `Document type: ${doc.document_type}, Version: ${doc.version}`,
            });

            if (doc.status === "completed") {
              auditEvents.push({
                id: eventId++,
                timestamp: doc.created_at || new Date().toISOString(),
                user: { email: "system@dokydoc.com", role: "System" },
                action: `Completed analysis for: ${doc.filename}`,
                actionType: "update",
                resource: doc.filename,
                resourceType: "document",
                ipAddress: "127.0.0.1",
              });
            }
          });
        }

        if (codeRes.ok) {
          const code = await codeRes.json();
          code.forEach((comp: any) => {
            auditEvents.push({
              id: eventId++,
              timestamp: comp.created_at || new Date().toISOString(),
              user: { email: "user@example.com", role: "Admin" },
              action: `Registered code component: ${comp.name}`,
              actionType: "create",
              resource: comp.name,
              resourceType: "code",
              ipAddress: "192.168.1.100",
              details: `Type: ${comp.component_type}, Location: ${comp.location}`,
            });
          });
        }

        // Sort by timestamp descending
        auditEvents.sort(
          (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        );

        setEvents(auditEvents);
        setFilteredEvents(auditEvents);
      } catch (error) {
        console.error("Failed to fetch audit events:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAuditEvents();
  }, []);

  // Filter events based on search and action filter
  useEffect(() => {
    let filtered = events;

    if (searchTerm) {
      filtered = filtered.filter(
        (e) =>
          e.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
          e.resource.toLowerCase().includes(searchTerm.toLowerCase()) ||
          e.user.email.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    if (actionFilter !== "all") {
      filtered = filtered.filter((e) => e.actionType === actionFilter);
    }

    setFilteredEvents(filtered);
  }, [events, searchTerm, actionFilter]);

  const getActionIcon = (actionType: AuditEvent["actionType"]) => {
    switch (actionType) {
      case "create":
        return <Plus className="h-4 w-4 text-green-600" />;
      case "read":
        return <Eye className="h-4 w-4 text-blue-600" />;
      case "update":
        return <Edit className="h-4 w-4 text-orange-600" />;
      case "delete":
        return <Trash2 className="h-4 w-4 text-red-600" />;
      case "login":
        return <LogIn className="h-4 w-4 text-green-600" />;
      case "logout":
        return <LogOut className="h-4 w-4 text-gray-600" />;
      case "export":
        return <Download className="h-4 w-4 text-purple-600" />;
      default:
        return <Settings className="h-4 w-4 text-gray-600" />;
    }
  };

  const getResourceIcon = (resourceType: AuditEvent["resourceType"]) => {
    switch (resourceType) {
      case "document":
        return <FileText className="h-4 w-4 text-blue-600" />;
      case "code":
        return <Code className="h-4 w-4 text-green-600" />;
      case "user":
        return <User className="h-4 w-4 text-purple-600" />;
      case "settings":
        return <Settings className="h-4 w-4 text-gray-600" />;
      case "auth":
        return <ShieldCheck className="h-4 w-4 text-orange-600" />;
      default:
        return <Settings className="h-4 w-4 text-gray-600" />;
    }
  };

  const getActionBadgeVariant = (actionType: AuditEvent["actionType"]) => {
    switch (actionType) {
      case "create":
        return "default";
      case "delete":
        return "destructive";
      case "update":
        return "secondary";
      default:
        return "outline";
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

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
          <div className="p-2 bg-green-100 dark:bg-green-900 rounded-lg">
            <ShieldCheck className="w-6 h-6 text-green-600 dark:text-green-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Audit Trail</h1>
            <p className="text-muted-foreground">
              Track all user actions and system events
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm">
            <Download className="h-4 w-4 mr-2" />
            Export Logs
          </Button>
          <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Events</p>
                <p className="text-2xl font-bold">{events.length}</p>
              </div>
              <Calendar className="h-8 w-8 text-gray-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Creates</p>
                <p className="text-2xl font-bold text-green-600">
                  {events.filter((e) => e.actionType === "create").length}
                </p>
              </div>
              <Plus className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Updates</p>
                <p className="text-2xl font-bold text-orange-600">
                  {events.filter((e) => e.actionType === "update").length}
                </p>
              </div>
              <Edit className="h-8 w-8 text-orange-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Deletes</p>
                <p className="text-2xl font-bold text-red-600">
                  {events.filter((e) => e.actionType === "delete").length}
                </p>
              </div>
              <Trash2 className="h-8 w-8 text-red-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search by action, resource, or user..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <select
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                className="px-3 py-2 border border-input bg-background rounded-md text-sm"
              >
                <option value="all">All Actions</option>
                <option value="create">Creates</option>
                <option value="read">Reads</option>
                <option value="update">Updates</option>
                <option value="delete">Deletes</option>
                <option value="login">Logins</option>
                <option value="export">Exports</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Audit Log Table */}
      <Card>
        <CardHeader>
          <CardTitle>Activity Log</CardTitle>
          <CardDescription>
            Showing {filteredEvents.length} of {events.length} events
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <ShieldCheck className="h-16 w-16 text-muted-foreground mb-4" />
              <h3 className="text-xl font-semibold">No Audit Events</h3>
              <p className="text-muted-foreground mt-2">
                Activity will be logged here as you use the system.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Resource</TableHead>
                  <TableHead>IP Address</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredEvents.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                      {formatTimestamp(event.timestamp)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <p className="text-sm font-medium">{event.user.email}</p>
                          <p className="text-xs text-muted-foreground">{event.user.role}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getActionIcon(event.actionType)}
                        <div>
                          <Badge variant={getActionBadgeVariant(event.actionType)}>
                            {event.actionType.toUpperCase()}
                          </Badge>
                          <p className="text-sm mt-1">{event.action}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getResourceIcon(event.resourceType)}
                        <span className="text-sm">{event.resource}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground font-mono">
                      {event.ipAddress}
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
