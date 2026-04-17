"use client";

/**
 * P5C-08: ComplianceTrendChart
 * Line chart showing compliance score over time (7/14/30/90 days).
 * Uses recharts. Auto-refreshes every 5 minutes.
 */

import { useState, useEffect, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

const DIRECTION_CONFIG = {
  improving: { Icon: TrendingUp, color: "text-green-600", bg: "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-700" },
  degrading: { Icon: TrendingDown, color: "text-red-600", bg: "bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-700" },
  stable: { Icon: Minus, color: "text-muted-foreground", bg: "bg-muted border-border" },
  neutral: { Icon: Minus, color: "text-muted-foreground", bg: "bg-muted border-border" },
} as const;

type Direction = keyof typeof DIRECTION_CONFIG;

interface SnapshotPoint {
  date: string;
  score: number;
  total_atoms: number;
  covered_atoms: number;
  open_mismatches: number;
  critical_mismatches: number;
}

interface TrendData {
  document_id: number;
  days: number;
  trend: SnapshotPoint[];
  direction: Direction;
  change_pct: number;
  current_score: number | null;
  baseline_score: number | null;
}

interface Props {
  documentId: number;
}

export function ComplianceTrendChart({ documentId }: Props) {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<TrendData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchTrend = useCallback(async () => {
    if (!documentId) return;
    setIsLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/validation/${documentId}/compliance-trend?days=${days}`,
        { credentials: "include" }
      );
      if (res.ok) setData(await res.json());
    } finally {
      setIsLoading(false);
    }
  }, [documentId, days]);

  useEffect(() => {
    fetchTrend();
    const interval = setInterval(fetchTrend, 300_000); // every 5 min
    return () => clearInterval(interval);
  }, [fetchTrend]);

  if (isLoading && !data) {
    return <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">Loading trend…</div>;
  }

  if (!data?.trend?.length) {
    return (
      <div className="h-20 flex items-center justify-center text-sm text-muted-foreground">
        No trend data yet. Run a validation scan to start tracking.
      </div>
    );
  }

  const direction: Direction = (data.direction as Direction) || "neutral";
  const cfg = DIRECTION_CONFIG[direction] || DIRECTION_CONFIG.neutral;
  const { Icon } = cfg;

  const chartData = data.trend.map(s => ({
    ...s,
    date: (() => {
      const d = new Date(s.date);
      return `${d.getMonth() + 1}/${d.getDate()}`;
    })(),
  }));

  const latest = data.trend[data.trend.length - 1];

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold">{data.current_score}%</span>
          <div className={`flex items-center gap-1.5 px-2 py-1 rounded-full border text-xs font-medium ${cfg.bg} ${cfg.color}`}>
            <Icon className="h-3.5 w-3.5" />
            {direction === "improving" && `+${Math.abs(data.change_pct)}% in ${days}d`}
            {direction === "degrading" && `-${Math.abs(data.change_pct)}% in ${days}d`}
            {direction === "stable" && `Stable (${data.change_pct > 0 ? "+" : ""}${data.change_pct}%)`}
            {direction === "neutral" && "No trend data"}
          </div>
        </div>
        <div className="flex gap-1">
          {[7, 14, 30, 90].map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-2 py-0.5 text-xs rounded ${
                days === d
                  ? "bg-blue-600 text-white"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Line chart */}
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} tickFormatter={v => `${v}%`} />
          <Tooltip
            formatter={(value: number) => [`${value}%`, "Compliance"]}
            labelStyle={{ fontSize: 11 }}
            contentStyle={{ fontSize: 11 }}
          />
          <ReferenceLine
            y={80}
            stroke="#f59e0b"
            strokeDasharray="3 3"
            label={{ value: "80%", fontSize: 10, fill: "#f59e0b" }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 3, fill: "#3b82f6" }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Supporting metrics */}
      {latest && (
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div className="rounded border p-2">
            <div className="font-semibold">{latest.open_mismatches}</div>
            <div className="text-muted-foreground">Open mismatches</div>
          </div>
          <div className="rounded border p-2">
            <div className="font-semibold text-red-600">{latest.critical_mismatches}</div>
            <div className="text-muted-foreground">Critical/High</div>
          </div>
          <div className="rounded border p-2">
            <div className="font-semibold">{latest.total_atoms}</div>
            <div className="text-muted-foreground">Total atoms</div>
          </div>
        </div>
      )}
    </div>
  );
}
