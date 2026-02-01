/**
 * Dashboard Page - Role Router
 * Sprint 2 Refinement
 *
 * This page redirects users to their role-specific dashboard:
 * - CXO: /dashboard/cxo (Executive Overview)
 * - Admin: /dashboard/admin (Operations)
 * - Developer: /dashboard/developer (Execution)
 * - BA: /dashboard/ba (Requirements)
 * - PM: /dashboard/developer (Uses Developer view)
 */

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth } from "@/contexts/AuthContext";
import Link from "next/link";
import {
  FileText,
  Code,
  ListTodo,
  Users,
  TrendingUp,
  Clock,
  AlertTriangle,
  CheckCircle2,
  CreditCard,
  Activity,
  BarChart3,
  GitBranch,
  Target,
  Calendar,
  Shield,
  Zap,
  DollarSign,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const { user, tenant, isCXO, isLoading, getPrimaryDashboardUrl } = useAuth();

  // Redirect to role-specific dashboard
  useEffect(() => {
    if (!isLoading && user) {
      const dashboardUrl = getPrimaryDashboardUrl();
      router.replace(dashboardUrl);
    }
  }, [user, isLoading, getPrimaryDashboardUrl, router]);

  // Show loading while redirecting
  if (isLoading || user) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
            <p className="text-gray-600">Loading your dashboard...</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  // Fallback - determine roles for direct rendering
  const isDeveloper = user?.roles.includes("Developer");
  const isBA = user?.roles.includes("BA");
  const isPM = user?.roles.includes("PM") || user?.roles.includes("Product Manager");

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Welcome Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Welcome back{isCXO() ? ", Admin" : ""}!
          </h1>
          <p className="mt-2 text-gray-600">
            {isCXO() && "Monitor your organization's health and manage resources."}
            {isDeveloper && "Track your code components and development tasks."}
            {isBA && "Review documents, validation results, and business requirements."}
            {isPM && "Overview of project progress and team activities."}
          </p>
        </div>

        {/* Role-Specific Stats */}
        {isCXO() && <CXOStats tenant={tenant} />}
        {isDeveloper && <DeveloperStats />}
        {isBA && <BAStats />}
        {isPM && <PMStats />}

        {/* Role-Specific Content */}
        <div className="grid gap-6 lg:grid-cols-2">
          {isCXO() && (
            <>
              <BillingWidget tenant={tenant} />
              <TeamActivityWidget />
              <SystemHealthWidget />
              <QuickActionsWidget />
            </>
          )}

          {isDeveloper && (
            <>
              <MyTasksWidget />
              <CodeMismatchesWidget />
              <RecentCodeWidget />
              <CodeQualityWidget />
            </>
          )}

          {isBA && (
            <>
              <DocumentsWidget />
              <ValidationWidget />
              <MyTasksWidget />
              <RecentAnalysisWidget />
            </>
          )}

          {isPM && (
            <>
              <ProjectOverviewWidget />
              <TaskProgressWidget />
              <TeamTasksWidget />
              <MilestonesWidget />
            </>
          )}
        </div>
      </div>
    </AppLayout>
  );
}

// ============================================================================
// CXO Dashboard Components
// ============================================================================

function CXOStats({ tenant }: { tenant: any }) {
  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        label="Total Users"
        value="1"
        max={tenant?.max_users}
        icon={<Users className="h-5 w-5" />}
        color="blue"
        trend={{ value: "+0%", positive: true }}
      />
      <StatCard
        label="Documents"
        value="0"
        max={tenant?.max_documents}
        icon={<FileText className="h-5 w-5" />}
        color="green"
      />
      <StatCard
        label="Active Tasks"
        value="0"
        icon={<ListTodo className="h-5 w-5" />}
        color="purple"
      />
      <StatCard
        label="Monthly Cost"
        value="$0"
        icon={<DollarSign className="h-5 w-5" />}
        color="orange"
        trend={{ value: "-0%", positive: true }}
      />
    </div>
  );
}

function BillingWidget({ tenant }: { tenant: any }) {
  const isPrepaid = tenant?.billing_type === "prepaid";

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Billing Overview</h2>
        <Link href="/billing" className="text-sm text-blue-600 hover:text-blue-700">
          View Details
        </Link>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between rounded-lg bg-blue-50 p-4">
          <div>
            <p className="text-sm text-gray-600">Current Plan</p>
            <p className="text-2xl font-bold capitalize text-gray-900">{tenant?.tier || "Free"}</p>
          </div>
          <CreditCard className="h-8 w-8 text-blue-600" />
        </div>

        {isPrepaid ? (
          <div>
            <div className="mb-2 flex justify-between text-sm">
              <span className="text-gray-600">Balance</span>
              <span className="font-medium text-gray-900">$0.00</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-gray-200">
              <div className="h-full w-0 bg-green-600"></div>
            </div>
            <p className="mt-2 text-xs text-gray-500">Add balance to continue using services</p>
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

        <button className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          {isPrepaid ? "Add Balance" : "Upgrade Plan"}
        </button>
      </div>
    </div>
  );
}

function TeamActivityWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Team Activity</h2>
        <Activity className="h-5 w-5 text-gray-400" />
      </div>

      <div className="space-y-3">
        <EmptyState
          icon={<Clock className="h-6 w-6" />}
          title="No activity yet"
          description="Team activity will appear here"
        />
      </div>
    </div>
  );
}

