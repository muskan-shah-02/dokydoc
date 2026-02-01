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
import { useEffect, useState } from "react";
import Link from "next/link";
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
  TrendingUp,
  UserPlus,
  Receipt,
} from "lucide-react";

export default function AdminDashboardPage() {
  const { user, tenant, isCXO, isAdmin, hasPermission, isLoading, getPrimaryDashboardUrl } = useAuth();
  const router = useRouter();
  const [permissionChecked, setPermissionChecked] = useState(false);

  // Check if user has admin dashboard permission (CXO or Admin role)
  const canAccessAdminDashboard = hasPermission(Permission.DASHBOARD_ADMIN);

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
            value="1"
            max={tenant?.max_users || 10}
            icon={<Users className="h-5 w-5" />}
            color="blue"
            href="/settings/user_management"
          />
          <MetricCard
            label="Documents"
            value="0"
            max={tenant?.max_documents || 100}
            icon={<FileText className="h-5 w-5" />}
            color="green"
            href="/dashboard/documents"
          />
          <MetricCard
            label="Monthly Cost"
            value="$0"
            icon={<DollarSign className="h-5 w-5" />}
            color="orange"
            href="/settings/billing"
          />
          <MetricCard
            label="Active Tasks"
            value="0"
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

              {tenant?.billing_type === "prepaid" ? (
                <div>
                  <div className="mb-2 flex justify-between text-sm">
                    <span className="text-gray-600">Balance</span>
                    <span className="font-medium text-gray-900">$0.00</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-gray-200">
                    <div className="h-full w-0 bg-green-600"></div>
                  </div>
                  <p className="mt-2 text-xs text-gray-500">
                    Add balance to continue using services
                  </p>
                </div>
              ) : (
                <div>
                  <div className="mb-2 flex justify-between text-sm">
                    <span className="text-gray-600">Usage this month</span>
                    <span className="font-medium text-gray-900">$0.00</span>
                  </div>
                  <p className="text-xs text-gray-500">Next billing date: N/A</p>
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

        {/* Activity Timeline */}
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Recent Activity</h2>
            <Activity className="h-5 w-5 text-gray-400" />
          </div>

          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="rounded-full bg-gray-100 p-3">
              <Clock className="h-6 w-6 text-gray-400" />
            </div>
            <h3 className="mt-4 text-sm font-medium text-gray-900">No activity yet</h3>
            <p className="mt-1 text-sm text-gray-600">
              Team activity will appear here
            </p>
          </div>
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
