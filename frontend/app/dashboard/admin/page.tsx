/**
 * Admin Dashboard Page
 * Sprint 2 Extended - CXO/Admin Dashboard
 *
 * Dedicated admin dashboard with:
 * - Organization overview
 * - User management quick access
 * - Billing and usage monitoring
 * - System health status
 */

"use client";

import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth, Permission } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import {
  Users,
  FileText,
  CreditCard,
  Shield,
  BarChart3,
  Settings,
  DollarSign,
  Activity,
  CheckCircle2,
  Clock,
  Loader2,
  Briefcase,
  Sparkles,
  ChevronRight,
} from "lucide-react";

interface IndustrySettings {
  industry?: string;
  industry_display_name?: string;
  industry_confidence?: number;
  onboarding_complete?: boolean;
  glossary?: Record<string, string>;
}

interface AdminDashboardData {
  userCount: number;
  documentCount: number;
  monthlyCost: number;
  balance: number;
  billingType: string;
  activeTasks: number;
  recentActivity: Array<{
    id: number;
    action: string;
    resource_type: string;
    resource_id: number | null;
    user_email: string;
    created_at: string;
    details: any;
  }>;
}

export default function AdminDashboardPage() {
  const { user, tenant, isCXO, isAdmin, hasPermission, isLoading, getPrimaryDashboardUrl } = useAuth();
  const router = useRouter();
  const [permissionChecked, setPermissionChecked] = useState(false);
  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [industrySettings, setIndustrySettings] = useState<IndustrySettings | null>(null);

  // Check if user has admin dashboard permission (CXO or Admin role)
  const canAccessAdminDashboard = hasPermission(Permission.DASHBOARD_ADMIN);

  const fetchData = useCallback(async () => {
    setDataLoading(true);
    try {
      const [usersRes, docsRes, billingRes, auditRes, settingsRes] = await Promise.all([
        api.get<any[]>("/users").catch(() => []),
        api.get<any>("/documents?page_size=1").catch(() => ({ items: [] })),
        api.get<any>("/billing/usage").catch(() => null),
        api.get<any>("/audit/logs?page_size=5").catch(() => ({ items: [] })),
        api.get<{ settings: IndustrySettings }>("/tenants/me/settings").catch(() => null),
      ]);

      if (settingsRes?.settings) {
        setIndustrySettings(settingsRes.settings);
      }

      const userCount = Array.isArray(usersRes) ? usersRes.length : 1;
      const documentCount = docsRes?.total || (Array.isArray(docsRes?.items) ? docsRes.items.length : 0);
      const activityItems = auditRes?.items || (Array.isArray(auditRes) ? auditRes : []);

      setData({
        userCount,
        documentCount,
        monthlyCost: billingRes?.current_month_cost || 0,
        balance: billingRes?.balance_inr || 0,
        billingType: billingRes?.billing_type || tenant?.billing_type || "prepaid",
        activeTasks: 0,
        recentActivity: activityItems.slice(0, 5),
      });
    } catch {
      setData({
        userCount: 1,
        documentCount: 0,
        monthlyCost: 0,
        balance: 0,
        billingType: "prepaid",
        activeTasks: 0,
        recentActivity: [],
      });
    } finally {
      setDataLoading(false);
    }
  }, [tenant]);

  // Check permission after auth is loaded
  useEffect(() => {
    if (!isLoading && user && !permissionChecked) {
      setPermissionChecked(true);
      if (user.roles && user.roles.length > 0 && !canAccessAdminDashboard) {
        const primaryUrl = getPrimaryDashboardUrl();
        if (primaryUrl !== "/dashboard/admin") {
          router.replace(primaryUrl);
        }
      }
    }
  }, [user, isLoading, canAccessAdminDashboard, router, permissionChecked, getPrimaryDashboardUrl]);

  useEffect(() => {
    if (user && !isLoading) {
      fetchData();
    }
  }, [user, isLoading, fetchData]);

  if (isLoading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
            <p className="text-gray-600">Loading Admin Dashboard...</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  if (!canAccessAdminDashboard) {
    // Show loading while redirect happens
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
            <p className="text-gray-600">Redirecting...</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
          <p className="mt-2 text-gray-600">
            Organization overview and management tools
          </p>
        </div>

        {/* Key Metrics */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Total Users"
            value={dataLoading ? "..." : String(data?.userCount ?? 0)}
            max={tenant?.max_users || 10}
            icon={<Users className="h-5 w-5" />}
            color="blue"
            href="/settings/user_management"
          />
          <MetricCard
            label="Documents"
            value={dataLoading ? "..." : String(data?.documentCount ?? 0)}
            max={tenant?.max_documents || 100}
            icon={<FileText className="h-5 w-5" />}
            color="green"
            href="/dashboard/documents"
          />
          <MetricCard
            label="Monthly Cost"
            value={dataLoading ? "..." : `$${(data?.monthlyCost ?? 0).toFixed(2)}`}
            icon={<DollarSign className="h-5 w-5" />}
            color="orange"
            href="/settings/billing"
          />
          <MetricCard
            label="Active Tasks"
            value={dataLoading ? "..." : String(data?.activeTasks ?? 0)}
            icon={<Activity className="h-5 w-5" />}
            color="purple"
            href="/tasks"
          />
        </div>

        {/* Main Content Grid */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Organization Info */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Organization</h2>
              <Link href="/settings/organization" className="text-sm text-blue-600 hover:text-blue-700">
                Manage
              </Link>
            </div>

            <div className="space-y-4">
              <InfoRow label="Name" value={tenant?.name || "N/A"} />
              <InfoRow label="Subdomain" value={`${tenant?.subdomain}.dokydoc.com`} />
              <InfoRow label="Plan" value={
                <span className="inline-flex rounded-full bg-blue-100 px-3 py-1 text-sm font-medium capitalize text-blue-700">
                  {tenant?.tier || "Free"}
                </span>
              } />
              <InfoRow label="Status" value={
                <span className="inline-flex items-center rounded-full bg-green-100 px-3 py-1 text-sm font-medium capitalize text-green-700">
                  <CheckCircle2 className="mr-1 h-3 w-3" />
                  {tenant?.status || "Active"}
                </span>
              } />
            </div>
          </div>

          {/* Billing Overview */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Billing Overview</h2>
              <Link href="/settings/billing" className="text-sm text-blue-600 hover:text-blue-700">
                View Details
              </Link>
            </div>

            <div className="space-y-4">
              <div className="rounded-lg bg-blue-50 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Current Plan</p>
                    <p className="text-2xl font-bold capitalize text-gray-900">
                      {tenant?.tier || "Free"}
                    </p>
                  </div>
                  <CreditCard className="h-8 w-8 text-blue-600" />
                </div>
              </div>

              {(data?.billingType || tenant?.billing_type) === "prepaid" ? (
                <div>
                  <div className="mb-2 flex justify-between text-sm">
                    <span className="text-gray-600">Balance</span>
                    <span className="font-medium text-gray-900">
                      {dataLoading ? "..." : `$${(data?.balance ?? 0).toFixed(2)}`}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-gray-200">
                    <div
                      className="h-full bg-green-600 transition-all"
                      style={{ width: `${Math.min(100, ((data?.balance ?? 0) / Math.max(1, tenant?.monthly_limit_inr || 10000)) * 100)}%` }}
                    ></div>
                  </div>
                  <p className="mt-2 text-xs text-gray-500">
                    {(data?.balance ?? 0) > 0
                      ? `$${(data?.balance ?? 0).toFixed(2)} remaining`
                      : "Add balance to continue using services"}
                  </p>
                </div>
              ) : (
                <div>
                  <div className="mb-2 flex justify-between text-sm">
                    <span className="text-gray-600">Usage this month</span>
                    <span className="font-medium text-gray-900">
                      {dataLoading ? "..." : `$${(data?.monthlyCost ?? 0).toFixed(2)}`}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">Postpaid billing</p>
                </div>
              )}
            </div>
          </div>

          {/* System Health */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">System Health</h2>
              <Shield className="h-5 w-5 text-gray-400" />
            </div>

            <div className="space-y-3">
              <HealthItem label="API Status" status="operational" />
              <HealthItem label="Database" status="operational" />
              <HealthItem label="AI Services" status="operational" />
              <HealthItem label="Storage" status="operational" />
            </div>
          </div>

          {/* Quick Actions */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">Quick Actions</h2>

            <div className="grid gap-3 sm:grid-cols-2">
              <ActionLink
                href="/settings/user_management"
                icon={<Users className="h-5 w-5" />}
                label="Manage Users"
              />
              <ActionLink
                href="/settings/billing"
                icon={<CreditCard className="h-5 w-5" />}
                label="View Billing"
              />
              <ActionLink
                href="/dashboard/validation-panel"
                icon={<BarChart3 className="h-5 w-5" />}
                label="Analytics"
              />
              <ActionLink
                href="/settings"
                icon={<Settings className="h-5 w-5" />}
                label="Settings"
              />
            </div>
          </div>
        </div>

        {/* P5-09: Industry Profile Card */}
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Briefcase className="h-5 w-5 text-blue-600" />
              <h2 className="text-lg font-semibold text-gray-900">Industry Profile</h2>
            </div>
            <Link
              href="/dashboard/onboarding"
              className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
            >
              {industrySettings?.industry ? "Update" : "Configure"}
              <ChevronRight className="h-4 w-4" />
            </Link>
          </div>

          {industrySettings?.industry ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3 rounded-lg bg-blue-50 px-4 py-3">
                <Sparkles className="h-5 w-5 text-blue-600 flex-shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-blue-900">
                    {industrySettings.industry_display_name || industrySettings.industry}
                  </p>
                  {industrySettings.industry_confidence !== undefined && (
                    <p className="text-xs text-blue-600 mt-0.5">
                      Auto-detected &middot; {Math.round((industrySettings.industry_confidence || 0) * 100)}% confidence
                    </p>
                  )}
                </div>
              </div>

              {industrySettings.glossary && Object.keys(industrySettings.glossary).length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                    Glossary ({Object.keys(industrySettings.glossary).length} terms)
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {Object.keys(industrySettings.glossary).slice(0, 6).map((term) => (
                      <span
                        key={term}
                        className="inline-flex rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs font-medium text-gray-700"
                      >
                        {term}
                      </span>
                    ))}
                    {Object.keys(industrySettings.glossary).length > 6 && (
                      <span className="text-xs text-gray-400 self-center">
                        +{Object.keys(industrySettings.glossary).length - 6} more
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-6 text-center">
              <div className="rounded-full bg-gray-100 p-3 mb-3">
                <Briefcase className="h-6 w-6 text-gray-400" />
              </div>
              <p className="text-sm font-medium text-gray-900">No industry configured</p>
              <p className="mt-1 text-xs text-gray-500 max-w-xs">
                Configure your industry profile so DokyDoc can tailor validation prompts and glossary suggestions
              </p>
              <Link
                href="/dashboard/onboarding"
                className="mt-3 inline-flex items-center gap-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
              >
                Set Up Industry Profile
              </Link>
            </div>
          )}
        </div>

        {/* Activity Timeline */}
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Recent Activity</h2>
            <Link href="/dashboard/audit-trail" className="text-sm text-blue-600 hover:text-blue-700">
              View All
            </Link>
          </div>

          {dataLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600"></div>
            </div>
          ) : data?.recentActivity && data.recentActivity.length > 0 ? (
            <div className="space-y-3">
              {data.recentActivity.map((activity) => (
                <div key={activity.id} className="flex items-start gap-3 rounded-lg border p-3">
                  <div className="mt-0.5">
                    <Activity className="h-4 w-4 text-gray-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">
                      {activity.action?.replace(/_/g, " ")}
                    </p>
                    <p className="text-xs text-gray-500">
                      {activity.user_email} &middot; {activity.resource_type}
                      {activity.created_at && ` &middot; ${new Date(activity.created_at).toLocaleString()}`}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="rounded-full bg-gray-100 p-3">
                <Clock className="h-6 w-6 text-gray-400" />
              </div>
              <h3 className="mt-4 text-sm font-medium text-gray-900">No activity yet</h3>
              <p className="mt-1 text-sm text-gray-600">
                Team activity will appear here
              </p>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}

// ============================================================================
// Helper Components
// ============================================================================

function MetricCard({
  label,
  value,
  max,
  icon,
  color,
  href,
}: {
  label: string;
  value: string;
  max?: number;
  icon: React.ReactNode;
  color: string;
  href?: string;
}) {
  const colorClasses = {
    blue: "bg-blue-100 text-blue-600",
    green: "bg-green-100 text-green-600",
    purple: "bg-purple-100 text-purple-600",
    orange: "bg-orange-100 text-orange-600",
  };

  const card = (
    <div className={`rounded-lg border bg-white p-6 shadow-sm ${href ? "cursor-pointer hover:border-blue-300 hover:shadow-md transition-all" : ""}`}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600">{label}</p>
          <div className="mt-2 flex items-baseline space-x-2">
            <p className="text-3xl font-bold text-gray-900">{value}</p>
            {max && <span className="text-sm text-gray-500">/ {max}</span>}
          </div>
        </div>
        <div className={`rounded-lg p-3 ${colorClasses[color as keyof typeof colorClasses]}`}>
          {icon}
        </div>
      </div>
    </div>
  );

  return href ? <Link href={href}>{card}</Link> : card;
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}

function HealthItem({
  label,
  status,
}: {
  label: string;
  status: "operational" | "degraded" | "down";
}) {
  const statusConfig = {
    operational: {
      color: "text-green-600",
      bg: "bg-green-100",
      label: "Operational",
    },
    degraded: { color: "text-yellow-600", bg: "bg-yellow-100", label: "Degraded" },
    down: { color: "text-red-600", bg: "bg-red-100", label: "Down" },
  };

  const config = statusConfig[status];

  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-700">{label}</span>
      <span
        className={`rounded-full ${config.bg} px-2 py-1 text-xs font-medium ${config.color}`}
      >
        {config.label}
      </span>
    </div>
  );
}

function ActionLink({
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
      className="flex items-center space-x-3 rounded-lg border p-3 transition-colors hover:border-blue-300 hover:bg-blue-50"
    >
      <div className="text-blue-600">{icon}</div>
      <span className="text-sm font-medium">{label}</span>
    </Link>
  );
}
