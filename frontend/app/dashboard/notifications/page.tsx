"use client";

import { useEffect } from "react";
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
  Bell,
  CheckCheck,
  FileText,
  Code,
  AlertTriangle,
  Info,
  RefreshCw,
  Loader2,
  Inbox,
} from "lucide-react";
import { useNotifications } from "@/contexts/NotificationContext";

function getNotificationIcon(type: string) {
  switch (type) {
    case "analysis_complete":
      return <FileText className="h-5 w-5 text-green-500" />;
    case "analysis_failed":
      return <AlertTriangle className="h-5 w-5 text-red-500" />;
    case "validation_alert":
      return <AlertTriangle className="h-5 w-5 text-yellow-500" />;
    case "system":
      return <Info className="h-5 w-5 text-blue-500" />;
    default:
      return <Bell className="h-5 w-5 text-gray-500" />;
  }
}

function getTypeBadge(type: string) {
  const map: Record<string, { label: string; className: string }> = {
    analysis_complete: { label: "Analysis", className: "bg-green-100 text-green-700" },
    analysis_failed: { label: "Error", className: "bg-red-100 text-red-700" },
    validation_alert: { label: "Validation", className: "bg-yellow-100 text-yellow-700" },
    system: { label: "System", className: "bg-blue-100 text-blue-700" },
    mention: { label: "Mention", className: "bg-purple-100 text-purple-700" },
  };
  const config = map[type] || { label: type, className: "bg-gray-100 text-gray-700" };
  return <Badge className={config.className}>{config.label}</Badge>;
}

export default function NotificationsPage() {
  const { notifications, unreadCount, isLoading, refresh, markRead, markAllRead } =
    useNotifications();

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
            <Bell className="w-6 h-6 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Notifications</h1>
            <p className="text-muted-foreground">
              {unreadCount > 0
                ? `${unreadCount} unread notification${unreadCount !== 1 ? "s" : ""}`
                : "All caught up"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <Button variant="outline" size="sm" onClick={() => markAllRead()}>
              <CheckCheck className="h-4 w-4 mr-2" />
              Mark All Read
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={refresh}
            disabled={isLoading}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Refresh
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Notifications</CardTitle>
          <CardDescription>
            {notifications.length} notification{notifications.length !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Inbox className="h-16 w-16 text-muted-foreground mb-4" />
              <h3 className="text-xl font-semibold">No Notifications</h3>
              <p className="text-muted-foreground mt-2">
                You will receive notifications when documents are analyzed,
                validations complete, or important system events occur.
              </p>
            </div>
          ) : (
            <div className="divide-y">
              {notifications.map((n) => (
                <div
                  key={n.id}
                  className={`flex items-start gap-4 py-4 px-2 rounded-lg transition-colors ${
                    !n.is_read ? "bg-blue-50/50" : "hover:bg-gray-50"
                  }`}
                >
                  <div className="mt-0.5 flex-shrink-0">
                    {getNotificationIcon(n.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p
                        className={`text-sm ${
                          !n.is_read ? "font-semibold" : "font-medium"
                        } text-gray-900`}
                      >
                        {n.title}
                      </p>
                      {getTypeBadge(n.type)}
                    </div>
                    <p className="text-sm text-gray-600">{n.message}</p>
                    {n.created_at && (
                      <p className="text-xs text-gray-400 mt-1">
                        {new Date(n.created_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                  <div className="flex-shrink-0">
                    {!n.is_read ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => markRead(n.id)}
                        className="text-xs"
                      >
                        Mark read
                      </Button>
                    ) : (
                      <span className="text-xs text-gray-400">Read</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
