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
  History,
  FileText,
  Code,
  CheckCircle,
  AlertCircle,
  Clock,
  RefreshCw,
  Loader2,
  Filter,
  Calendar,
} from "lucide-react";

interface SyncEvent {
  id: number;
  type: "document_upload" | "code_register" | "analysis_complete" | "validation_run" | "link_created";
  title: string;
  description: string;
  timestamp: string;
  status: "success" | "warning" | "error" | "info";
  relatedItem?: {
    type: "document" | "code";
    name: string;
  };
}

export default function SyncTimelinePage() {
  const [events, setEvents] = useState<SyncEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    // Fetch recent activity from API
    const fetchEvents = async () => {
      const token = localStorage.getItem("accessToken");
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        // In production, fetch from a dedicated activity/audit endpoint
        // For now, we'll check documents and code components for recent activity
        const [docsRes, codeRes] = await Promise.all([
          fetch("http://localhost:8000/api/v1/documents/", {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch("http://localhost:8000/api/v1/code-components/", {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);

        const generatedEvents: SyncEvent[] = [];

        if (docsRes.ok) {
          const docs = await docsRes.json();
          docs.forEach((doc: any, idx: number) => {
            generatedEvents.push({
              id: idx + 1,
              type: "document_upload",
              title: "Document Uploaded",
              description: `${doc.filename} was uploaded`,
              timestamp: doc.created_at || new Date().toISOString(),
              status: "success",
              relatedItem: { type: "document", name: doc.filename },
            });

            if (doc.status === "completed") {
              generatedEvents.push({
                id: idx + 1000,
                type: "analysis_complete",
                title: "Analysis Completed",
                description: `AI analysis finished for ${doc.filename}`,
                timestamp: doc.created_at || new Date().toISOString(),
                status: "success",
                relatedItem: { type: "document", name: doc.filename },
              });
            }
          });
        }

        if (codeRes.ok) {
          const code = await codeRes.json();
          code.forEach((comp: any, idx: number) => {
            generatedEvents.push({
              id: idx + 2000,
              type: "code_register",
              title: "Code Component Registered",
              description: `${comp.name} was added to the codebase`,
              timestamp: comp.created_at || new Date().toISOString(),
              status: "info",
              relatedItem: { type: "code", name: comp.name },
            });
          });
        }

        // Sort by timestamp descending
        generatedEvents.sort(
          (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        );

        setEvents(generatedEvents);
      } catch (error) {
        console.error("Failed to fetch timeline events:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchEvents();
  }, []);

  const filteredEvents = filter === "all"
    ? events
    : events.filter((e) => e.type === filter);

  const getEventIcon = (type: SyncEvent["type"]) => {
    switch (type) {
      case "document_upload":
        return <FileText className="h-4 w-4 text-blue-600" />;
      case "code_register":
        return <Code className="h-4 w-4 text-green-600" />;
      case "analysis_complete":
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case "validation_run":
        return <AlertCircle className="h-4 w-4 text-orange-600" />;
      case "link_created":
        return <History className="h-4 w-4 text-purple-600" />;
      default:
        return <Clock className="h-4 w-4 text-gray-600" />;
    }
  };

  const getStatusBadge = (status: SyncEvent["status"]) => {
    switch (status) {
      case "success":
        return <Badge className="bg-green-100 text-green-700">Success</Badge>;
      case "warning":
        return <Badge className="bg-yellow-100 text-yellow-700">Warning</Badge>;
      case "error":
        return <Badge className="bg-red-100 text-red-700">Error</Badge>;
      default:
        return <Badge className="bg-blue-100 text-blue-700">Info</Badge>;
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24) return `${diffHours} hours ago`;
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
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
          <div className="p-2 bg-orange-100 dark:bg-orange-900 rounded-lg">
            <History className="w-6 h-6 text-orange-600 dark:text-orange-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Sync Timeline</h1>
            <p className="text-muted-foreground">
              Track all document and code synchronization events
            </p>
          </div>
        </div>
        <Button variant="outline" onClick={() => window.location.reload()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
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
              <History className="h-8 w-8 text-gray-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Documents</p>
                <p className="text-2xl font-bold">
                  {events.filter((e) => e.type === "document_upload").length}
                </p>
              </div>
              <FileText className="h-8 w-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Code Changes</p>
                <p className="text-2xl font-bold">
                  {events.filter((e) => e.type === "code_register").length}
                </p>
              </div>
              <Code className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Analyses</p>
                <p className="text-2xl font-bold">
                  {events.filter((e) => e.type === "analysis_complete").length}
                </p>
              </div>
              <CheckCircle className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="px-3 py-2 border border-input bg-background rounded-md text-sm"
        >
          <option value="all">All Events</option>
          <option value="document_upload">Document Uploads</option>
          <option value="code_register">Code Registrations</option>
          <option value="analysis_complete">Analyses</option>
          <option value="validation_run">Validations</option>
        </select>
      </div>

      {/* Timeline */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Activity Timeline
          </CardTitle>
          <CardDescription>
            Recent synchronization and processing events
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <History className="h-16 w-16 text-muted-foreground mb-4" />
              <h3 className="text-xl font-semibold">No Activity Yet</h3>
              <p className="text-muted-foreground mt-2">
                Upload documents or register code components to see activity here.
              </p>
            </div>
          ) : (
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200 dark:bg-gray-700" />

              {/* Events */}
              <div className="space-y-6">
                {filteredEvents.map((event) => (
                  <div key={event.id} className="relative flex items-start gap-4 pl-10">
                    {/* Timeline dot */}
                    <div className="absolute left-2.5 w-3 h-3 bg-white border-2 border-gray-300 rounded-full" />

                    {/* Event content */}
                    <div className="flex-1 bg-white dark:bg-gray-800 rounded-lg border p-4 hover:shadow-sm transition-shadow">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-center gap-2">
                          {getEventIcon(event.type)}
                          <h4 className="font-medium">{event.title}</h4>
                        </div>
                        <div className="flex items-center gap-2">
                          {getStatusBadge(event.status)}
                          <span className="text-sm text-muted-foreground">
                            {formatTimestamp(event.timestamp)}
                          </span>
                        </div>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {event.description}
                      </p>
                      {event.relatedItem && (
                        <div className="mt-2 flex items-center gap-2">
                          {event.relatedItem.type === "document" ? (
                            <FileText className="h-3 w-3 text-blue-600" />
                          ) : (
                            <Code className="h-3 w-3 text-green-600" />
                          )}
                          <span className="text-xs text-muted-foreground">
                            {event.relatedItem.name}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
