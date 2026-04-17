"use client";

/**
 * P5C-04: UATChecklist
 * Shows manual-testability atoms as a UAT checklist.
 * QA/BA can mark each as pass, fail, or blocked with notes.
 */

import { useState } from "react";
import { CheckCircle2, XCircle, MinusCircle, Clock } from "lucide-react";
import { useUATChecklist, UATChecklistItem } from "@/hooks/useUATChecklist";
import { API_BASE_URL } from "@/lib/api";

const RESULT_CONFIG = {
  pass: { Icon: CheckCircle2, color: "text-green-600", bg: "bg-green-50 dark:bg-green-950/30", label: "Pass" },
  fail: { Icon: XCircle, color: "text-red-600", bg: "bg-red-50 dark:bg-red-950/30", label: "Fail" },
  blocked: { Icon: MinusCircle, color: "text-amber-600", bg: "bg-amber-50 dark:bg-amber-950/30", label: "Blocked" },
} as const;

interface Props {
  documentId: number;
}

export function UATChecklist({ documentId }: Props) {
  const { checklist, isLoading, mutate } = useUATChecklist(documentId);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState<number | null>(null);

  const handleCheck = async (item: UATChecklistItem, result: "pass" | "fail" | "blocked") => {
    setSaving(item.id);
    try {
      const res = await fetch(
        `${API_BASE_URL}/validation/${documentId}/uat-checklist/${item.id}/check`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ result, notes: notes[item.id] || null }),
        }
      );
      if (res.ok) {
        await mutate();
        setExpanded(null);
      }
    } finally {
      setSaving(null);
    }
  };

  if (isLoading && checklist.items.length === 0) {
    return <div className="text-sm text-muted-foreground p-4">Loading UAT checklist…</div>;
  }

  const { summary, items } = checklist;

  if (items.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        No manual UAT items found. All requirements may be auto-testable.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-2">
        {[
          { label: "Total", value: summary.total, color: "text-foreground" },
          { label: "Pending", value: summary.pending, color: "text-amber-600" },
          { label: "Passed", value: summary.passed, color: "text-green-600" },
          { label: "Failed", value: summary.failed, color: "text-red-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="text-center rounded-lg border p-3">
            <div className={`text-2xl font-bold ${color}`}>{value}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
          </div>
        ))}
      </div>

      {/* Progress bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>UAT Progress</span>
          <span>{summary.completion_pct}% complete</span>
        </div>
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-green-500 rounded-full transition-all duration-300"
            style={{ width: `${summary.completion_pct}%` }}
          />
        </div>
      </div>

      {/* Checklist items */}
      <div className="space-y-2">
        {items.map(item => {
          const cfg = item.result ? RESULT_CONFIG[item.result] : null;
          return (
            <div
              key={item.id}
              className={`border rounded-lg p-3 cursor-pointer hover:bg-muted/30 transition-colors ${cfg?.bg ?? ""}`}
              onClick={() => setExpanded(expanded === item.id ? null : item.id)}
            >
              <div className="flex items-start gap-2">
                {cfg ? (
                  <cfg.Icon className={`h-4 w-4 mt-0.5 shrink-0 ${cfg.color}`} />
                ) : (
                  <Clock className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap mb-1">
                    <span className="text-xs font-mono text-muted-foreground">{item.atom_id}</span>
                    <span className="text-xs px-1.5 py-0.5 bg-muted rounded">{item.atom_type}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      item.criticality === "critical" ? "bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300" :
                      item.criticality === "high" ? "bg-orange-100 dark:bg-orange-900 text-orange-700 dark:text-orange-300" :
                      "bg-muted text-muted-foreground"
                    }`}>
                      {item.criticality}
                    </span>
                  </div>
                  <p className="text-sm line-clamp-2">{item.content}</p>
                </div>
              </div>

              {expanded === item.id && (
                <div className="mt-3 pt-3 border-t space-y-2" onClick={e => e.stopPropagation()}>
                  <textarea
                    placeholder="Testing notes (optional)…"
                    value={notes[item.id] ?? item.notes ?? ""}
                    onChange={e => setNotes(prev => ({ ...prev, [item.id]: e.target.value }))}
                    className="w-full text-xs border border-input rounded p-2 h-16 resize-none bg-background"
                  />
                  <div className="flex gap-2">
                    {(["pass", "fail", "blocked"] as const).map(r => {
                      const c = RESULT_CONFIG[r];
                      return (
                        <button
                          key={r}
                          disabled={saving === item.id}
                          onClick={() => handleCheck(item, r)}
                          className={`flex-1 flex items-center justify-center gap-1 py-1.5 text-white text-xs rounded transition-opacity ${
                            r === "pass" ? "bg-green-600 hover:bg-green-700" :
                            r === "fail" ? "bg-red-600 hover:bg-red-700" :
                            "bg-amber-500 hover:bg-amber-600"
                          } disabled:opacity-50`}
                        >
                          <c.Icon className="h-3.5 w-3.5" />
                          {c.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
