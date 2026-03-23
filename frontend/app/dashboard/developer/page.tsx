/**
 * Developer Dashboard
 * URL: /dashboard/developer
 *
 * Target Audience: Software Engineers
 * Mandatory Widgets:
 * - My Tasks: List of tasks assigned specifically to the logged-in user
 * - Code Mismatches: Live count of Code vs. Doc discrepancies
 * - Recent Code Components: List of recently synced/uploaded code files
 * - Validation Quick-Run: Button to trigger immediate validation
 */

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth, Permission } from "@/contexts/AuthContext";
import Link from "next/link";
import {
  Code,
  ListTodo,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Play,
  GitBranch,
  FileCode,
  Zap,
  ArrowUpRight,
  RefreshCw,
  Loader2,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export default function DeveloperDashboardPage() {
  const router = useRouter();
  const { user, hasPermission, isLoading, getPrimaryDashboardUrl } = useAuth();
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [validationRunning, setValidationRunning] = useState(false);
  const [permissionChecked, setPermissionChecked] = useState(false);

  // Check permission after auth is loaded
  useEffect(() => {
    if (!isLoading && user && !permissionChecked) {
      setPermissionChecked(true);
      if (user.roles && user.roles.length > 0 && !hasPermission(Permission.DASHBOARD_DEVELOPER)) {
        const primaryUrl = getPrimaryDashboardUrl();
        if (primaryUrl !== "/dashboard/developer") {
          router.replace(primaryUrl);
        }
      }
    }
  }, [user, isLoading, hasPermission, router, permissionChecked, getPrimaryDashboardUrl]);

  // Load dashboard data from real APIs
  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const [mismatches, codeComponents] = await Promise.allSettled([
          api.get<any[]>("/validation/mismatches?limit=100"),
          api.get<any[]>("/code-components/?limit=10"),
        ]);

        const mismatchList = mismatches.status === "fulfilled" ? mismatches.value : [];
        const codeList = codeComponents.status === "fulfilled" ? codeComponents.value : [];

        const criticalCount = mismatchList.filter((m: any) => m.severity === "critical" || m.severity === "high").length;
        const warningCount = mismatchList.filter((m: any) => m.severity === "medium" || m.severity === "warning").length;

        setDashboardData({
          myTasks: [],
          codeMismatches: {
            total: mismatchList.length,
            critical: criticalCount,
            warning: warningCount,
          },
          recentCode: codeList.slice(0, 5).map((c: any) => ({
            id: c.id,
            name: c.name,
            language: c.component_type || "Unknown",
            updatedAt: c.updated_at ? new Date(c.updated_at).toLocaleDateString() : "",
          })),
          stats: {
            tasksAssigned: 0,
            tasksCompleted: 0,
            codeComponents: codeList.length,
            avgResolutionTime: "N/A",
          },
        });
      } catch {
        setDashboardData({
          myTasks: [],
          codeMismatches: { total: 0, critical: 0, warning: 0 },
          recentCode: [],
          stats: { tasksAssigned: 0, tasksCompleted: 0, codeComponents: 0, avgResolutionTime: "N/A" },
        });
      } finally {
        setDataLoading(false);
      }
    };
    loadDashboard();
  }, []);

  const handleQuickValidation = async () => {
    setValidationRunning(true);
    try {
      // Fetch user's documents to validate against
      const docs = await api.get<any[]>("/documents/?limit=100");
      const docIds = docs.map((d: any) => d.id);
      if (docIds.length === 0) {
        alert("No documents found to validate. Upload documents first.");
        return;
      }
      await api.post("/validation/run-scan", { document_ids: docIds });
      alert(`Validation scan started for ${docIds.length} document(s). Check back shortly for results.`);
    } catch {
      alert("Failed to start validation scan. Please try again.");
    } finally {
      setValidationRunning(false);
    }
  };

  if (isLoading || dataLoading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
            <p className="text-gray-600">Loading Developer Dashboard...</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  const data = dashboardData;

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Developer Dashboard</h1>
            <p className="mt-2 text-gray-600">
              Track your tasks, code components, and validation status
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <span className="rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-700">
              Developer View
            </span>
            <Button
              onClick={handleQuickValidation}
              disabled={validationRunning}
              className="flex items-center space-x-2"
            >
              {validationRunning ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              <span>{validationRunning ? "Running..." : "Quick Validate"}</span>
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Tasks Assigned"
            value={data.stats.tasksAssigned}
            icon={<ListTodo className="h-5 w-5" />}
            color="blue"
          />
          <StatCard
            label="Code Components"
            value={data.stats.codeComponents}
            icon={<Code className="h-5 w-5" />}
            color="green"
          />
          <StatCard
            label="Mismatches"
            value={data.codeMismatches.total}
            icon={<AlertTriangle className="h-5 w-5" />}
            color={data.codeMismatches.total > 0 ? "red" : "gray"}
          />
          <StatCard
            label="Tasks Completed"
            value={data.stats.tasksCompleted}
            icon={<CheckCircle2 className="h-5 w-5" />}
            color="purple"
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* My Tasks */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">My Tasks</h2>
              <Link href="/tasks" className="text-sm text-blue-600 hover:text-blue-700">
                View All
              </Link>
            </div>

            {data.myTasks.length === 0 ? (
              <EmptyState
                icon={<ListTodo className="h-8 w-8 text-gray-400" />}
                title="No tasks assigned"
                description="Tasks assigned to you will appear here"
                action={
                  <Link href="/tasks">
                    <Button variant="outline" size="sm" className="mt-4">
                      Browse Tasks
                    </Button>
                  </Link>
                }
              />
            ) : (
              <div className="space-y-3">
                {data.myTasks.map((task: any) => (
                  <TaskItem key={task.id} task={task} />
                ))}
              </div>
            )}
          </div>

          {/* Code Mismatches */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Code Mismatches</h2>
              <Link href="/dashboard/validation-panel" className="text-sm text-blue-600 hover:text-blue-700">
                View All
              </Link>
            </div>

            {data.codeMismatches.total === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <div className="rounded-full bg-green-100 p-4">
                  <CheckCircle2 className="h-8 w-8 text-green-600" />
                </div>
                <h3 className="mt-4 text-sm font-medium text-gray-900">All Clear!</h3>
                <p className="mt-1 text-sm text-gray-600">
                  No code mismatches detected
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-lg bg-red-50 p-4 text-center">
                    <p className="text-2xl font-bold text-red-600">{data.codeMismatches.critical}</p>
                    <p className="text-sm text-gray-600">Critical</p>
                  </div>
                  <div className="rounded-lg bg-yellow-50 p-4 text-center">
                    <p className="text-2xl font-bold text-yellow-600">{data.codeMismatches.warning}</p>
                    <p className="text-sm text-gray-600">Warnings</p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Recent Code Components */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Recent Code Components</h2>
              <Link href="/dashboard/code" className="text-sm text-blue-600 hover:text-blue-700">
                View All
              </Link>
            </div>

            {data.recentCode.length === 0 ? (
              <EmptyState
                icon={<FileCode className="h-8 w-8 text-gray-400" />}
                title="No code components yet"
                description="Upload or sync code to get started"
                action={
                  <Link href="/dashboard/code">
                    <Button variant="outline" size="sm" className="mt-4">
                      Add Code
                    </Button>
                  </Link>
                }
              />
            ) : (
              <div className="space-y-3">
                {data.recentCode.map((code: any) => (
                  <CodeItem key={code.id} code={code} />
                ))}
              </div>
            )}
          </div>

          {/* Quick Actions */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">Quick Actions</h2>
            <div className="grid gap-3 grid-cols-2">
              <QuickActionButton
                href="/dashboard/code"
                icon={<Code className="h-5 w-5" />}
                label="Add Code"
              />
              <QuickActionButton
                href="/dashboard/validation-panel"
                icon={<Zap className="h-5 w-5" />}
                label="Run Validation"
              />
              <QuickActionButton
                href="/tasks"
                icon={<ListTodo className="h-5 w-5" />}
                label="View Tasks"
              />
              <QuickActionButton
                href="/dashboard/documents"
                icon={<GitBranch className="h-5 w-5" />}
                label="View Docs"
              />
              <QuickActionButton
                href="/dashboard/chat"
                icon={<Sparkles className="h-5 w-5" />}
                label="Ask about mismatches"
              />
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

// Helper Components

function StatCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
}) {
  const colorClasses: Record<string, string> = {
    blue: "bg-blue-100 text-blue-600",
    green: "bg-green-100 text-green-600",
    purple: "bg-purple-100 text-purple-600",
    red: "bg-red-100 text-red-600",
    gray: "bg-gray-100 text-gray-600",
  };

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{label}</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">{value}</p>
        </div>
        <div className={`rounded-lg p-3 ${colorClasses[color]}`}>{icon}</div>
      </div>
    </div>
  );
}

function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="rounded-full bg-gray-100 p-3">{icon}</div>
      <h3 className="mt-4 text-sm font-medium text-gray-900">{title}</h3>
      <p className="mt-1 text-sm text-gray-600">{description}</p>
      {action}
    </div>
  );
}

