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
import {
  History,
  FileText,
  Code,
  CheckCircle,
  Clock,
  RefreshCw,
  Loader2,
  Filter,
  Calendar,
  GitBranch,
  FolderGit2,
  Shield,
  Upload,
  LogIn,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

interface TimelineEvent {
  id: number;
  type: string;
  title: string;
  description: string;
  timestamp: string;
  status: string;
  user_email: string | null;
  related_item: {
    type: string;
    name: string;
    id: number | null;
  } | null;
}

export default function SyncTimelinePage() {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [filter, setFilter] = useState<string>("all");
  const [days, setDays] = useState(7);
  const [nextCursor, setNextCursor] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const fetchTimeline = useCallback(async (cursor?: number | null) => {
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
      const params = new URLSearchParams({ days: String(days), page_size: "50" });
      if (cursor != null) {
        params.set("cursor", String(cursor));
      }
      if (filter !== "all") {
        params.set("event_type", filter);
      }

      const res = await fetch(
        `${API_BASE_URL}/audit/timeline?${params}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (res.ok) {
        const data = await res.json();
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
        await fetchLegacyTimeline(token);
      }
    } catch (error) {
      console.error("Failed to fetch timeline:", error);
      if (!isAppend) {
        const token2 = localStorage.getItem("accessToken");
        if (token2) await fetchLegacyTimeline(token2);
      }
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [filter, days]);

  const fetchLegacyTimeline = async (token: string) => {
    try {
      const [docsRes, codeRes] = await Promise.all([
        fetch(`${API_BASE_URL}/documents/`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`${API_BASE_URL}/repositories/`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      const generatedEvents: TimelineEvent[] = [];

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
            user_email: null,
            related_item: { type: "document", name: doc.filename, id: doc.id },
          });
          if (doc.status === "completed") {
            generatedEvents.push({
              id: idx + 1000,
              type: "analysis_complete",
              title: "Analysis Completed",
              description: `AI analysis finished for ${doc.filename}`,
              timestamp: doc.created_at || new Date().toISOString(),
              status: "success",
              user_email: null,
              related_item: { type: "document", name: doc.filename, id: doc.id },
            });
          }
        });
      }

      if (codeRes.ok) {
        const repos = await codeRes.json();
        repos.forEach((repo: any, idx: number) => {
          generatedEvents.push({
            id: idx + 2000,
            type: "code_register",
            title: "Repository Onboarded",
            description: `${repo.name} was added`,
            timestamp: repo.created_at || new Date().toISOString(),
            status: "success",
            user_email: null,
            related_item: { type: "repository", name: repo.name, id: repo.id },
          });
        });
      }

      generatedEvents.sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      setEvents(generatedEvents);
    } catch {
      setEvents([]);
    }
  };

  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  const filteredEvents =
    filter === "all" ? events : events.filter((e) => e.type === filter);

  const getEventIcon = (type: string) => {
    switch (type) {
      case "document_upload":
        return <Upload className="h-4 w-4 text-blue-600" />;
      case "code_register":
        return <FolderGit2 className="h-4 w-4 text-green-600" />;
      case "analysis_complete":
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case "validation_run":
        return <Shield className="h-4 w-4 text-orange-600" />;
      case "login":
        return <LogIn className="h-4 w-4 text-purple-600" />;
      case "system_event":
        return <GitBranch className="h-4 w-4 text-gray-600" />;
      default:
        return <Clock className="h-4 w-4 text-gray-600" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "success":
        return <Badge className="bg-green-100 text-green-700">Success</Badge>;
      case "warning":
        return (
          <Badge className="bg-yellow-100 text-yellow-700">Warning</Badge>
        );
      case "failure":
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

  const statCounts = {
    total: events.length,
    documents: events.filter((e) => e.type === "document_upload").length,
    code: events.filter((e) => e.type === "code_register").length,
    analyses: events.filter((e) => e.type === "analysis_complete").length,
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
        <Button
          variant="outline"
          onClick={() => {
            setIsLoading(true);
            setNextCursor(null);
            setHasMore(false);
            fetchTimeline();
          }}
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Total Events
                </p>
                <p className="text-2xl font-bold">{statCounts.total}</p>
              </div>
              <History className="h-8 w-8 text-gray-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Documents
                </p>
                <p className="text-2xl font-bold">{statCounts.documents}</p>
              </div>
              <FileText className="h-8 w-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Code Changes
                </p>
                <p className="text-2xl font-bold">{statCounts.code}</p>
              </div>
              <Code className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Analyses
                </p>
                <p className="text-2xl font-bold">{statCounts.analyses}</p>
              </div>
              <CheckCircle className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex items-center gap-4">
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
            <option value="system_event">System Events</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-3 py-2 border border-input bg-background rounded-md text-sm"
          >
            <option value={1}>Last 24 hours</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Activity Timeline
          </CardTitle>
          <CardDescription>
            Showing {filteredEvents.length} events from the last {days} days
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <History className="h-16 w-16 text-muted-foreground mb-4" />
              <h3 className="text-xl font-semibold">No Activity Yet</h3>
              <p className="text-muted-foreground mt-2">
                Upload documents or register code components to see activity
                here.
              </p>
            </div>
          ) : (
            <div className="relative">
              <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200 dark:bg-gray-700" />
              <div className="space-y-6">
                {filteredEvents.map((event) => (
                  <div
                    key={event.id}
                    className="relative flex items-start gap-4 pl-10"
                  >
                    <div className="absolute left-2.5 w-3 h-3 bg-white border-2 border-gray-300 rounded-full" />
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
                      <div className="mt-2 flex items-center gap-3">
                        {event.related_item && (
                          <div className="flex items-center gap-1.5">
                            {event.related_item.type === "document" ? (
                              <FileText className="h-3 w-3 text-blue-600" />
                            ) : (
                              <Code className="h-3 w-3 text-green-600" />
                            )}
                            <span className="text-xs text-muted-foreground">
                              {event.related_item.name}
                            </span>
                          </div>
                        )}
                        {event.user_email && (
                          <span className="text-xs text-muted-foreground">
                            by {event.user_email}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {hasMore && (
                <div className="flex justify-center pt-6">
                  <Button
                    variant="outline"
                    onClick={() => fetchTimeline(nextCursor)}
                    disabled={isLoadingMore}
                  >
                    {isLoadingMore ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : null}
                    Load More Events
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
