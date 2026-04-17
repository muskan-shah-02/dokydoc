"use client";

/**
 * P5C-09: CTO / VP Compliance Dashboard
 * Aggregate compliance view across all tenant projects.
 * Auto-refreshes every 5 minutes.
 */

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
import {
  ShieldCheck,
  AlertTriangle,
  Clock,
  TrendingUp,
  RefreshCw,
  Loader2,
  FileText,
  AlertCircle,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────

interface ProjectRow {
  document_id: number;
  title: string;
  atom_count: number;
  compliance_score: number | null;
  open_mismatches: number;
  critical_mismatches: number;
  last_snapshot_date: string | null;
}

interface ComplianceOverview {
  tenant_id: number;
  total_documents: number;
  total_atoms: number;
  overall_compliance_pct: number;
  total_open_mismatches: number;
  mismatch_breakdown: Record<string, number>;
  regulatory_risk: Record<string, number>;
  qa_time_saved_hours: number;
  auto_testable_atoms: number;
  qa_baseline_hours_per_atom: number;
  projects: ProjectRow[];
  generated_at: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function scoreColor(score: number | null): string {
  if (score === null) return "#9ca3af";
  if (score >= 80) return "#10b981";
  if (score >= 60) return "#f59e0b";
  return "#ef4444";
}

function scoreBadge(score: number | null): string {
  if (score === null) return "bg-gray-100 text-gray-500";
  if (score >= 80) return "bg-green-100 text-green-700";
  if (score >= 60) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

// ── Custom Tooltip ─────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const score = payload[0]?.value as number;
  return (
    <div className="rounded-lg border bg-white px-3 py-2 shadow text-xs">
      <p className="font-medium text-gray-800 mb-1 max-w-[200px] truncate">{label}</p>
      <p style={{ color: scoreColor(score) }} className="font-bold text-base">{score}%</p>
      <p className="text-gray-400">compliance score</p>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function CTOComplianceDashboard() {
  const router = useRouter();
  const [data, setData] = useState<ComplianceOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setIsLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("accessToken");
      const res = await fetch(`${API_BASE_URL}/analytics/compliance-overview`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e: any) {
      setError(e.message ?? "Failed to load compliance data");
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(true), 300_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center gap-2">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
        <span className="text-sm text-gray-500">Loading compliance overview…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
        <AlertCircle className="h-8 w-8 text-red-400" />
        <p className="text-sm text-gray-600">{error}</p>
        <button
          onClick={() => fetchData()}
          className="text-xs text-indigo-600 underline hover:text-indigo-800"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  const topRegulatoryRisks = Object.entries(data.regulatory_risk)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  const chartData = [...data.projects]
    .sort((a, b) => (a.compliance_score ?? 100) - (b.compliance_score ?? 100))
    .slice(0, 20)
    .map((p) => ({
      name: p.title.length > 22 ? p.title.slice(0, 20) + "…" : p.title,
      fullTitle: p.title,
      score: p.compliance_score ?? 100,
      document_id: p.document_id,
    }));

  return (
    <div className="min-h-screen bg-gray-50/50 p-4 lg:p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-indigo-50 p-3">
            <ShieldCheck className="h-6 w-6 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Compliance Dashboard</h1>
            <p className="mt-0.5 text-sm text-gray-500">
              Aggregate compliance across all projects · generated {data.generated_at}
            </p>
          </div>
        </div>
        <button
          onClick={() => fetchData(true)}
          disabled={refreshing}
          className="flex items-center gap-1.5 rounded-lg border bg-white px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* KPI Cards */}
      <div className="mb-6 grid gap-4 grid-cols-2 lg:grid-cols-4">
        {[
          {
            label: "Overall Compliance",
            value: `${data.overall_compliance_pct}%`,
            sub: `${data.total_documents} projects · ${data.total_atoms} atoms`,
            icon: ShieldCheck,
            color: "text-indigo-600",
            bg: "bg-indigo-50",
            valueColor:
              data.overall_compliance_pct >= 80
                ? "text-green-700"
                : data.overall_compliance_pct >= 60
                ? "text-amber-700"
                : "text-red-700",
          },
          {
            label: "Open Mismatches",
            value: data.total_open_mismatches.toLocaleString(),
            sub: Object.entries(data.mismatch_breakdown)
              .map(([k, v]) => `${v} ${k}`)
              .join(" · ") || "No open mismatches",
            icon: AlertTriangle,
            color: "text-red-600",
            bg: "bg-red-50",
            valueColor: data.total_open_mismatches > 0 ? "text-red-700" : "text-green-700",
          },
          {
            label: "QA Time Saved",
            value: `${data.qa_time_saved_hours}h`,
            sub: `${data.auto_testable_atoms} auto-testable atoms`,
            icon: Clock,
            color: "text-green-600",
            bg: "bg-green-50",
            valueColor: "text-green-700",
          },
          {
            label: "Regulatory Tags",
            value: topRegulatoryRisks.length.toLocaleString(),
            sub: topRegulatoryRisks.slice(0, 2).map(([k]) => k).join(", ") || "None detected",
            icon: TrendingUp,
            color: "text-amber-600",
            bg: "bg-amber-50",
            valueColor: "text-amber-700",
          },
        ].map((card) => (
          <div key={card.label} className="rounded-lg border bg-white p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-gray-500">{card.label}</p>
                <p className={`mt-1 text-2xl font-bold ${card.valueColor}`}>{card.value}</p>
                <p className="mt-0.5 text-[10px] text-gray-400 truncate">{card.sub}</p>
              </div>
              <div className={`ml-3 flex-shrink-0 rounded-lg p-2.5 ${card.bg}`}>
                <card.icon className={`h-5 w-5 ${card.color}`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Chart + Regulatory Risk */}
      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        {/* Compliance by Project Bar Chart */}
        <div className="lg:col-span-2 rounded-lg border bg-white p-5">
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-900">Compliance by Project</h3>
            <p className="text-xs text-gray-400">
              Projects sorted lowest→highest · click to open
            </p>
          </div>
          {chartData.length === 0 ? (
            <div className="flex h-48 items-center justify-center text-xs text-gray-400">
              No projects with compliance data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 4, right: 40, left: 8, bottom: 4 }}
                onClick={(e) => {
                  const docId = (e?.activePayload?.[0]?.payload as any)?.document_id;
                  if (docId) router.push(`/dashboard/documents/${docId}`);
                }}
                style={{ cursor: "pointer" }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} tickFormatter={(v) => `${v}%`} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={110} />
                <Tooltip content={<ChartTooltip />} />
                <ReferenceLine x={80} stroke="#f59e0b" strokeDasharray="4 4" />
                <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={scoreColor(entry.score)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Regulatory Risk */}
        <div className="rounded-lg border bg-white p-5">
          <h3 className="mb-3 text-sm font-semibold text-gray-900">Regulatory Tags at Risk</h3>
          {topRegulatoryRisks.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-xs text-gray-400">
              No regulatory tags detected
            </div>
          ) : (
            <div className="space-y-3">
              {topRegulatoryRisks.map(([tag, count]) => (
                <div key={tag}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="font-medium text-gray-700">{tag}</span>
                    <span className="text-gray-500">{count} atoms</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-gray-100">
                    <div
                      className="h-full rounded-full bg-amber-400"
                      style={{
                        width: `${Math.min(100, (count / (topRegulatoryRisks[0][1] || 1)) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Mismatch Severity Breakdown */}
          {Object.keys(data.mismatch_breakdown).length > 0 && (
            <div className="mt-5 border-t pt-4">
              <h4 className="mb-3 text-xs font-semibold text-gray-700">Mismatch Severity</h4>
              {Object.entries(data.mismatch_breakdown)
                .sort(([a], [b]) => {
                  const order = ["critical", "high", "medium", "low"];
                  return order.indexOf(a) - order.indexOf(b);
                })
                .map(([severity, count]) => {
                  const colors: Record<string, string> = {
                    critical: "bg-red-500",
                    high: "bg-red-400",
                    medium: "bg-amber-400",
                    low: "bg-green-400",
                  };
                  return (
                    <div key={severity} className="mb-2 flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <div className={`h-2 w-2 rounded-full ${colors[severity] ?? "bg-gray-400"}`} />
                        <span className="capitalize text-gray-600">{severity}</span>
                      </div>
                      <span className="font-semibold text-gray-800">{count}</span>
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      </div>

      {/* Project Table */}
      <div className="rounded-lg border bg-white">
        <div className="flex items-center justify-between border-b px-5 py-3">
          <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <FileText className="h-4 w-4 text-gray-400" />
            All Projects
          </h3>
          <span className="text-xs text-gray-400">{data.projects.length} total</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 text-xs font-medium text-gray-500">
                <th className="px-5 py-3 text-left">Project</th>
                <th className="px-4 py-3 text-right">Score</th>
                <th className="px-4 py-3 text-right">Atoms</th>
                <th className="px-4 py-3 text-right">Open</th>
                <th className="px-4 py-3 text-right">Critical/High</th>
                <th className="px-4 py-3 text-right">Last Updated</th>
              </tr>
            </thead>
            <tbody>
              {data.projects.map((project) => (
                <tr
                  key={project.document_id}
                  className="border-b last:border-0 hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => router.push(`/dashboard/documents/${project.document_id}`)}
                >
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <FileText className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
                      <span className="font-medium text-gray-900 truncate max-w-[280px]">
                        {project.title}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {project.compliance_score !== null ? (
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${scoreBadge(
                          project.compliance_score
                        )}`}
                      >
                        {project.compliance_score}%
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-gray-600">
                    {project.atom_count.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span
                      className={`text-xs font-medium ${
                        project.open_mismatches > 0 ? "text-red-600" : "text-green-600"
                      }`}
                    >
                      {project.open_mismatches}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span
                      className={`text-xs font-medium ${
                        project.critical_mismatches > 0 ? "text-red-700 font-bold" : "text-gray-400"
                      }`}
                    >
                      {project.critical_mismatches}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-gray-400">
                    {project.last_snapshot_date ?? "Never"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.projects.length === 0 && (
            <div className="flex h-24 items-center justify-center text-xs text-gray-400">
              No projects found. Upload documents and run validation scans to populate this view.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
