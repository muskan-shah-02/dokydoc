/**
 * Billing Analytics Dashboard
 * Sprint 2 - Complete AI Usage Transparency
 *
 * Features:
 * - Time range filters (today, week, month, custom)
 * - Feature breakdown (document analysis, code analysis, validation, etc.)
 * - Token usage analytics (input/output)
 * - Daily usage charts
 * - Top documents by cost
 * - Detailed usage logs
 */

"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Cpu,
  Zap,
  FileText,
  Code,
  Shield,
  MessageSquare,
  BarChart3,
  PieChart,
  Calendar,
  Filter,
  RefreshCw,
  ChevronDown,
  IndianRupee,
  Clock,
  Activity,
  Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import Link from "next/link";

// Time range options
const TIME_RANGES = [
  { value: "today", label: "Today" },
  { value: "yesterday", label: "Yesterday" },
  { value: "last_7_days", label: "Last 7 Days" },
  { value: "last_15_days", label: "Last 15 Days" },
  { value: "this_week", label: "This Week" },
  { value: "this_month", label: "This Month" },
  { value: "last_30_days", label: "Last 30 Days" },
  { value: "last_90_days", label: "Last 90 Days" },
];

// Feature type labels and icons
const FEATURE_CONFIG: Record<string, { label: string; color: string; bgColor: string }> = {
  document_analysis: { label: "Document Analysis", color: "text-blue-600", bgColor: "bg-blue-100" },
  code_analysis: { label: "Code Analysis", color: "text-purple-600", bgColor: "bg-purple-100" },
  validation: { label: "Validation", color: "text-green-600", bgColor: "bg-green-100" },
  chat: { label: "Chat", color: "text-orange-600", bgColor: "bg-orange-100" },
  summary: { label: "Summary", color: "text-teal-600", bgColor: "bg-teal-100" },
  other: { label: "Other", color: "text-gray-600", bgColor: "bg-gray-100" },
};

// Interfaces
interface TokenSummary {
  total_input_tokens: number;
  total_output_tokens: number;
  total_cached_tokens: number;
  total_tokens: number;
  avg_input_per_call: number;
  avg_output_per_call: number;
  input_output_ratio: number;
}

interface FeatureUsage {
  feature_type: string;
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost_inr: number;
  percentage_of_total: number;
}

interface OperationUsage {
  feature_type: string;
  operation: string;
  total_calls: number;
  total_tokens: number;
  total_cost_inr: number;
}

interface DailyUsage {
  date: string;
  total_cost_inr: number;
  total_tokens: number;
  call_count: number;
}

interface DocumentUsage {
  document_id: number;
  filename: string;
  feature_type: string;
  total_calls: number;
  total_tokens: number;
  total_cost_inr: number;
  last_used: string;
}

interface WeeklyUsage {
  week_number: number;
  week_start: string;
  week_end: string;
  total_cost_inr: number;
  total_tokens: number;
  call_count: number;
  change_from_previous_week: number | null;
}

interface CodeComponentUsage {
  component_id: number;
  name: string;
  component_type: string;
  total_cost_inr: number;
  token_count_input: number;
  token_count_output: number;
  total_tokens: number;
  analysis_status: string;
}

interface AnalyticsData {
  time_range: string;
  start_date: string;
  end_date: string;
  total_cost_inr: number;
  total_cost_usd: number;
  total_api_calls: number;
  tokens: TokenSummary;
  by_feature: FeatureUsage[];
  by_operation: OperationUsage[];
  daily_usage: DailyUsage[];
  top_documents: DocumentUsage[];
  top_code_components: CodeComponentUsage[];
}

