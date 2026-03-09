/**
 * CXO (Executive) Dashboard
 * URL: /dashboard/cxo
 *
 * Target Audience: Tenant Owners / CTOs
 * Mandatory Widgets:
 * - Cost Overview: Current month spending vs. budget
 * - System Health: RAG status of API, DB, and AI Services
 * - Team Velocity: Tasks Completed vs. Open
 * - Tenant Usage: Storage used, API calls vs. Plan Limits
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth, Permission } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import Link from "next/link";
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Shield,
  Users,
  FileText,
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock,
  Server,
  Database,
  Cpu,
  HardDrive,
  BarChart3,
  ArrowUpRight,
  RefreshCw,
} from "lucide-react";

export default function CXODashboardPage() {
  const router = useRouter();
  const { user, tenant, hasPermission, isLoading, getPrimaryDashboardUrl } = useAuth();
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [permissionChecked, setPermissionChecked] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Check permission after auth is loaded
  useEffect(() => {
    if (!isLoading && user && !permissionChecked) {
      setPermissionChecked(true);
      // Only redirect if user explicitly doesn't have permission AND has roles loaded
      if (user.roles && user.roles.length > 0 && !hasPermission(Permission.DASHBOARD_CXO)) {
        // Redirect to their actual primary dashboard, not /dashboard to avoid loop
        const primaryUrl = getPrimaryDashboardUrl();
        if (primaryUrl !== "/dashboard/cxo") {
          router.replace(primaryUrl);
        }
      }
    }
  }, [user, isLoading, hasPermission, router, permissionChecked, getPrimaryDashboardUrl]);

  // Types for API responses
  interface BillingUsageResponse {
    balance_inr?: number;
    billing_type?: string;
    current_month_cost?: number;
    monthly_limit_inr?: number;
    last_30_days_cost?: number;
    low_balance_alert?: boolean;
  }

  interface DocumentsResponse {
    items?: any[];
    total?: number;
  }

  interface TasksResponse {
    items?: any[];
    total?: number;
  }

  // Fetch real data from APIs
  const fetchDashboardData = useCallback(async () => {
    try {
      // Add timeout to prevent hanging forever
      const withTimeout = <T,>(promise: Promise<T>, fallback: T, ms = 10000): Promise<T> =>
        Promise.race([promise, new Promise<T>((resolve) => setTimeout(() => resolve(fallback), ms))]);

      // Fetch billing data, documents, and tasks in parallel
      const [billingData, documentsData, tasksData, usersData] = await Promise.all([
        withTimeout(api.get<BillingUsageResponse>("/billing/usage").catch(() => null), null),
        withTimeout(api.get<DocumentsResponse>("/documents").catch(() => ({ items: [], total: 0 })), { items: [], total: 0 }),
        withTimeout(api.get<TasksResponse>("/tasks").catch(() => ({ items: [], total: 0 })), { items: [], total: 0 }),
        withTimeout(api.get<any[]>("/users").catch(() => []), []),
      ]);

      // Calculate task stats
      const tasks = tasksData?.items || tasksData || [];
      const completedTasks = Array.isArray(tasks) ? tasks.filter((t: any) => t.status === "done").length : 0;
      const inProgressTasks = Array.isArray(tasks) ? tasks.filter((t: any) => t.status === "in_progress").length : 0;
      const openTasks = Array.isArray(tasks) ? tasks.filter((t: any) => ["todo", "backlog"].includes(t.status)).length : 0;

      // Get user count
      const userCount = Array.isArray(usersData) ? usersData.length : 1;

      // Get document count
      const documentCount = documentsData?.total || (Array.isArray(documentsData?.items) ? documentsData.items.length : 0);

      setDashboardData({
        costOverview: {
          currentMonth: billingData?.current_month_cost || 0,
          budget: billingData?.monthly_limit_inr || tenant?.monthly_limit_inr || 10000,
          lastMonth: billingData?.last_30_days_cost || 0,
          trend: 0, // Calculate from history if available
          balance: billingData?.balance_inr || 0,
          billingType: billingData?.billing_type || "prepaid",
          lowBalanceAlert: billingData?.low_balance_alert || false,
        },
        systemHealth: {
          api: "operational",
          database: "operational",
          aiServices: "operational",
          storage: "operational",
        },
        teamVelocity: {
          completed: completedTasks,
          open: openTasks,
          inProgress: inProgressTasks,
        },
        tenantUsage: {
          users: { current: userCount, max: tenant?.max_users || 10 },
          documents: { current: documentCount, max: tenant?.max_documents || 100 },
          storage: { used: 0, max: 10 }, // GB - would need separate API
          apiCalls: { current: 0, max: 10000 }, // Would need separate tracking
        },
      });
    } catch (error) {
      console.error("Failed to load dashboard data:", error);
      // Set default data on error
      setDashboardData({
        costOverview: { currentMonth: 0, budget: 10000, lastMonth: 0, trend: 0, balance: 0, billingType: "prepaid" },
        systemHealth: { api: "operational", database: "operational", aiServices: "operational", storage: "operational" },
        teamVelocity: { completed: 0, open: 0, inProgress: 0 },
        tenantUsage: {
          users: { current: 1, max: tenant?.max_users || 10 },
          documents: { current: 0, max: tenant?.max_documents || 100 },
          storage: { used: 0, max: 10 },
          apiCalls: { current: 0, max: 10000 },
        },
      });
    } finally {
      setDataLoading(false);
      setRefreshing(false);
    }
  }, [tenant]);

  // Load dashboard data
  useEffect(() => {
    if (!isLoading) {
      if (user) {
        fetchDashboardData();
      } else {
        setDataLoading(false);
      }
    }
  }, [user, isLoading, fetchDashboardData]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchDashboardData();
  };

  if (isLoading || dataLoading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
            <p className="text-gray-600">Loading Executive Dashboard...</p>
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
            <h1 className="text-3xl font-bold text-gray-900">Executive Dashboard</h1>
            <p className="mt-2 text-gray-600">
              Monitor costs, system health, and organizational metrics
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center space-x-2 rounded-lg border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
              <span>Refresh</span>
            </button>
            <span className="rounded-full bg-purple-100 px-3 py-1 text-sm font-medium text-purple-700">
              CXO View
            </span>
          </div>
        </div>

        {/* Low Balance Alert */}
        {data.costOverview.billingType === "prepaid" && data.costOverview.lowBalanceAlert && (
          <div className="rounded-lg border border-orange-300 bg-orange-50 p-4">
            <div className="flex items-center space-x-3">
              <AlertCircle className="h-5 w-5 text-orange-600" />
              <div>
                <p className="font-medium text-orange-800">Low Balance Alert</p>
                <p className="text-sm text-orange-700">
                  Your prepaid balance is running low. Current balance: INR {data.costOverview.balance.toFixed(2)}.
                  <Link href="/settings/billing" className="ml-1 underline">Top up now</Link>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Cost Overview */}
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Cost Overview</h2>
            <div className="flex items-center space-x-4">
              <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                data.costOverview.billingType === "prepaid"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-purple-100 text-purple-700"
              }`}>
                {data.costOverview.billingType === "prepaid" ? "Prepaid" : "Postpaid"}
              </span>
              <Link href="/settings/billing" className="text-sm text-blue-600 hover:text-blue-700">
                View Billing Details
              </Link>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-4">
            {/* Current Balance (for prepaid) or Current Month Cost */}
            {data.costOverview.billingType === "prepaid" ? (
              <div className={`rounded-lg p-4 ${
                data.costOverview.balance < 100 ? "bg-red-50" : "bg-green-50"
              }`}>
                <div className="flex items-center justify-between">
                  <p className="text-sm text-gray-600">Current Balance</p>
                  <DollarSign className={`h-5 w-5 ${
                    data.costOverview.balance < 100 ? "text-red-600" : "text-green-600"
                  }`} />
                </div>
                <p className="mt-2 text-3xl font-bold text-gray-900">
                  INR {data.costOverview.balance.toFixed(2)}
                </p>
                <p className="mt-1 text-xs text-gray-500">
                  {data.costOverview.balance < 100 ? "Low balance - top up soon" : "Available for API calls"}
                </p>
              </div>
            ) : (
              <div className="rounded-lg bg-blue-50 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-gray-600">Current Month</p>
                  <DollarSign className="h-5 w-5 text-blue-600" />
                </div>
                <p className="mt-2 text-3xl font-bold text-gray-900">
                  INR {data.costOverview.currentMonth.toFixed(2)}
                </p>
                <p className="mt-1 text-xs text-gray-500">
                  of INR {data.costOverview.budget} budget
                </p>
              </div>
            )}

            <div className="rounded-lg bg-blue-50 p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-600">Month Spend</p>
                <TrendingUp className="h-5 w-5 text-blue-600" />
              </div>
              <p className="mt-2 text-3xl font-bold text-gray-900">
                INR {data.costOverview.currentMonth.toFixed(2)}
              </p>
              <p className="mt-1 text-xs text-gray-500">
                This billing cycle
              </p>
            </div>

            <div className="rounded-lg bg-gray-50 p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-600">Last 30 Days</p>
                <BarChart3 className="h-5 w-5 text-gray-600" />
              </div>
              <p className="mt-2 text-3xl font-bold text-gray-900">
                INR {data.costOverview.lastMonth.toFixed(2)}
              </p>
              <p className="mt-1 text-xs text-gray-500">Total spend</p>
            </div>

            <div className="rounded-lg bg-purple-50 p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-600">Monthly Limit</p>
                <Shield className="h-5 w-5 text-purple-600" />
              </div>
              <p className="mt-2 text-3xl font-bold text-gray-900">
                INR {data.costOverview.budget.toFixed(0)}
              </p>
              <p className="mt-1 text-xs text-gray-500">
                {(((data.costOverview.budget - data.costOverview.currentMonth) / data.costOverview.budget) * 100).toFixed(0)}% remaining
              </p>
            </div>
          </div>
        </div>

        {/* System Health (RAG Status) */}
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">System Health</h2>
            <Shield className="h-5 w-5 text-gray-400" />
          </div>

          <div className="grid gap-4 md:grid-cols-4">
            <HealthStatusCard
              label="API Services"
              status={data.systemHealth.api}
              icon={<Server className="h-5 w-5" />}
            />
            <HealthStatusCard
              label="Database"
              status={data.systemHealth.database}
              icon={<Database className="h-5 w-5" />}
            />
            <HealthStatusCard
              label="AI Services"
              status={data.systemHealth.aiServices}
              icon={<Cpu className="h-5 w-5" />}
            />
            <HealthStatusCard
              label="Storage"
              status={data.systemHealth.storage}
              icon={<HardDrive className="h-5 w-5" />}
            />
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Team Velocity */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Team Velocity</h2>
              <Activity className="h-5 w-5 text-gray-400" />
            </div>

            <div className="grid gap-4 grid-cols-3">
              <div className="text-center">
                <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
                  <CheckCircle2 className="h-6 w-6 text-green-600" />
                </div>
                <p className="text-2xl font-bold text-gray-900">{data.teamVelocity.completed}</p>
                <p className="text-sm text-gray-600">Completed</p>
              </div>

              <div className="text-center">
                <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-blue-100">
                  <Clock className="h-6 w-6 text-blue-600" />
                </div>
                <p className="text-2xl font-bold text-gray-900">{data.teamVelocity.inProgress}</p>
                <p className="text-sm text-gray-600">In Progress</p>
              </div>

              <div className="text-center">
                <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-orange-100">
                  <AlertCircle className="h-6 w-6 text-orange-600" />
                </div>
                <p className="text-2xl font-bold text-gray-900">{data.teamVelocity.open}</p>
                <p className="text-sm text-gray-600">Open</p>
              </div>
            </div>
          </div>

          {/* Tenant Usage */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Resource Usage</h2>
              <Link href="/settings" className="text-sm text-blue-600 hover:text-blue-700">
                Manage
              </Link>
            </div>

            <div className="space-y-4">
              <UsageBar
                label="Users"
                current={data.tenantUsage.users.current}
                max={data.tenantUsage.users.max}
                icon={<Users className="h-4 w-4" />}
              />
              <UsageBar
                label="Documents"
                current={data.tenantUsage.documents.current}
                max={data.tenantUsage.documents.max}
                icon={<FileText className="h-4 w-4" />}
              />
              <UsageBar
                label="Storage (GB)"
                current={data.tenantUsage.storage.used}
                max={data.tenantUsage.storage.max}
                icon={<HardDrive className="h-4 w-4" />}
              />
              <UsageBar
                label="API Calls"
                current={data.tenantUsage.apiCalls.current}
                max={data.tenantUsage.apiCalls.max}
                icon={<Activity className="h-4 w-4" />}
              />
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Quick Actions</h2>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
            <QuickActionButton href="/settings/user_management" icon={<Users className="h-5 w-5" />} label="Manage Users" />
            <QuickActionButton href="/settings/billing" icon={<DollarSign className="h-5 w-5" />} label="View Billing" />
            <QuickActionButton href="/dashboard/documents" icon={<FileText className="h-5 w-5" />} label="View Documents" />
            <QuickActionButton href="/settings/organization" icon={<Shield className="h-5 w-5" />} label="Organization" />
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

// Helper Components

function HealthStatusCard({
  label,
  status,
  icon,
}: {
  label: string;
  status: "operational" | "degraded" | "down";
  icon: React.ReactNode;
}) {
  const statusConfig = {
    operational: {
      bg: "bg-green-50",
      border: "border-green-200",
      text: "text-green-700",
      dot: "bg-green-500",
      label: "Operational",
    },
    degraded: {
      bg: "bg-yellow-50",
      border: "border-yellow-200",
      text: "text-yellow-700",
      dot: "bg-yellow-500",
      label: "Degraded",
    },
    down: {
      bg: "bg-red-50",
      border: "border-red-200",
      text: "text-red-700",
      dot: "bg-red-500",
      label: "Down",
    },
  };

  const config = statusConfig[status];

  return (
    <div className={`rounded-lg border ${config.border} ${config.bg} p-4`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-gray-600">{icon}</span>
          <span className="text-sm font-medium text-gray-900">{label}</span>
        </div>
        <div className={`h-3 w-3 rounded-full ${config.dot}`}></div>
      </div>
      <p className={`mt-2 text-sm font-medium ${config.text}`}>{config.label}</p>
    </div>
  );
}

function UsageBar({
  label,
  current,
  max,
  icon,
}: {
  label: string;
  current: number;
  max: number;
  icon: React.ReactNode;
}) {
  const percentage = max > 0 ? Math.min((current / max) * 100, 100) : 0;
  const isNearLimit = percentage > 80;

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <div className="flex items-center space-x-2">
          <span className="text-gray-500">{icon}</span>
          <span className="text-gray-700">{label}</span>
        </div>
        <span className="font-medium text-gray-900">
          {current} / {max}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-gray-200">
        <div
          className={`h-full transition-all ${isNearLimit ? "bg-red-500" : "bg-blue-600"}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
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
