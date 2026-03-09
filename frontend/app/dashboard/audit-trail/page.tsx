"use client";

import { useState, useEffect, useCallback } from "react";
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
  GitBranch,
  AlertCircle,
} from "lucide-react";

interface AuditEvent {
  id: number;
  timestamp: string;
  user: {
    id: number | null;
    email: string;
    role: string;
  };
  action: string;
  action_type: string;
  resource: string;
  resource_type: string;
  resource_id: number | null;
  description: string;
  ip_address: string;
  status: string;
  details: any;
}

interface AuditStats {
  total_events: number;
  by_action: Record<string, number>;
  by_resource: Record<string, number>;
  by_status: Record<string, number>;
  period_days: number;
}

export default function AuditTrailPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [stats, setStats] = useState<AuditStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [days, setDays] = useState(30);
  const [nextCursor, setNextCursor] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const fetchAuditData = useCallback(async (cursor?: number | null) => {
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setIsLoading(false);
      return;
    }

    const isAppend = cursor != null;
    if (isAppend) {
      setIsLoadingMore(true);
    }

    try {
      const params = new URLSearchParams({
        days: String(days),
        page_size: "50",
      });
      if (cursor != null) {
        params.set("cursor", String(cursor));
      }
      if (actionFilter !== "all") {
        params.set("action", actionFilter);
      }
      if (searchTerm) {
        params.set("search", searchTerm);
      }

      const fetches: Promise<Response>[] = [
        fetch(`http://localhost:8000/api/v1/audit/logs?${params}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ];

      // Only fetch stats on initial load (not on "load more")
      if (!isAppend) {
        fetches.push(
          fetch(`http://localhost:8000/api/v1/audit/stats?days=${days}`, {
            headers: { Authorization: `Bearer ${token}` },
          })
        );
      }

      const results = await Promise.all(fetches);
      const logsRes = results[0];
      const statsRes = results[1];

      if (logsRes.ok) {
        const data = await logsRes.json();
        // Handle both cursor-paginated and plain array responses
        if (data.items) {
          if (isAppend) {
            setEvents((prev) => [...prev, ...data.items]);
          } else {
            setEvents(data.items);
          }
          setNextCursor(data.next_cursor);
          setHasMore(data.has_more);
        } else {
          // Legacy plain array response
          setEvents(Array.isArray(data) ? data : []);
          setNextCursor(null);
          setHasMore(false);
        }
      } else if (!isAppend) {
        await fetchLegacyAudit(token);
      }

      if (statsRes?.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (error) {
      console.error("Failed to fetch audit events:", error);
      if (!isAppend) {
        const token2 = localStorage.getItem("accessToken");
        if (token2) await fetchLegacyAudit(token2);
      }
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [actionFilter, searchTerm, days]);

  const fetchLegacyAudit = async (token: string) => {
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

      if (docsRes.ok) {
        const docs = await docsRes.json();
        docs.forEach((doc: any) => {
          auditEvents.push({
            id: eventId++,
            timestamp: doc.created_at || new Date().toISOString(),
            user: { id: null, email: "user", role: "User" },
            action: "create",
            action_type: "create",
            resource: doc.filename,
            resource_type: "document",
            resource_id: doc.id,
            description: `Uploaded document: ${doc.filename}`,
            ip_address: "-",
            status: "success",
            details: null,
          });
        });
      }

      if (codeRes.ok) {
        const code = await codeRes.json();
        code.forEach((comp: any) => {
          auditEvents.push({
            id: eventId++,
            timestamp: comp.created_at || new Date().toISOString(),
            user: { id: null, email: "user", role: "User" },
            action: "create",
            action_type: "create",
            resource: comp.name,
            resource_type: "code_component",
            resource_id: comp.id,
            description: `Registered code component: ${comp.name}`,
            ip_address: "-",
            status: "success",
            details: null,
          });
        });
      }

      auditEvents.sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      setEvents(auditEvents);
    } catch {
      setEvents([]);
    }
  };

  useEffect(() => {
    fetchAuditData();
  }, [fetchAuditData]);

  const handleExport = async () => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;

    try {
      const res = await fetch(
        `http://localhost:8000/api/v1/audit/export?days=${days}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit_log_export_${new Date().toISOString().split("T")[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error("Export failed:", error);
    }
  };

  const getActionIcon = (action: string) => {
    switch (action) {
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
      case "analyze":
        return <Settings className="h-4 w-4 text-blue-600" />;
      case "webhook":
        return <GitBranch className="h-4 w-4 text-purple-600" />;
      case "export":
        return <Download className="h-4 w-4 text-purple-600" />;
      default:
        return <Settings className="h-4 w-4 text-gray-600" />;
    }
  };

  const getResourceIcon = (resourceType: string) => {
    switch (resourceType) {
      case "document":
        return <FileText className="h-4 w-4 text-blue-600" />;
      case "code_component":
      case "repository":
        return <Code className="h-4 w-4 text-green-600" />;
      case "user":
        return <User className="h-4 w-4 text-purple-600" />;
      case "auth":
        return <ShieldCheck className="h-4 w-4 text-orange-600" />;
      case "system":
        return <GitBranch className="h-4 w-4 text-gray-600" />;
      default:
        return <Settings className="h-4 w-4 text-gray-600" />;
    }
  };

  const getActionBadgeVariant = (action: string): "default" | "destructive" | "secondary" | "outline" => {
    switch (action) {
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
    return new Date(timestamp).toLocaleString();
  };

  // Compute stats from data or from API
  const totalEvents = stats?.total_events ?? events.length;
  const creates = stats?.by_action?.create ?? events.filter((e) => e.action === "create").length;
  const updates = stats?.by_action?.update ?? events.filter((e) => e.action === "update").length;
  const deletes = stats?.by_action?.delete ?? events.filter((e) => e.action === "delete").length;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
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
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="h-4 w-4 mr-2" />
            Export Logs
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setIsLoading(true);
              setNextCursor(null);
              setHasMore(false);
              fetchAuditData();
            }}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Total Events
                </p>
                <p className="text-2xl font-bold">{totalEvents}</p>
              </div>
              <Calendar className="h-8 w-8 text-gray-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Creates
                </p>
                <p className="text-2xl font-bold text-green-600">{creates}</p>
              </div>
              <Plus className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Updates
                </p>
                <p className="text-2xl font-bold text-orange-600">{updates}</p>
              </div>
              <Edit className="h-8 w-8 text-orange-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Deletes
                </p>
                <p className="text-2xl font-bold text-red-600">{deletes}</p>
              </div>
              <Trash2 className="h-8 w-8 text-red-600" />
            </div>
          </CardContent>
        </Card>
      </div>

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
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    setIsLoading(true);
                    fetchAuditData();
                  }
                }}
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
                <option value="update">Updates</option>
                <option value="delete">Deletes</option>
                <option value="analyze">Analyses</option>
                <option value="login">Logins</option>
                <option value="webhook">Webhooks</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="px-3 py-2 border border-input bg-background rounded-md text-sm"
              >
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Activity Log</CardTitle>
          <CardDescription>
            Showing {events.length} events from the last {days} days
          </CardDescription>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <ShieldCheck className="h-16 w-16 text-muted-foreground mb-4" />
              <h3 className="text-xl font-semibold">No Audit Events</h3>
              <p className="text-muted-foreground mt-2">
                Activity will be logged here as you use the system.
              </p>
            </div>
          ) : (
            <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Resource</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>IP Address</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                      {formatTimestamp(event.timestamp)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <p className="text-sm font-medium">
                            {event.user.email}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {event.user.role}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getActionIcon(event.action)}
                        <div>
                          <Badge variant={getActionBadgeVariant(event.action)}>
                            {event.action.toUpperCase()}
                          </Badge>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getResourceIcon(event.resource_type)}
                        <span className="text-sm truncate max-w-[200px]">
                          {event.resource}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={
                          event.status === "success"
                            ? "bg-green-100 text-green-700"
                            : event.status === "failure"
                              ? "bg-red-100 text-red-700"
                              : "bg-yellow-100 text-yellow-700"
                        }
                      >
                        {event.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground font-mono">
                      {event.ip_address}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {hasMore && (
              <div className="flex justify-center pt-4">
                <Button
                  variant="outline"
                  onClick={() => fetchAuditData(nextCursor)}
                  disabled={isLoadingMore}
                >
                  {isLoadingMore ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : null}
                  Load More
                </Button>
              </div>
            )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