export default function BillingAnalyticsPage() {
  const router = useRouter();
  const { isCXO, isAdmin } = useAuth();

  const [timeRange, setTimeRange] = useState("this_month");
  const [featureFilter, setFeatureFilter] = useState<string | null>(null);
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [weeklyData, setWeeklyData] = useState<WeeklyUsage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // Redirect if not CXO or Admin
  useEffect(() => {
    if (!isCXO() && !isAdmin()) {
      router.push("/dashboard");
    }
  }, [isCXO, isAdmin, router]);

  useEffect(() => {
    loadAnalytics();
  }, [timeRange, featureFilter]);

  // Auto-refresh every 30 seconds when enabled
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadAnalytics();
    }, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh, timeRange, featureFilter]);

  const loadAnalytics = async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams({ time_range: timeRange });
      if (featureFilter) {
        params.append("feature_type", featureFilter);
      }

      const [analytics, weekly] = await Promise.all([
        api.get(`/billing/analytics?${params.toString()}`),
        api.get("/billing/analytics/weekly?weeks=4"),
      ]);

      setAnalyticsData(analytics);
      setWeeklyData(weekly);
      setLastUpdated(new Date());
    } catch (error) {
      console.error("Failed to load analytics:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadAnalytics();
    setIsRefreshing(false);
  };

  // Calculate max daily cost for chart scaling
  const maxDailyCost = useMemo(() => {
    if (!analyticsData?.daily_usage?.length) return 1;
    return Math.max(...analyticsData.daily_usage.map((d) => d.total_cost_inr), 1);
  }, [analyticsData?.daily_usage]);

  if (!isCXO() && !isAdmin()) {
    return null;
  }

  return (
    <AppLayout>
      <div className="space-y-6 max-w-7xl">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <Link
              href="/settings/billing"
              className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-2"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Billing
            </Link>
            <h1 className="text-3xl font-bold text-gray-900">AI Usage Analytics</h1>
            <p className="mt-1 text-gray-600">
              Complete transparency into your AI API usage and costs
            </p>
          </div>

          <div className="flex items-center gap-3">
            {lastUpdated && (
              <span className="text-xs text-muted-foreground">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                autoRefresh
                  ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                  : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${autoRefresh ? "bg-green-500 animate-pulse" : "bg-gray-400"}`} />
              {autoRefresh ? "Live" : "Paused"}
            </button>
            <Button
              onClick={handleRefresh}
              variant="outline"
              size="sm"
              disabled={isRefreshing}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4 items-center p-4 rounded-lg border bg-white shadow-sm">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-gray-500" />
            <Label className="text-sm font-medium">Time Range:</Label>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="border rounded-md px-3 py-1.5 text-sm"
            >
              {TIME_RANGES.map((range) => (
                <option key={range.value} value={range.value}>
                  {range.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-gray-500" />
            <Label className="text-sm font-medium">Feature:</Label>
            <select
              value={featureFilter || ""}
              onChange={(e) => setFeatureFilter(e.target.value || null)}
              className="border rounded-md px-3 py-1.5 text-sm"
            >
              <option value="">All Features</option>
              {Object.entries(FEATURE_CONFIG).map(([key, config]) => (
                <option key={key} value={key}>
                  {config.label}
                </option>
              ))}
            </select>
          </div>

          {analyticsData && (
            <div className="ml-auto text-sm text-gray-500">
              {new Date(analyticsData.start_date).toLocaleDateString()} -{" "}
              {new Date(analyticsData.end_date).toLocaleDateString()}
            </div>
          )}
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
              <p className="text-gray-600">Loading analytics...</p>
            </div>
          </div>
        ) : analyticsData ? (
          <>
            {/* Summary Cards */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {/* Total Cost */}
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Total Cost</p>
                    <p className="mt-2 text-3xl font-bold text-gray-900">
                      <span className="text-lg">₹</span>
                      {analyticsData.total_cost_inr.toFixed(2)}
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      ${analyticsData.total_cost_usd.toFixed(4)} USD
                    </p>
                  </div>
                  <div className="rounded-lg bg-green-100 p-3">
                    <IndianRupee className="h-6 w-6 text-green-600" />
                  </div>
                </div>
              </div>

              {/* Total API Calls */}
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">API Calls</p>
                    <p className="mt-2 text-3xl font-bold text-gray-900">
                      {analyticsData.total_api_calls.toLocaleString()}
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      Avg: ₹{analyticsData.total_api_calls > 0
                        ? (analyticsData.total_cost_inr / analyticsData.total_api_calls).toFixed(4)
                        : "0"} per call
                    </p>
                  </div>
                  <div className="rounded-lg bg-blue-100 p-3">
                    <Zap className="h-6 w-6 text-blue-600" />
                  </div>
                </div>
              </div>

              {/* Total Tokens */}
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Total Tokens</p>
                    <p className="mt-2 text-3xl font-bold text-gray-900">
                      {(analyticsData.tokens.total_tokens / 1000).toFixed(1)}K
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      {(analyticsData.tokens.total_input_tokens / 1000).toFixed(1)}K in / {(analyticsData.tokens.total_output_tokens / 1000).toFixed(1)}K out
                    </p>
                  </div>
                  <div className="rounded-lg bg-purple-100 p-3">
                    <Cpu className="h-6 w-6 text-purple-600" />
                  </div>
                </div>
              </div>

              {/* Week over Week */}
              {weeklyData.length >= 2 && weeklyData[0].change_from_previous_week !== null && (
                <div className="rounded-lg border bg-white p-6 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-600">vs Last Week</p>
                      <p className={`mt-2 text-3xl font-bold ${
                        weeklyData[0].change_from_previous_week >= 0 ? "text-red-600" : "text-green-600"
                      }`}>
                        {weeklyData[0].change_from_previous_week >= 0 ? "+" : ""}
                        {weeklyData[0].change_from_previous_week.toFixed(1)}%
                      </p>
                      <p className="mt-1 text-xs text-gray-500">
                        This week: ₹{weeklyData[0].total_cost_inr.toFixed(2)}
                      </p>
                    </div>
                    <div className={`rounded-lg p-3 ${
                      weeklyData[0].change_from_previous_week >= 0 ? "bg-red-100" : "bg-green-100"
                    }`}>
                      {weeklyData[0].change_from_previous_week >= 0 ? (
                        <TrendingUp className="h-6 w-6 text-red-600" />
                      ) : (
                        <TrendingDown className="h-6 w-6 text-green-600" />
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Charts Row */}
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Feature Breakdown */}
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <PieChart className="h-5 w-5 text-gray-500" />
                  Cost by Feature
                </h3>
                {analyticsData.by_feature.length > 0 ? (
                  <div className="space-y-3">
                    {analyticsData.by_feature.map((feature) => {
                      const config = FEATURE_CONFIG[feature.feature_type] || FEATURE_CONFIG.other;
                      return (
                        <div key={feature.feature_type} className="space-y-1">
                          <div className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                              <div className={`w-3 h-3 rounded-full ${config.bgColor}`}></div>
                              <span className="font-medium">{config.label}</span>
                            </div>
                            <div className="flex items-center gap-4">
                              <span className="text-gray-600">{feature.total_calls} calls</span>
                              <span className="font-semibold">₹{feature.total_cost_inr.toFixed(2)}</span>
                            </div>
                          </div>
                          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full ${config.bgColor.replace("100", "500")}`}
                              style={{ width: `${feature.percentage_of_total}%` }}
                            />
                          </div>
                          <p className="text-xs text-gray-500 text-right">
                            {feature.percentage_of_total.toFixed(1)}% of total
                          </p>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-gray-500 text-center py-8">No usage data for selected period</p>
                )}
              </div>

              {/* Daily Usage Chart */}
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-gray-500" />
                  Daily Usage
                </h3>
                {analyticsData.daily_usage.length > 0 ? (
                  <div className="h-48 flex items-end gap-1">
                    {analyticsData.daily_usage.slice(-14).map((day, idx) => {
                      const height = (day.total_cost_inr / maxDailyCost) * 100;
                      return (
                        <div
                          key={day.date}
                          className="flex-1 flex flex-col items-center group"
                        >
                          <div className="relative w-full">
                            <div
                              className="w-full bg-blue-500 rounded-t hover:bg-blue-600 transition-colors cursor-pointer"
                              style={{ height: `${Math.max(height, 2)}%`, minHeight: "4px" }}
                            />
                            {/* Tooltip */}
                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                              <div className="bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
                                <div className="font-semibold">₹{day.total_cost_inr.toFixed(2)}</div>
                                <div>{day.call_count} calls</div>
                                <div>{(day.total_tokens / 1000).toFixed(1)}K tokens</div>
                              </div>
                            </div>
                          </div>
                          <p className="text-[10px] text-gray-500 mt-1 rotate-45 origin-left">
                            {new Date(day.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-gray-500 text-center py-8">No daily data for selected period</p>
                )}
              </div>
            </div>

            {/* Token Analytics */}
            <div className="rounded-lg border bg-white p-6 shadow-sm">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Cpu className="h-5 w-5 text-gray-500" />
                Token Usage Breakdown
              </h3>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="p-4 rounded-lg bg-blue-50">
                  <p className="text-sm text-blue-700 font-medium">Input Tokens</p>
                  <p className="text-2xl font-bold text-blue-900">
                    {analyticsData.tokens.total_input_tokens.toLocaleString()}
                  </p>
                  <p className="text-xs text-blue-600">
                    Avg: {analyticsData.tokens.avg_input_per_call.toFixed(0)} per call
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-yellow-50">
                  <p className="text-sm text-yellow-700 font-medium">Output Tokens</p>
                  <p className="text-2xl font-bold text-yellow-900">
                    {analyticsData.tokens.total_output_tokens.toLocaleString()}
                  </p>
                  <p className="text-xs text-yellow-600">
                    Avg: {analyticsData.tokens.avg_output_per_call.toFixed(0)} per call
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-green-50">
                  <p className="text-sm text-green-700 font-medium">Cached Tokens</p>
                  <p className="text-2xl font-bold text-green-900">
                    {analyticsData.tokens.total_cached_tokens.toLocaleString()}
                  </p>
                  <p className="text-xs text-green-600">
                    90% discount applied
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-purple-50">
                  <p className="text-sm text-purple-700 font-medium">I/O Ratio</p>
                  <p className="text-2xl font-bold text-purple-900">
                    {analyticsData.tokens.input_output_ratio.toFixed(2)}:1
                  </p>
                  <p className="text-xs text-purple-600">
                    Input to output ratio
                  </p>
                </div>
              </div>
            </div>

            {/* Operations Breakdown */}
            {analyticsData.by_operation.length > 0 && (
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Layers className="h-5 w-5 text-gray-500" />
                  Top Operations by Cost
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Operation</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Feature</th>
                        <th className="px-4 py-3 text-right font-semibold text-gray-700">Calls</th>
                        <th className="px-4 py-3 text-right font-semibold text-gray-700">Tokens</th>
                        <th className="px-4 py-3 text-right font-semibold text-gray-700">Cost (INR)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {analyticsData.by_operation.map((op, idx) => {
                        const config = FEATURE_CONFIG[op.feature_type] || FEATURE_CONFIG.other;
                        return (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-4 py-3 font-medium text-gray-900">
                              {op.operation.replace(/_/g, " ")}
                            </td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.bgColor} ${config.color}`}>
                                {config.label}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-right text-gray-700">{op.total_calls}</td>
                            <td className="px-4 py-3 text-right text-gray-700">{op.total_tokens.toLocaleString()}</td>
                            <td className="px-4 py-3 text-right font-semibold text-gray-900">₹{op.total_cost_inr.toFixed(2)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Top Documents */}
            {analyticsData.top_documents.length > 0 && (
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <FileText className="h-5 w-5 text-gray-500" />
                  Top Documents by Cost
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Document</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Feature</th>
                        <th className="px-4 py-3 text-right font-semibold text-gray-700">Calls</th>
                        <th className="px-4 py-3 text-right font-semibold text-gray-700">Tokens</th>
                        <th className="px-4 py-3 text-right font-semibold text-gray-700">Cost (INR)</th>
                        <th className="px-4 py-3 text-right font-semibold text-gray-700">Last Used</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {analyticsData.top_documents.map((doc) => {
                        const config = FEATURE_CONFIG[doc.feature_type] || FEATURE_CONFIG.other;
                        return (
                          <tr key={`${doc.document_id}-${doc.feature_type}`} className="hover:bg-gray-50">
                            <td className="px-4 py-3">
                              <Link
                                href={`/dashboard/documents/${doc.document_id}`}
                                className="font-medium text-blue-600 hover:underline"
                              >
                                {doc.filename}
                              </Link>
                            </td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.bgColor} ${config.color}`}>
                                {config.label}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-right text-gray-700">{doc.total_calls}</td>
                            <td className="px-4 py-3 text-right text-gray-700">{doc.total_tokens.toLocaleString()}</td>
                            <td className="px-4 py-3 text-right font-semibold text-gray-900">₹{doc.total_cost_inr.toFixed(2)}</td>
                            <td className="px-4 py-3 text-right text-gray-500">
                              {new Date(doc.last_used).toLocaleDateString()}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Top Code Components */}
            {analyticsData.top_code_components && analyticsData.top_code_components.length > 0 && (
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Code className="h-5 w-5 text-gray-500" />
                  Top Code Components by Cost
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Component</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Type</th>
                        <th className="px-4 py-3 text-right font-semibold text-gray-700">Input Tokens</th>
                        <th className="px-4 py-3 text-right font-semibold text-gray-700">Output Tokens</th>
                        <th className="px-4 py-3 text-right font-semibold text-gray-700">Cost (INR)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {analyticsData.top_code_components.map((comp) => (
                        <tr key={comp.component_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3">
                            <Link
                              href={`/dashboard/code/${comp.component_id}`}
                              className="font-medium text-purple-600 hover:underline"
                            >
                              {comp.name}
                            </Link>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-600">
                              {comp.component_type}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right text-gray-700">{comp.token_count_input.toLocaleString()}</td>
                          <td className="px-4 py-3 text-right text-gray-700">{comp.token_count_output.toLocaleString()}</td>
                          <td className="px-4 py-3 text-right font-semibold text-gray-900">₹{comp.total_cost_inr.toFixed(2)}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                              comp.analysis_status === "completed" ? "bg-green-100 text-green-600" :
                              comp.analysis_status === "processing" ? "bg-blue-100 text-blue-600" :
                              comp.analysis_status === "failed" ? "bg-red-100 text-red-600" :
                              "bg-gray-100 text-gray-600"
                            }`}>
                              {comp.analysis_status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Weekly Summary */}
            {weeklyData.length > 0 && (
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Activity className="h-5 w-5 text-gray-500" />
                  Weekly Summary (Last 4 Weeks)
                </h3>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {weeklyData.map((week) => (
                    <div key={week.week_number} className="p-4 rounded-lg border bg-gray-50">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-gray-700">
                          Week {week.week_number}
                        </span>
                        {week.change_from_previous_week !== null && (
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                            week.change_from_previous_week >= 0
                              ? "bg-red-100 text-red-700"
                              : "bg-green-100 text-green-700"
                          }`}>
                            {week.change_from_previous_week >= 0 ? "+" : ""}
                            {week.change_from_previous_week.toFixed(1)}%
                          </span>
                        )}
                      </div>
                      <p className="text-2xl font-bold text-gray-900">₹{week.total_cost_inr.toFixed(2)}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        {week.call_count} calls | {(week.total_tokens / 1000).toFixed(1)}K tokens
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        {new Date(week.week_start).toLocaleDateString("en-US", { month: "short", day: "numeric" })} - {new Date(week.week_end).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="rounded-lg border bg-white p-12 text-center shadow-sm">
            <BarChart3 className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-medium text-gray-900">No Analytics Data</h3>
            <p className="mt-2 text-gray-600">
              Start analyzing documents to see usage analytics here.
            </p>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
