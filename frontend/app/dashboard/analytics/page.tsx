"use client";

import { useState, useEffect, useCallback } from "react";
import {
  BarChart3,
  TrendingUp,
  Brain,
  Activity,
  DollarSign,
  Zap,
  FileText,
  GitBranch,
  MessageSquare,
  Network,
  Loader2,
  RefreshCw,
  Calendar,
} from "lucide-react";
import { api } from "@/lib/api";

// --- Types ---

interface Overview {
  total_cost_inr: number;
  total_tokens: number;
  total_operations: number;
  this_month_cost: number;
  active_features: number;
}

interface CostEntry {
  date: string;
  cost_inr: number;
  feature_type: string;
  operation_count: number;
}

interface ConceptEntry {
  date: string;
  concept_count: number;
  relationship_count: number;
}

interface ActivityMetrics {
  total_documents: number;
  total_repos: number;
  total_concepts: number;
  total_chat_messages: number;
  total_validations: number;
}

type Period = "week" | "month" | "quarter";

// P4-09: BOE Savings Analytics Widget types
interface BOESavingsSummary {
  confirmed_mapping_count: number;
  auto_approved_count: number;
  coverage_pct: number;
  auto_approve_threshold: number;
  estimated_calls_saved_this_month: number;
  estimated_inr_saved: number;
}

const FEATURE_COLORS: Record<string, string> = {
  document_analysis: "#6366f1",
  code_analysis: "#f59e0b",
  validation: "#10b981",
  chat: "#3b82f6",
  summary: "#8b5cf6",
  other: "#9ca3af",
};

const FEATURE_LABELS: Record<string, string> = {
  document_analysis: "Document Analysis",
  code_analysis: "Code Analysis",
  validation: "Validation",
  chat: "Chat",
  summary: "Summary",
  other: "Other",
};

function formatINR(val: number) {
  if (val >= 1000) return `₹${(val / 1000).toFixed(1)}k`;
  return `₹${val.toFixed(2)}`;
}

function formatNumber(val: number) {
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `${(val / 1_000).toFixed(1)}k`;
  return val.toString();
}

