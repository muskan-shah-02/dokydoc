/**
 * Dashboard Page
 * Sprint 2 Extended - Multi-Tenancy Support
 *
 * Main dashboard - will be customized per role in Phase 3
 */

"use client";

import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth } from "@/contexts/AuthContext";
import {
  FileText,
  Code,
  ListTodo,
  Users,
  TrendingUp,
  Clock,
} from "lucide-react";

export default function DashboardPage() {
  const { user, tenant, isCXO } = useAuth();

  // Quick stats (placeholder data)
  const stats = [
    {
      label: "Documents",
      value: "0",
      icon: <FileText className="h-5 w-5" />,
      color: "blue",
    },
    {
      label: "Code Components",
      value: "0",
      icon: <Code className="h-5 w-5" />,
      color: "green",
    },
    {
      label: "Active Tasks",
      value: "0",
      icon: <ListTodo className="h-5 w-5" />,
      color: "purple",
    },
    {
      label: "Team Members",
      value: tenant?.max_users || "0",
      icon: <Users className="h-5 w-5" />,
      color: "orange",
    },
  ];

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Welcome Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Welcome back{isCXO() ? ", Admin" : ""}!
          </h1>
          <p className="mt-2 text-gray-600">
            Here's what's happening with your organization today.
          </p>
        </div>

        {/* Quick Stats */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat, idx) => (
            <div
              key={idx}
              className="rounded-lg border bg-white p-6 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    {stat.label}
                  </p>
                  <p className="mt-2 text-3xl font-bold text-gray-900">
                    {stat.value}
                  </p>
                </div>
                <div
                  className={`rounded-lg bg-${stat.color}-100 p-3 text-${stat.color}-600`}
                >
                  {stat.icon}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Recent Activity */}
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">
              Recent Activity
            </h2>
            <button className="text-sm text-blue-600 hover:text-blue-700">
              View all
            </button>
          </div>

          {/* Empty State */}
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="rounded-full bg-gray-100 p-4">
              <Clock className="h-8 w-8 text-gray-400" />
            </div>
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              No activity yet
            </h3>
            <p className="mt-2 text-sm text-gray-600">
              Get started by uploading documents, creating tasks, or inviting
              team members.
            </p>
            <div className="mt-6 flex space-x-3">
              <button className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                Upload Document
              </button>
              <button className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
                Create Task
              </button>
            </div>
          </div>
        </div>

        {/* Quick Actions (CXO only) */}
        {isCXO() && (
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">
              Admin Quick Actions
            </h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <button className="flex items-center space-x-3 rounded-lg border border-gray-300 p-4 text-left hover:border-blue-300 hover:bg-blue-50">
                <Users className="h-5 w-5 text-blue-600" />
                <div>
                  <p className="font-medium text-gray-900">Invite Users</p>
                  <p className="text-sm text-gray-600">Add team members</p>
                </div>
              </button>

              <button className="flex items-center space-x-3 rounded-lg border border-gray-300 p-4 text-left hover:border-blue-300 hover:bg-blue-50">
                <TrendingUp className="h-5 w-5 text-blue-600" />
                <div>
                  <p className="font-medium text-gray-900">View Analytics</p>
                  <p className="text-sm text-gray-600">Usage insights</p>
                </div>
              </button>

              <button className="flex items-center space-x-3 rounded-lg border border-gray-300 p-4 text-left hover:border-blue-300 hover:bg-blue-50">
                <FileText className="h-5 w-5 text-blue-600" />
                <div>
                  <p className="font-medium text-gray-900">View Billing</p>
                  <p className="text-sm text-gray-600">Manage subscription</p>
                </div>
              </button>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