function SystemHealthWidget() {
  return (
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
  );
}

function QuickActionsWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold text-gray-900">Quick Actions</h2>

      <div className="grid gap-3 sm:grid-cols-2">
        <Link href="/users" className="flex items-center space-x-3 rounded-lg border p-3 hover:border-blue-300 hover:bg-blue-50">
          <Users className="h-5 w-5 text-blue-600" />
          <span className="text-sm font-medium">Manage Users</span>
        </Link>

        <Link href="/billing" className="flex items-center space-x-3 rounded-lg border p-3 hover:border-blue-300 hover:bg-blue-50">
          <CreditCard className="h-5 w-5 text-blue-600" />
          <span className="text-sm font-medium">View Billing</span>
        </Link>

        <Link href="/analysis" className="flex items-center space-x-3 rounded-lg border p-3 hover:border-blue-300 hover:bg-blue-50">
          <BarChart3 className="h-5 w-5 text-blue-600" />
          <span className="text-sm font-medium">Analytics</span>
        </Link>

        <Link href="/settings" className="flex items-center space-x-3 rounded-lg border p-3 hover:border-blue-300 hover:bg-blue-50">
          <Target className="h-5 w-5 text-blue-600" />
          <span className="text-sm font-medium">Settings</span>
        </Link>
      </div>
    </div>
  );
}

// ============================================================================
// Developer Dashboard Components
// ============================================================================

function DeveloperStats() {
  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard label="My Tasks" value="0" icon={<ListTodo className="h-5 w-5" />} color="blue" />
      <StatCard label="Code Components" value="0" icon={<Code className="h-5 w-5" />} color="green" />
      <StatCard label="Mismatches" value="0" icon={<AlertTriangle className="h-5 w-5" />} color="red" />
      <StatCard label="Resolved" value="0" icon={<CheckCircle2 className="h-5 w-5" />} color="purple" />
    </div>
  );
}

function CodeMismatchesWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Code Mismatches</h2>
        <Link href="/validation" className="text-sm text-blue-600 hover:text-blue-700">
          View All
        </Link>
      </div>

      <EmptyState
        icon={<CheckCircle2 className="h-6 w-6 text-green-600" />}
        title="No mismatches"
        description="All code is in sync with documentation"
      />
    </div>
  );
}

function RecentCodeWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Recent Components</h2>
        <Link href="/code" className="text-sm text-blue-600 hover:text-blue-700">
          View All
        </Link>
      </div>

      <EmptyState
        icon={<Code className="h-6 w-6" />}
        title="No components yet"
        description="Code components will appear here"
      />
    </div>
  );
}

function CodeQualityWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Code Quality</h2>
        <Zap className="h-5 w-5 text-gray-400" />
      </div>

      <div className="space-y-3">
        <QualityMetric label="Coverage" value="0%" color="blue" />
        <QualityMetric label="Documentation" value="0%" color="green" />
        <QualityMetric label="Compliance" value="0%" color="purple" />
      </div>
    </div>
  );
}

// ============================================================================
// BA Dashboard Components
// ============================================================================

function BAStats() {
  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard label="Documents" value="0" icon={<FileText className="h-5 w-5" />} color="blue" />
      <StatCard label="Validations" value="0" icon={<CheckCircle2 className="h-5 w-5" />} color="green" />
      <StatCard label="My Tasks" value="0" icon={<ListTodo className="h-5 w-5" />} color="purple" />
      <StatCard label="Analysis" value="0" icon={<BarChart3 className="h-5 w-5" />} color="orange" />
    </div>
  );
}

function DocumentsWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Recent Documents</h2>
        <Link href="/documents" className="text-sm text-blue-600 hover:text-blue-700">
          View All
        </Link>
      </div>

      <EmptyState
        icon={<FileText className="h-6 w-6" />}
        title="No documents yet"
        description="Upload documents to get started"
        action={
          <button className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
            Upload Document
          </button>
        }
      />
    </div>
  );
}

function ValidationWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Validation Results</h2>
        <Link href="/validation" className="text-sm text-blue-600 hover:text-blue-700">
          View All
        </Link>
      </div>

      <EmptyState
        icon={<CheckCircle2 className="h-6 w-6 text-green-600" />}
        title="No validations yet"
        description="Validation results will appear here"
      />
    </div>
  );
}

function RecentAnalysisWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Recent Analysis</h2>
        <Link href="/analysis" className="text-sm text-blue-600 hover:text-blue-700">
          View All
        </Link>
      </div>

      <EmptyState
        icon={<BarChart3 className="h-6 w-6" />}
        title="No analysis yet"
        description="Analysis results will appear here"
      />
    </div>
  );
}

// ============================================================================
// PM Dashboard Components
// ============================================================================

