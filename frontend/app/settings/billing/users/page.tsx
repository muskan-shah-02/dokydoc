"use client";

/**
 * Billing By User Dashboard - Admin/CXO View
 *
 * Provides full transparency into AI costs by team member.
 * Designed for executives and administrators to monitor usage.
 */

import React, { useState, useEffect, useMemo } from "react";
import {
  Users,
  TrendingUp,
  TrendingDown,
  IndianRupee,
  Zap,
  FileText,
  Clock,
  ChevronRight,
  Search,
  Filter,
  Download,
  RefreshCw,
  User,
  BarChart3,
  PieChart,
  ArrowUpRight,
  ArrowDownRight,
  Calendar,
  Activity,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import Link from "next/link";

// ============================================================================
// TYPES
// ============================================================================

interface UserUsageSummary {
  user_id: number | null;
  user_email: string;
  user_name: string;
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  total_cost_inr: number;
  percentage_of_total: number;
  last_activity: string | null;
}

interface AllUsersAnalyticsResponse {
  time_range: string;
  start_date: string;
  end_date: string;
  total_tenant_cost_inr: number;
  total_tenant_calls: number;
  users: UserUsageSummary[];
}

interface UserDetailAnalytics {
  user_id: number;
  user_email: string;
  user_name: string;
  time_range: string;
  start_date: string;
  end_date: string;
  total_cost_inr: number;
  total_cost_usd: number;
  total_api_calls: number;
  total_tokens: number;
  by_feature: FeatureUsageSummary[];
  daily_usage: DailyUsagePoint[];
  top_documents: DocumentUsageSummary[];
}

interface FeatureUsageSummary {
  feature_type: string;
  total_calls: number;
  total_tokens: number;
  total_cost_inr: number;
  percentage_of_total: number;
}

interface DailyUsagePoint {
  date: string;
  total_cost_inr: number;
  total_tokens: number;
  call_count: number;
}

interface DocumentUsageSummary {
  document_id: number;
  filename: string;
  feature_type: string;
  total_calls: number;
  total_tokens: number;
  total_cost_inr: number;
  last_used: string;
}

// ============================================================================
// COMPONENTS
// ============================================================================

// User Card with usage visualization
function UserCard({
  user,
  totalTenantCost,
  onClick,
}: {
  user: UserUsageSummary;
  totalTenantCost: number;
  onClick: () => void;
}) {
  const percentage = user.percentage_of_total;

  return (
    <div
      onClick={onClick}
      className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-lg hover:border-blue-200 transition-all duration-200 cursor-pointer group"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold">
            {user.user_name?.charAt(0) || user.user_email?.charAt(0) || "U"}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
              {user.user_name || "Unknown User"}
            </h3>
            <p className="text-sm text-gray-500">{user.user_email}</p>
          </div>
        </div>
        <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-blue-500 transition-colors" />
      </div>

      {/* Cost Bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-2xl font-bold text-gray-900">
            ₹{user.total_cost_inr.toFixed(2)}
          </span>
          <Badge
            className={`${
              percentage >= 30
                ? "bg-red-100 text-red-700"
                : percentage >= 15
                ? "bg-amber-100 text-amber-700"
                : "bg-green-100 text-green-700"
            }`}
          >
            {percentage.toFixed(1)}% of total
          </Badge>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-500 ${
              percentage >= 30
                ? "bg-red-500"
                : percentage >= 15
                ? "bg-amber-500"
                : "bg-green-500"
            }`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="bg-gray-50 rounded-lg p-2">
          <p className="text-lg font-semibold text-gray-900">{user.total_calls}</p>
          <p className="text-xs text-gray-500">API Calls</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-2">
          <p className="text-lg font-semibold text-gray-900">
            {(user.total_tokens / 1000).toFixed(1)}K
          </p>
          <p className="text-xs text-gray-500">Tokens</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-2">
          <p className="text-xs text-gray-600">
            {user.last_activity
              ? new Date(user.last_activity).toLocaleDateString()
              : "Never"}
          </p>
          <p className="text-xs text-gray-500">Last Active</p>
        </div>
      </div>
    </div>
  );
}

// User Detail Modal/Panel
function UserDetailPanel({
  userId,
  timeRange,
  onClose,
}: {
  userId: number;
  timeRange: string;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<UserDetailAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchDetail() {
      setLoading(true);
      try {
        const data = await api.get<UserDetailAnalytics>(
          `/billing/analytics/users/${userId}?time_range=${timeRange}`
        );
        setDetail(data);
      } catch (error) {
        console.error("Failed to fetch user detail:", error);
      } finally {
        setLoading(false);
      }
    }
    fetchDetail();
  }, [userId, timeRange]);

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-xl p-8">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
        </div>
      </div>
    );
  }

  if (!detail) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-100 p-6 flex items-center justify-between z-10">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg">
              {detail.user_name?.charAt(0) || detail.user_email?.charAt(0) || "U"}
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900">{detail.user_name}</h2>
              <p className="text-gray-500">{detail.user_email}</p>
            </div>
          </div>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-4">
              <p className="text-sm text-blue-600 font-medium">Total Cost</p>
              <p className="text-2xl font-bold text-blue-900">₹{detail.total_cost_inr.toFixed(2)}</p>
            </div>
            <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-4">
              <p className="text-sm text-purple-600 font-medium">API Calls</p>
              <p className="text-2xl font-bold text-purple-900">{detail.total_api_calls}</p>
            </div>
            <div className="bg-gradient-to-br from-emerald-50 to-emerald-100 rounded-xl p-4">
              <p className="text-sm text-emerald-600 font-medium">Tokens Used</p>
              <p className="text-2xl font-bold text-emerald-900">
                {(detail.total_tokens / 1000).toFixed(1)}K
              </p>
            </div>
            <div className="bg-gradient-to-br from-amber-50 to-amber-100 rounded-xl p-4">
              <p className="text-sm text-amber-600 font-medium">Avg Cost/Call</p>
              <p className="text-2xl font-bold text-amber-900">
                ₹{detail.total_api_calls > 0 ? (detail.total_cost_inr / detail.total_api_calls).toFixed(2) : "0.00"}
              </p>
            </div>
          </div>

          {/* Feature Breakdown */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Usage by Feature</h3>
            <div className="space-y-2">
              {detail.by_feature.length > 0 ? (
                detail.by_feature.map((feature) => (
                  <div
                    key={feature.feature_type}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-8 rounded-full bg-blue-500" />
                      <div>
                        <p className="font-medium text-gray-900 capitalize">
                          {feature.feature_type.replace(/_/g, " ")}
                        </p>
                        <p className="text-sm text-gray-500">
                          {feature.total_calls} calls | {(feature.total_tokens / 1000).toFixed(1)}K tokens
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-gray-900">₹{feature.total_cost_inr.toFixed(2)}</p>
                      <p className="text-sm text-gray-500">{feature.percentage_of_total.toFixed(1)}%</p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-gray-500 text-center py-4">No usage data for this period</p>
              )}
            </div>
          </div>

          {/* Top Documents */}
          {detail.top_documents.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Top Documents by Cost</h3>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Document</TableHead>
                    <TableHead>Calls</TableHead>
                    <TableHead>Tokens</TableHead>
                    <TableHead className="text-right">Cost</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detail.top_documents.map((doc) => (
                    <TableRow key={doc.document_id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-gray-400" />
                          <span className="font-medium">{doc.filename}</span>
                        </div>
                      </TableCell>
                      <TableCell>{doc.total_calls}</TableCell>
                      <TableCell>{(doc.total_tokens / 1000).toFixed(1)}K</TableCell>
                      <TableCell className="text-right font-medium">₹{doc.total_cost_inr.toFixed(2)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN PAGE
// ============================================================================

export default function BillingByUserPage() {
  const [data, setData] = useState<AllUsersAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("this_month");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [sortBy, setSortBy] = useState<"cost" | "calls" | "tokens">("cost");

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const response = await api.get<AllUsersAnalyticsResponse>(
          `/billing/analytics/users?time_range=${timeRange}`
        );
        setData(response);
      } catch (error) {
        console.error("Failed to fetch user analytics:", error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [timeRange]);

  // Filter and sort users
  const filteredUsers = useMemo(() => {
    if (!data) return [];

    let users = [...data.users];

    // Filter by search
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      users = users.filter(
        (u) =>
          u.user_email?.toLowerCase().includes(query) ||
          u.user_name?.toLowerCase().includes(query)
      );
    }

    // Sort
    users.sort((a, b) => {
      switch (sortBy) {
        case "cost":
          return b.total_cost_inr - a.total_cost_inr;
        case "calls":
          return b.total_calls - a.total_calls;
        case "tokens":
          return b.total_tokens - a.total_tokens;
        default:
          return b.total_cost_inr - a.total_cost_inr;
      }
    });

    return users;
  }, [data, searchQuery, sortBy]);

  // Calculate top user percentage
  const topUserPercentage = useMemo(() => {
    if (!filteredUsers.length) return 0;
    return filteredUsers[0].percentage_of_total;
  }, [filteredUsers]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50/50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
              <Link href="/settings/billing" className="hover:text-blue-600">
                Billing
              </Link>
              <ChevronRight className="w-4 h-4" />
              <span className="text-gray-900 font-medium">Team Usage</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Billing by Team Member</h1>
            <p className="text-gray-500 mt-1">
              Monitor AI usage and costs across your team
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="today">Today</SelectItem>
                <SelectItem value="this_week">This Week</SelectItem>
                <SelectItem value="this_month">This Month</SelectItem>
                <SelectItem value="last_30_days">Last 30 Days</SelectItem>
                <SelectItem value="last_90_days">Last 90 Days</SelectItem>
              </SelectContent>
            </Select>

            <Button variant="outline">
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-gradient-to-br from-blue-500 to-blue-600 text-white border-0">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-blue-100 text-sm font-medium">Total Team Cost</p>
                  <p className="text-3xl font-bold mt-1">
                    ₹{data?.total_tenant_cost_inr.toFixed(2) || "0.00"}
                  </p>
                </div>
                <div className="p-3 bg-white/20 rounded-xl">
                  <IndianRupee className="w-6 h-6" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-500 text-sm font-medium">Active Users</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {data?.users.length || 0}
                  </p>
                </div>
                <div className="p-3 bg-purple-100 rounded-xl">
                  <Users className="w-6 h-6 text-purple-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-500 text-sm font-medium">Total API Calls</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {data?.total_tenant_calls.toLocaleString() || 0}
                  </p>
                </div>
                <div className="p-3 bg-emerald-100 rounded-xl">
                  <Activity className="w-6 h-6 text-emerald-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-500 text-sm font-medium">Top User Share</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {topUserPercentage.toFixed(1)}%
                  </p>
                </div>
                <div className="p-3 bg-amber-100 rounded-xl">
                  <PieChart className="w-6 h-6 text-amber-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="Search users..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>

          <Select value={sortBy} onValueChange={(v: any) => setSortBy(v)}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="cost">Sort by Cost</SelectItem>
              <SelectItem value="calls">Sort by Calls</SelectItem>
              <SelectItem value="tokens">Sort by Tokens</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Users Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredUsers.map((user) => (
            <UserCard
              key={user.user_id || user.user_email}
              user={user}
              totalTenantCost={data?.total_tenant_cost_inr || 0}
              onClick={() => user.user_id && setSelectedUserId(user.user_id)}
            />
          ))}
        </div>

        {filteredUsers.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <Users className="w-12 h-12 mx-auto mb-4 opacity-20" />
            <p>No users found</p>
          </div>
        )}

        {/* Table View */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Detailed Breakdown</CardTitle>
            <CardDescription>Complete usage statistics for all team members</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead className="text-right">API Calls</TableHead>
                  <TableHead className="text-right">Input Tokens</TableHead>
                  <TableHead className="text-right">Output Tokens</TableHead>
                  <TableHead className="text-right">Total Cost</TableHead>
                  <TableHead className="text-right">% of Total</TableHead>
                  <TableHead className="text-right">Last Activity</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredUsers.map((user) => (
                  <TableRow
                    key={user.user_id || user.user_email}
                    className="cursor-pointer hover:bg-gray-50"
                    onClick={() => user.user_id && setSelectedUserId(user.user_id)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-sm font-medium">
                          {user.user_name?.charAt(0) || user.user_email?.charAt(0) || "U"}
                        </div>
                        <div>
                          <p className="font-medium">{user.user_name || "Unknown"}</p>
                          <p className="text-xs text-gray-500">{user.user_email}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">{user.total_calls.toLocaleString()}</TableCell>
                    <TableCell className="text-right">
                      {user.total_input_tokens.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      {user.total_output_tokens.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      ₹{user.total_cost_inr.toFixed(2)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge
                        variant="outline"
                        className={`${
                          user.percentage_of_total >= 30
                            ? "border-red-200 text-red-700 bg-red-50"
                            : user.percentage_of_total >= 15
                            ? "border-amber-200 text-amber-700 bg-amber-50"
                            : "border-green-200 text-green-700 bg-green-50"
                        }`}
                      >
                        {user.percentage_of_total.toFixed(1)}%
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right text-gray-500 text-sm">
                      {user.last_activity
                        ? new Date(user.last_activity).toLocaleDateString()
                        : "Never"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* User Detail Panel */}
        {selectedUserId && (
          <UserDetailPanel
            userId={selectedUserId}
            timeRange={timeRange}
            onClose={() => setSelectedUserId(null)}
          />
        )}
      </div>
    </div>
  );
}