// Simple bar chart using CSS
function SimpleBarChart({
  data,
  valueKey,
  colorKey,
  colorMap,
  maxValue,
  labelKey = "date",
}: {
  data: any[];
  valueKey: string;
  colorKey?: string;
  colorMap?: Record<string, string>;
  maxValue: number;
  labelKey?: string;
}) {
  if (!data.length) return (
    <div className="flex h-32 items-center justify-center text-xs text-gray-400">No data</div>
  );

  return (
    <div className="flex items-end gap-1 h-32 w-full">
      {data.map((d, i) => {
        const val = d[valueKey] ?? 0;
        const height = maxValue > 0 ? Math.max(4, (val / maxValue) * 100) : 4;
        const color = colorKey && colorMap ? (colorMap[d[colorKey]] ?? "#9ca3af") : "#6366f1";
        return (
          <div key={i} className="flex flex-col items-center flex-1 min-w-0 gap-1" title={`${d[labelKey]}: ${val}`}>
            <div
              className="w-full rounded-t-sm transition-all"
              style={{ height: `${height}%`, backgroundColor: color }}
            />
            {data.length <= 14 && (
              <span className="text-[9px] text-gray-400 truncate w-full text-center">
                {String(d[labelKey]).slice(5)}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// Line sparkline using SVG
function Sparkline({ data, valueKey }: { data: any[]; valueKey: string }) {
  if (data.length < 2) return <div className="h-16 flex items-center justify-center text-xs text-gray-400">Insufficient data</div>;
  const vals = data.map((d) => d[valueKey] ?? 0);
  const max = Math.max(...vals, 1);
  const min = Math.min(...vals);
  const range = max - min || 1;
  const w = 300;
  const h = 60;
  const pts = vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 8) - 4;
    return `${x},${y}`;
  });
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-16">
      <polyline
        points={pts.join(" ")}
        fill="none"
        stroke="#6366f1"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle
        cx={pts[pts.length - 1].split(",")[0]}
        cy={pts[pts.length - 1].split(",")[1]}
        r="3"
        fill="#6366f1"
      />
    </svg>
  );
}

export default function AnalyticsDashboardPage() {
  const [period, setPeriod] = useState<Period>("month");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [costs, setCosts] = useState<CostEntry[]>([]);
  const [concepts, setConcepts] = useState<ConceptEntry[]>([]);
  const [activity, setActivity] = useState<ActivityMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  // P4-09: BOE savings state
  const [boeSavings, setBoeSavings] = useState<BOESavingsSummary | null>(null);

  const fetchAll = useCallback(async (p: Period, isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const [ov, cs, cn, act, boe] = await Promise.allSettled([
        api.get<Overview>("/analytics/overview"),
        api.get<CostEntry[]>(`/analytics/costs?period=${p}`),
        api.get<ConceptEntry[]>(`/analytics/concepts?period=${p}`),
        api.get<ActivityMetrics>("/analytics/activity"),
        api.get<BOESavingsSummary>("/analysis/boe-savings-summary"),  // P4-09
      ]);
      if (ov.status === "fulfilled") setOverview(ov.value);
      if (cs.status === "fulfilled") setCosts(Array.isArray(cs.value) ? cs.value : []);
      if (cn.status === "fulfilled") setConcepts(Array.isArray(cn.value) ? cn.value : []);
      if (act.status === "fulfilled") setActivity(act.value);
      if (boe.status === "fulfilled") setBoeSavings(boe.value);  // P4-09
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchAll(period);
  }, [period, fetchAll]);

  // Aggregate cost by feature type for pie breakdown
  const costByFeature = costs.reduce<Record<string, number>>((acc, d) => {
    acc[d.feature_type] = (acc[d.feature_type] ?? 0) + d.cost_inr;
    return acc;
  }, {});
  const totalFeatureCost = Object.values(costByFeature).reduce((a, b) => a + b, 0) || 1;

  // Aggregate daily cost (all features)
  const dailyCostMap = costs.reduce<Record<string, number>>((acc, d) => {
    acc[d.date] = (acc[d.date] ?? 0) + d.cost_inr;
    return acc;
  }, {});
  const dailyCosts = Object.entries(dailyCostMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, cost_inr]) => ({ date, cost_inr }));
  const maxDailyCost = Math.max(...dailyCosts.map((d) => d.cost_inr), 1);
  const maxConceptCount = Math.max(...concepts.map((d) => d.concept_count), 1);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center gap-2">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
        <span className="text-sm text-gray-500">Loading analytics...</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50/50 p-4 lg:p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-indigo-50 p-3">
            <BarChart3 className="h-6 w-6 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
            <p className="mt-0.5 text-sm text-gray-500">
              AI cost, knowledge growth, and team activity
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Period selector */}
          <div className="flex rounded-lg border bg-white p-1 gap-1">
            {(["week", "month", "quarter"] as Period[]).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-all capitalize ${
                  period === p
                    ? "bg-indigo-600 text-white"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
          <button
            onClick={() => fetchAll(period, true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 rounded-lg border bg-white px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="mb-6 grid gap-4 grid-cols-2 lg:grid-cols-5">
        {[
          {
            label: "Total Cost",
            value: overview ? formatINR(overview.total_cost_inr) : "—",
            sub: overview ? `${formatINR(overview.this_month_cost)} this month` : "",
            icon: DollarSign,
            color: "text-indigo-600",
            bg: "bg-indigo-50",
          },
          {
            label: "Total Tokens",
            value: overview ? formatNumber(overview.total_tokens) : "—",
            sub: `${overview?.total_operations ?? 0} operations`,
            icon: Zap,
            color: "text-amber-600",
            bg: "bg-amber-50",
          },
          {
            label: "Documents",
            value: activity ? formatNumber(activity.total_documents) : "—",
            sub: "uploaded & analyzed",
            icon: FileText,
            color: "text-blue-600",
            bg: "bg-blue-50",
          },
          {
            label: "Repositories",
            value: activity ? formatNumber(activity.total_repos) : "—",
            sub: "code repositories",
            icon: GitBranch,
            color: "text-green-600",
            bg: "bg-green-50",
          },
          {
            label: "Concepts",
            value: activity ? formatNumber(activity.total_concepts) : "—",
            sub: `${activity?.total_chat_messages ?? 0} chat messages`,
            icon: Brain,
            color: "text-purple-600",
            bg: "bg-purple-50",
          },
        ].map((card) => (
          <div key={card.label} className="rounded-lg border bg-white p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-gray-500">{card.label}</p>
                <p className="mt-1 text-xl font-bold text-gray-900">{card.value}</p>
                {card.sub && <p className="mt-0.5 text-[10px] text-gray-400">{card.sub}</p>}
              </div>
              <div className={`rounded-lg p-2.5 ${card.bg}`}>
                <card.icon className={`h-5 w-5 ${card.color}`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* P4-09: BOE Savings Analytics Widget */}
      {boeSavings && (
        <div className="mb-6 rounded-lg border bg-white p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-green-50 p-2.5">
                <Zap className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">
                  BOE Cost Savings — Business Ontology Engine
                </h3>
                <p className="text-xs text-gray-400">
                  Gemini calls avoided through high-confidence concept auto-approval
                </p>
              </div>
            </div>
            <span className="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
              Active
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-lg bg-gray-50 p-3">
              <p className="text-xs font-medium text-gray-500">Confirmed Mappings</p>
              <p className="mt-1 text-xl font-bold text-gray-900">
                {boeSavings.confirmed_mapping_count.toLocaleString()}
              </p>
              <p className="mt-0.5 text-[10px] text-gray-400">doc ↔ code concept links</p>
            </div>
            <div className="rounded-lg bg-green-50 p-3">
              <p className="text-xs font-medium text-gray-500">Auto-Approvable</p>
              <p className="mt-1 text-xl font-bold text-green-700">
                {boeSavings.auto_approved_count.toLocaleString()}
              </p>
              <p className="mt-0.5 text-[10px] text-gray-400">
                confidence ≥ {(boeSavings.auto_approve_threshold * 100).toFixed(0)}%
              </p>
            </div>
            <div className="rounded-lg bg-blue-50 p-3">
              <p className="text-xs font-medium text-gray-500">Calls Saved / Month</p>
              <p className="mt-1 text-xl font-bold text-blue-700">
                ~{boeSavings.estimated_calls_saved_this_month.toLocaleString()}
              </p>
              <p className="mt-0.5 text-[10px] text-gray-400">estimated Gemini skips</p>
            </div>
            <div className="rounded-lg bg-amber-50 p-3">
              <p className="text-xs font-medium text-gray-500">Est. Savings / Month</p>
              <p className="mt-1 text-xl font-bold text-amber-700">
                ₹{boeSavings.estimated_inr_saved.toFixed(2)}
              </p>
              <p className="mt-0.5 text-[10px] text-gray-400">at ₹0.03/call</p>
            </div>
          </div>

          {/* Coverage progress bar */}
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>BOE Coverage</span>
              <span className="font-semibold text-gray-700">
                {boeSavings.coverage_pct}%
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-gray-100">
              <div
                className="h-2 rounded-full bg-green-500 transition-all duration-500"
                style={{ width: `${Math.min(boeSavings.coverage_pct, 100)}%` }}
              />
            </div>
            <p className="mt-1 text-[10px] text-gray-400">
              {boeSavings.coverage_pct < 30
                ? "BOE is learning — run more validations to improve auto-approval rate"
                : boeSavings.coverage_pct < 70
                ? "BOE is building confidence — costs reducing with each validation run"
                : "BOE is mature — high percentage of validations run cost-free"}
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Daily Cost Chart */}
        <div className="lg:col-span-2 rounded-lg border bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">Daily AI Cost</h3>
              <p className="text-xs text-gray-400">Cost in INR over the selected period</p>
            </div>
            <div className="flex items-center gap-1 text-xs text-gray-500">
              <Calendar className="h-3.5 w-3.5" />
              {period}
            </div>
          </div>
          <SimpleBarChart
            data={dailyCosts}
            valueKey="cost_inr"
            maxValue={maxDailyCost}
          />
        </div>

        {/* Cost by Feature */}
        <div className="rounded-lg border bg-white p-5">
          <h3 className="mb-4 text-sm font-semibold text-gray-900">Cost by Feature</h3>
          {Object.keys(costByFeature).length === 0 ? (
            <div className="flex h-32 items-center justify-center text-xs text-gray-400">No cost data</div>
          ) : (
            <div className="space-y-3">
              {Object.entries(costByFeature)
                .sort(([, a], [, b]) => b - a)
                .map(([ft, cost]) => (
                  <div key={ft}>
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span className="font-medium text-gray-700">
                        {FEATURE_LABELS[ft] ?? ft}
                      </span>
                      <span className="text-gray-500">{formatINR(cost)}</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-gray-100">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${(cost / totalFeatureCost) * 100}%`,
                          backgroundColor: FEATURE_COLORS[ft] ?? "#9ca3af",
                        }}
                      />
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>

      {/* Knowledge Graph Growth */}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border bg-white p-5">
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-900">Concept Growth</h3>
            <p className="text-xs text-gray-400">Total concepts extracted over time</p>
          </div>
          {concepts.length > 0 ? (
            <>
              <Sparkline data={concepts} valueKey="concept_count" />
              <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
                <span>{concepts[0]?.date?.slice(5)}</span>
                <span className="font-semibold text-indigo-700">
                  {concepts[concepts.length - 1]?.concept_count ?? 0} total
                </span>
                <span>{concepts[concepts.length - 1]?.date?.slice(5)}</span>
              </div>
            </>
          ) : (
            <div className="flex h-20 items-center justify-center text-xs text-gray-400">
              No concept data — analyze a repository or document first
            </div>
          )}
        </div>

        {/* Activity Breakdown */}
        <div className="rounded-lg border bg-white p-5">
          <h3 className="mb-4 text-sm font-semibold text-gray-900">Activity Summary</h3>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Documents", value: activity?.total_documents ?? 0, icon: FileText, color: "text-blue-600", bg: "bg-blue-50" },
              { label: "Repositories", value: activity?.total_repos ?? 0, icon: GitBranch, color: "text-green-600", bg: "bg-green-50" },
              { label: "Ontology Concepts", value: activity?.total_concepts ?? 0, icon: Network, color: "text-purple-600", bg: "bg-purple-50" },
              { label: "Chat Messages", value: activity?.total_chat_messages ?? 0, icon: MessageSquare, color: "text-indigo-600", bg: "bg-indigo-50" },
              { label: "Validations", value: activity?.total_validations ?? 0, icon: Activity, color: "text-amber-600", bg: "bg-amber-50" },
              { label: "Active Features", value: overview?.active_features ?? 0, icon: TrendingUp, color: "text-pink-600", bg: "bg-pink-50" },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-3 rounded-lg bg-gray-50 p-3">
                <div className={`rounded-md p-2 ${item.bg}`}>
                  <item.icon className={`h-4 w-4 ${item.color}`} />
                </div>
                <div>
                  <p className="text-lg font-bold text-gray-900">{formatNumber(item.value)}</p>
                  <p className="text-[10px] text-gray-500">{item.label}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