function PMStats() {
  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard label="Total Tasks" value="0" icon={<ListTodo className="h-5 w-5" />} color="blue" />
      <StatCard label="Completed" value="0" icon={<CheckCircle2 className="h-5 w-5" />} color="green" />
      <StatCard label="In Progress" value="0" icon={<Clock className="h-5 w-5" />} color="orange" />
      <StatCard label="Team Members" value="1" icon={<Users className="h-5 w-5" />} color="purple" />
    </div>
  );
}

function ProjectOverviewWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Project Overview</h2>
        <Target className="h-5 w-5 text-gray-400" />
      </div>

      <div className="space-y-4">
        <div>
          <div className="mb-2 flex justify-between text-sm">
            <span className="text-gray-600">Overall Progress</span>
            <span className="font-medium text-gray-900">0%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-gray-200">
            <div className="h-full w-0 bg-blue-600"></div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-2xl font-bold text-gray-900">0</p>
            <p className="text-sm text-gray-600">Total Tasks</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-green-600">0</p>
            <p className="text-sm text-gray-600">Completed</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function TaskProgressWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Task Progress</h2>
        <Link href="/tasks" className="text-sm text-blue-600 hover:text-blue-700">
          View All
        </Link>
      </div>

      <div className="space-y-3">
        <ProgressItem label="Backlog" value={0} total={0} color="gray" />
        <ProgressItem label="In Progress" value={0} total={0} color="blue" />
        <ProgressItem label="In Review" value={0} total={0} color="yellow" />
        <ProgressItem label="Done" value={0} total={0} color="green" />
      </div>
    </div>
  );
}

function TeamTasksWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Team Tasks</h2>
        <Users className="h-5 w-5 text-gray-400" />
      </div>

      <EmptyState
        icon={<ListTodo className="h-6 w-6" />}
        title="No tasks assigned"
        description="Create tasks and assign to team members"
        action={
          <button className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
            Create Task
          </button>
        }
      />
    </div>
  );
}

function MilestonesWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Milestones</h2>
        <Calendar className="h-5 w-5 text-gray-400" />
      </div>

      <EmptyState
        icon={<Target className="h-6 w-6" />}
        title="No milestones"
        description="Set project milestones to track progress"
      />
    </div>
  );
}

// ============================================================================
// Shared Components (All Roles)
// ============================================================================

function MyTasksWidget() {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">My Tasks</h2>
        <Link href="/tasks" className="text-sm text-blue-600 hover:text-blue-700">
          View All
        </Link>
      </div>

      <EmptyState
        icon={<ListTodo className="h-6 w-6" />}
        title="No tasks assigned"
        description="Tasks assigned to you will appear here"
      />
    </div>
  );
}

// ============================================================================
// Utility Components
// ============================================================================

function StatCard({
  label,
  value,
  max,
  icon,
  color,
  trend,
}: {
  label: string;
  value: string | number;
  max?: number;
  icon: React.ReactNode;
  color: string;
  trend?: { value: string; positive: boolean };
}) {
  const colorClasses = {
    blue: "bg-blue-100 text-blue-600",
    green: "bg-green-100 text-green-600",
    purple: "bg-purple-100 text-purple-600",
    orange: "bg-orange-100 text-orange-600",
    red: "bg-red-100 text-red-600",
  };

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600">{label}</p>
          <div className="mt-2 flex items-baseline space-x-2">
            <p className="text-3xl font-bold text-gray-900">{value}</p>
            {max && <span className="text-sm text-gray-500">/ {max}</span>}
          </div>
          {trend && (
            <div className={`mt-2 flex items-center text-sm ${trend.positive ? "text-green-600" : "text-red-600"}`}>
              {trend.positive ? (
                <ArrowUpRight className="h-4 w-4" />
              ) : (
                <ArrowDownRight className="h-4 w-4" />
              )}
              <span>{trend.value}</span>
            </div>
          )}
        </div>
        <div className={`rounded-lg p-3 ${colorClasses[color as keyof typeof colorClasses]}`}>
          {icon}
        </div>
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

function HealthItem({ label, status }: { label: string; status: "operational" | "degraded" | "down" }) {
  const statusConfig = {
    operational: { color: "text-green-600", bg: "bg-green-100", label: "Operational" },
    degraded: { color: "text-yellow-600", bg: "bg-yellow-100", label: "Degraded" },
    down: { color: "text-red-600", bg: "bg-red-100", label: "Down" },
  };

  const config = statusConfig[status];

  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-700">{label}</span>
      <span className={`rounded-full ${config.bg} px-2 py-1 text-xs font-medium ${config.color}`}>
        {config.label}
      </span>
    </div>
  );
}

function QualityMetric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium text-gray-900">{value}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-gray-200">
        <div className={`h-full w-0 bg-${color}-600`}></div>
      </div>
    </div>
  );
}

function ProgressItem({
  label,
  value,
  total,
  color,
}: {
  label: string;
  value: number;
  total: number;
  color: string;
}) {
  const percentage = total > 0 ? Math.round((value / total) * 100) : 0;

  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium text-gray-900">
          {value} / {total}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-gray-200">
        <div className={`h-full bg-${color}-600`} style={{ width: `${percentage}%` }}></div>
      </div>
    </div>
  );
}