function TaskItem({ task }: { task: any }) {
  const priorityColors: Record<string, string> = {
    high: "bg-red-100 text-red-700",
    medium: "bg-yellow-100 text-yellow-700",
    low: "bg-green-100 text-green-700",
  };

  return (
    <div className="flex items-center justify-between rounded-lg border p-3 hover:bg-gray-50">
      <div className="flex items-center space-x-3">
        <Clock className="h-4 w-4 text-gray-400" />
        <div>
          <p className="text-sm font-medium text-gray-900">{task.title}</p>
          <p className="text-xs text-gray-500">{task.project}</p>
        </div>
      </div>
      <span className={`rounded-full px-2 py-1 text-xs font-medium ${priorityColors[task.priority]}`}>
        {task.priority}
      </span>
    </div>
  );
}

function CodeItem({ code }: { code: any }) {
  return (
    <div className="flex items-center justify-between rounded-lg border p-3 hover:bg-gray-50">
      <div className="flex items-center space-x-3">
        <FileCode className="h-4 w-4 text-gray-400" />
        <div>
          <p className="text-sm font-medium text-gray-900">{code.name}</p>
          <p className="text-xs text-gray-500">{code.language}</p>
        </div>
      </div>
      <span className="text-xs text-gray-500">{code.updatedAt}</span>
    </div>
  );
}

function QuickActionButton({
  href,
  icon,
  label,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center justify-between rounded-lg border p-4 hover:border-blue-300 hover:bg-blue-50 transition-colors"
    >
      <div className="flex items-center space-x-3">
        <span className="text-blue-600">{icon}</span>
        <span className="text-sm font-medium text-gray-900">{label}</span>
      </div>
      <ArrowUpRight className="h-4 w-4 text-gray-400" />
    </Link>
  );
}
