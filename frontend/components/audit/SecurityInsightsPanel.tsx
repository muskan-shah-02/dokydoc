"use client";

import { useState, useEffect } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from "recharts";
import { AlertTriangle, ChevronDown, ChevronUp, Download, Loader2, ShieldAlert, Users, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface AnalyticsData {
  daily_counts: { date: string; count: number }[];
  action_breakdown: Record<string, number>;
  top_users: { email: string; event_count: number }[];
  busiest_hour: number;
}

interface AnomalyData {
  repeated_failures: { email: string; count: number; last_attempt: string | null }[];
  off_hours_access: { email: string; datetime: string; hour: number }[];
  bulk_deletes: { email: string; count: number }[];
}

const ACTION_COLORS: Record<string, string> = {
  create: "#22c55e",
  update: "#3b82f6",
  delete: "#ef4444",
  login: "#a855f7",
  analyze: "#f59e0b",
  export: "#06b6d4",
};

const PIE_COLORS = ["#22c55e", "#3b82f6", "#ef4444", "#a855f7", "#f59e0b", "#06b6d4"];

export function SecurityInsightsPanel() {
  const [collapsed, setCollapsed] = useState(false);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloadingReport, setDownloadingReport] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get("/audit/analytics"),
      api.get("/audit/anomalies"),
    ])
      .then(([a, b]) => {
        setAnalytics(a as AnalyticsData);
        setAnomalies(b as AnomalyData);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleDownloadReport = async () => {
    setDownloadingReport(true);
    try {
      const data = await api.get("/audit/compliance-report");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `compliance-report-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Failed to download compliance report.");
    } finally {
      setDownloadingReport(false);
    }
  };

  const pieData = analytics
    ? Object.entries(analytics.action_breakdown).map(([name, value]) => ({ name, value }))
    : [];

  const totalAnomalies =
    (anomalies?.repeated_failures.length || 0) +
    (anomalies?.off_hours_access.length || 0) +
    (anomalies?.bulk_deletes.length || 0);

  return (
    <div className="bg-white border rounded-xl shadow-sm overflow-hidden mb-6">
      {/* Panel header */}
      <div className="flex items-center justify-between px-6 py-4 border-b bg-gray-50">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-blue-600" />
          <h2 className="text-base font-semibold text-gray-900">Security Insights</h2>
          {totalAnomalies > 0 && (
            <span className="ml-1 inline-flex items-center justify-center px-2 py-0.5 text-xs font-bold rounded-full bg-red-100 text-red-700">
              {totalAnomalies} alert{totalAnomalies !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
        >
          {collapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          {collapsed ? "Expand" : "Collapse"}
        </button>
      </div>

      {!collapsed && (
        <div className="p-6 space-y-6">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-blue-500 mr-2" />
              <span className="text-sm text-gray-500">Loading insights…</span>
            </div>
          ) : (
            <>
              {/* Charts Row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Activity Bar Chart */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">Activity (Last 14 Days)</h3>
                  {analytics && analytics.daily_counts.length > 0 ? (
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart data={analytics.daily_counts} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 11 }}
                          tickFormatter={(d) => d.slice(5)} // MM-DD
                        />
                        <YAxis tick={{ fontSize: 11 }} width={30} />
                        <Tooltip
                          contentStyle={{ fontSize: 12 }}
                          formatter={(v: unknown) => [v as number, "Events"]}
                        />
                        <Bar dataKey="count" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="flex items-center justify-center h-44 text-gray-400 text-sm">No data for last 14 days</div>
                  )}
                </div>

                {/* Action Pie Chart */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">Action Mix</h3>
                  {pieData.length > 0 ? (
                    <div className="flex items-center gap-4">
                      <ResponsiveContainer width={160} height={160}>
                        <PieChart>
                          <Pie data={pieData} cx="50%" cy="50%" outerRadius={70} dataKey="value">
                            {pieData.map((_, i) => (
                              <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip contentStyle={{ fontSize: 12 }} />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="space-y-1.5">
                        {pieData.map((d, i) => (
                          <div key={d.name} className="flex items-center gap-2 text-xs">
                            <span
                              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                              style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                            />
                            <span className="capitalize text-gray-700">{d.name}</span>
                            <span className="text-gray-400 ml-auto">{d.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-44 text-gray-400 text-sm">No action data</div>
                  )}
                </div>
              </div>

              {/* Anomaly Alerts */}
              {anomalies && totalAnomalies > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    Anomaly Alerts
                  </h3>
                  <div className="space-y-2">
                    {anomalies.repeated_failures.map((r, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm">
                        <span className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0 mt-1.5" />
                        <div>
                          <span className="font-medium text-red-700">{r.count} repeated failures</span>
                          <span className="text-red-600"> — {r.email}</span>
                          {r.last_attempt && (
                            <span className="text-red-500 text-xs ml-2">
                              (last: {new Date(r.last_attempt).toLocaleString()})
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                    {anomalies.off_hours_access.slice(0, 3).map((r, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm">
                        <span className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0 mt-1.5" />
                        <div>
                          <span className="font-medium text-amber-700">Off-hours access</span>
                          <span className="text-amber-600"> — {r.email}</span>
                          <span className="text-amber-500 text-xs ml-2">
                            ({String(r.hour).padStart(2, "0")}:xx on {r.datetime.slice(0, 10)})
                          </span>
                        </div>
                      </div>
                    ))}
                    {anomalies.bulk_deletes.map((r, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm">
                        <span className="w-2 h-2 rounded-full bg-red-600 flex-shrink-0 mt-1.5" />
                        <div>
                          <span className="font-medium text-red-700">Bulk delete detected</span>
                          <span className="text-red-600"> — {r.email}</span>
                          <span className="text-red-500 text-xs ml-2">({r.count} deletes in last hour)</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Top Active Users */}
              {analytics && analytics.top_users.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-1.5">
                    <Users className="w-4 h-4 text-blue-500" />
                    Top Active Users
                  </h3>
                  <div className="overflow-hidden border rounded-lg">
                    <table className="min-w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">User</th>
                          <th className="px-4 py-2 text-right text-xs font-semibold text-gray-600">Events</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {analytics.top_users.map((u, i) => (
                          <tr key={i} className="hover:bg-gray-50">
                            <td className="px-4 py-2 text-gray-700">{u.email}</td>
                            <td className="px-4 py-2 text-right font-medium text-gray-900">{u.event_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Busiest Hour + Download */}
              <div className="flex items-center justify-between pt-2 border-t">
                {analytics && (
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <Clock className="w-4 h-4" />
                    Busiest hour:{" "}
                    <span className="font-medium text-gray-700">
                      {String(analytics.busiest_hour).padStart(2, "0")}:00 – {String((analytics.busiest_hour + 1) % 24).padStart(2, "0")}:00 UTC
                    </span>
                  </div>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDownloadReport}
                  disabled={downloadingReport}
                  className="gap-1.5 text-xs"
                >
                  {downloadingReport ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Download className="w-3.5 h-3.5" />
                  )}
                  Download Compliance Report JSON
                </Button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
