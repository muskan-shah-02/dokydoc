/**
 * Business Analyst Dashboard
 * URL: /dashboard/ba
 *
 * Target Audience: Product Managers / BAs
 * Mandatory Widgets:
 * - Recent Documents: List of recently uploaded PRDs/Specs
 * - Analysis Queue: Status of documents currently being processed by AI
 * - Validation Reports: Summary of pass/fail rates for recent requirements
 * - Upload Widget: Drag-and-drop zone for new documentation
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth, Permission } from "@/contexts/AuthContext";
import Link from "next/link";
import {
  FileText,
  Upload,
  Clock,
  CheckCircle2,
  AlertCircle,
  BarChart3,
  ArrowUpRight,
  Loader2,
  XCircle,
  FileUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export default function BADashboardPage() {
  const router = useRouter();
  const { user, hasPermission, isLoading } = useAuth();
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [isDragging, setIsDragging] = useState(false);

  // Redirect if user doesn't have BA dashboard permission
  useEffect(() => {
    if (!isLoading && user) {
      if (!hasPermission(Permission.DASHBOARD_BA)) {
        router.push("/dashboard");
      }
    }
  }, [user, isLoading, hasPermission, router]);

  // Load dashboard data
  useEffect(() => {
    // Simulated data - in production, fetch from API
    setDashboardData({
      recentDocuments: [],
      analysisQueue: [],
      validationSummary: {
        passed: 0,
        failed: 0,
        pending: 0,
        total: 0,
      },
      stats: {
        documentsTotal: 0,
        documentsAnalyzed: 0,
        validationsRun: 0,
        avgAnalysisTime: "N/A",
      },
    });
    setDataLoading(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      // Handle file upload - redirect to documents page with upload
      router.push("/documents?upload=true");
    }
  }, [router]);

  if (isLoading || dataLoading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
            <p className="text-gray-600">Loading Analyst Dashboard...</p>
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
            <h1 className="text-3xl font-bold text-gray-900">Analyst Dashboard</h1>
            <p className="mt-2 text-gray-600">
              Manage documents, track analysis, and review validation reports
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-700">
              BA View
            </span>
            <Link href="/documents">
              <Button className="flex items-center space-x-2">
                <Upload className="h-4 w-4" />
                <span>Upload Document</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Total Documents"
            value={data.stats.documentsTotal}
            icon={<FileText className="h-5 w-5" />}
            color="blue"
          />
          <StatCard
            label="Analyzed"
            value={data.stats.documentsAnalyzed}
            icon={<CheckCircle2 className="h-5 w-5" />}
            color="green"
          />
          <StatCard
            label="Validations Run"
            value={data.stats.validationsRun}
            icon={<BarChart3 className="h-5 w-5" />}
            color="purple"
          />
          <StatCard
            label="Avg. Analysis Time"
            value={data.stats.avgAnalysisTime}
            icon={<Clock className="h-5 w-5" />}
            color="orange"
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Upload Widget */}
          <div
            className={`rounded-lg border-2 border-dashed p-8 transition-colors ${
              isDragging
                ? "border-blue-500 bg-blue-50"
                : "border-gray-300 bg-white hover:border-blue-400"
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div className="flex flex-col items-center justify-center text-center">
              <div className={`rounded-full p-4 ${isDragging ? "bg-blue-100" : "bg-gray-100"}`}>
                <FileUp className={`h-8 w-8 ${isDragging ? "text-blue-600" : "text-gray-400"}`} />
              </div>
              <h3 className="mt-4 text-lg font-medium text-gray-900">
                {isDragging ? "Drop files here" : "Upload Documents"}
              </h3>
              <p className="mt-2 text-sm text-gray-600">
                Drag and drop your PRDs, specs, or requirements documents
              </p>
              <Link href="/documents">
                <Button variant="outline" className="mt-4">
                  Browse Files
                </Button>
              </Link>
              <p className="mt-2 text-xs text-gray-500">
                Supports PDF, DOCX, TXT (max 10MB)
              </p>
            </div>
          </div>

          {/* Analysis Queue */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Analysis Queue</h2>
              <Link href="/analysis" className="text-sm text-blue-600 hover:text-blue-700">
                View All
              </Link>
            </div>

            {data.analysisQueue.length === 0 ? (
              <EmptyState
                icon={<Loader2 className="h-8 w-8 text-gray-400" />}
                title="No documents in queue"
                description="Upload documents to start AI analysis"
              />
            ) : (
              <div className="space-y-3">
                {data.analysisQueue.map((item: any) => (
                  <QueueItem key={item.id} item={item} />
                ))}
              </div>
            )}
          </div>

          {/* Recent Documents */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Recent Documents</h2>
              <Link href="/documents" className="text-sm text-blue-600 hover:text-blue-700">
                View All
              </Link>
            </div>

            {data.recentDocuments.length === 0 ? (
              <EmptyState
                icon={<FileText className="h-8 w-8 text-gray-400" />}
                title="No documents yet"
                description="Upload your first document to get started"
                action={
                  <Link href="/documents">
                    <Button variant="outline" size="sm" className="mt-4">
                      Upload Document
                    </Button>
                  </Link>
                }
              />
            ) : (
              <div className="space-y-3">
                {data.recentDocuments.map((doc: any) => (
                  <DocumentItem key={doc.id} doc={doc} />
                ))}
              </div>
            )}
          </div>

          {/* Validation Reports */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Validation Summary</h2>
              <Link href="/validation" className="text-sm text-blue-600 hover:text-blue-700">
                View Reports
              </Link>
            </div>

            {data.validationSummary.total === 0 ? (
              <EmptyState
                icon={<BarChart3 className="h-8 w-8 text-gray-400" />}
                title="No validations yet"
                description="Run validations to see results here"
              />
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div className="rounded-lg bg-green-50 p-4">
                    <p className="text-2xl font-bold text-green-600">{data.validationSummary.passed}</p>
                    <p className="text-sm text-gray-600">Passed</p>
                  </div>
                  <div className="rounded-lg bg-red-50 p-4">
                    <p className="text-2xl font-bold text-red-600">{data.validationSummary.failed}</p>
                    <p className="text-sm text-gray-600">Failed</p>
                  </div>
                  <div className="rounded-lg bg-yellow-50 p-4">
                    <p className="text-2xl font-bold text-yellow-600">{data.validationSummary.pending}</p>
                    <p className="text-sm text-gray-600">Pending</p>
                  </div>
                </div>

                {data.validationSummary.total > 0 && (
                  <div>
                    <div className="mb-1 flex justify-between text-sm">
                      <span className="text-gray-600">Pass Rate</span>
                      <span className="font-medium text-gray-900">
                        {((data.validationSummary.passed / data.validationSummary.total) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-gray-200">
                      <div
                        className="h-full bg-green-600"
                        style={{
                          width: `${(data.validationSummary.passed / data.validationSummary.total) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Quick Actions</h2>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
            <QuickActionButton
              href="/documents"
              icon={<Upload className="h-5 w-5" />}
              label="Upload Document"
            />
            <QuickActionButton
              href="/analysis"
              icon={<BarChart3 className="h-5 w-5" />}
              label="View Analysis"
            />
            <QuickActionButton
              href="/validation"
              icon={<CheckCircle2 className="h-5 w-5" />}
              label="Run Validation"
            />
            <QuickActionButton
              href="/tasks"
              icon={<Clock className="h-5 w-5" />}
              label="My Tasks"
            />
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
    orange: "bg-orange-100 text-orange-600",
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

function QueueItem({ item }: { item: any }) {
  const statusConfig: Record<string, { icon: React.ReactNode; color: string }> = {
    processing: {
      icon: <Loader2 className="h-4 w-4 animate-spin" />,
      color: "text-blue-600",
    },
    pending: {
      icon: <Clock className="h-4 w-4" />,
      color: "text-yellow-600",
    },
    completed: {
      icon: <CheckCircle2 className="h-4 w-4" />,
      color: "text-green-600",
    },
    failed: {
      icon: <XCircle className="h-4 w-4" />,
      color: "text-red-600",
    },
  };

  const config = statusConfig[item.status] || statusConfig.pending;

  return (
    <div className="flex items-center justify-between rounded-lg border p-3 hover:bg-gray-50">
      <div className="flex items-center space-x-3">
        <FileText className="h-4 w-4 text-gray-400" />
        <div>
          <p className="text-sm font-medium text-gray-900">{item.name}</p>
          <p className="text-xs text-gray-500">{item.progress}% complete</p>
        </div>
      </div>
      <span className={config.color}>{config.icon}</span>
    </div>
  );
}

function DocumentItem({ doc }: { doc: any }) {
  return (
    <div className="flex items-center justify-between rounded-lg border p-3 hover:bg-gray-50">
      <div className="flex items-center space-x-3">
        <FileText className="h-4 w-4 text-gray-400" />
        <div>
          <p className="text-sm font-medium text-gray-900">{doc.name}</p>
          <p className="text-xs text-gray-500">{doc.uploadedAt}</p>
        </div>
      </div>
      <span
        className={`rounded-full px-2 py-1 text-xs font-medium ${
          doc.analyzed ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"
        }`}
      >
        {doc.analyzed ? "Analyzed" : "Pending"}
      </span>
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
