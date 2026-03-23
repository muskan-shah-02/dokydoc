"use client";

import { useState } from "react";
import { Check, X, ExternalLink, ClipboardList, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";

interface ApprovalRef {
  id: number;
  entity_type: string;
  entity_id: number | null;
  entity_name: string | null;
  status: string;
  level: number | null;
  created_at: string | null;
}

interface InlineApprovalActionsProps {
  approvals: ApprovalRef[];
}

type ApprovalState = "pending" | "approved" | "rejected" | "loading";

export function InlineApprovalActions({ approvals }: InlineApprovalActionsProps) {
  const router = useRouter();
  const [states, setStates] = useState<Record<number, ApprovalState>>({});
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  if (!approvals || approvals.length === 0) return null;

  const pendingApprovals = approvals.filter(
    (a) => a.status === "pending" && (states[a.id] === undefined || states[a.id] === "pending")
  );

  if (pendingApprovals.length === 0) return null;

  const handleApprove = async (id: number) => {
    setStates((prev) => ({ ...prev, [id]: "loading" }));
    try {
      await api.post(`/approvals/${id}/approve`, {});
      setStates((prev) => ({ ...prev, [id]: "approved" }));
    } catch {
      setStates((prev) => ({ ...prev, [id]: "pending" }));
      alert("Failed to approve. Please try from the Approvals page.");
    }
  };

  const handleReject = async (id: number) => {
    if (!rejectReason.trim()) {
      alert("Please enter a rejection reason.");
      return;
    }
    setStates((prev) => ({ ...prev, [id]: "loading" }));
    try {
      await api.post(`/approvals/${id}/reject`, { reason: rejectReason });
      setStates((prev) => ({ ...prev, [id]: "rejected" }));
      setRejectingId(null);
      setRejectReason("");
    } catch {
      setStates((prev) => ({ ...prev, [id]: "pending" }));
      alert("Failed to reject. Please try from the Approvals page.");
    }
  };

  return (
    <div className="mt-3 border border-amber-200 rounded-lg bg-amber-50 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-amber-200 bg-amber-100">
        <ClipboardList className="w-4 h-4 text-amber-700 flex-shrink-0" />
        <span className="text-sm font-semibold text-amber-800">
          Pending Approvals ({pendingApprovals.length})
        </span>
      </div>

      {/* Approval items */}
      <div className="divide-y divide-amber-100">
        {pendingApprovals.map((approval) => {
          const state = states[approval.id] || "pending";
          const levelLabel = approval.level ? `L${approval.level}` : "";

          return (
            <div key={approval.id} className="px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {approval.entity_name || `${approval.entity_type} #${approval.entity_id}`}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {approval.entity_type}
                    {levelLabel && (
                      <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                        {levelLabel}
                      </span>
                    )}
                  </p>
                </div>

                <div className="flex items-center gap-1.5 flex-shrink-0">
                  {state === "loading" && (
                    <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                  )}
                  {state === "approved" && (
                    <span className="inline-flex items-center gap-1 text-xs text-green-700 font-medium">
                      <Check className="w-3.5 h-3.5" /> Approved
                    </span>
                  )}
                  {state === "rejected" && (
                    <span className="inline-flex items-center gap-1 text-xs text-red-600 font-medium">
                      <X className="w-3.5 h-3.5" /> Rejected
                    </span>
                  )}
                  {state === "pending" && (
                    <>
                      <Button
                        size="sm"
                        className="h-7 px-2.5 text-xs bg-green-600 hover:bg-green-700"
                        onClick={() => handleApprove(approval.id)}
                      >
                        <Check className="w-3 h-3 mr-1" /> Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 px-2.5 text-xs border-red-200 text-red-600 hover:bg-red-50"
                        onClick={() => setRejectingId(approval.id)}
                      >
                        <X className="w-3 h-3 mr-1" /> Reject
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs text-gray-500"
                        onClick={() => router.push("/dashboard/approvals")}
                        title="View details"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </Button>
                    </>
                  )}
                </div>
              </div>

              {/* Rejection reason input */}
              {rejectingId === approval.id && (
                <div className="mt-2 flex gap-2">
                  <input
                    type="text"
                    className="flex-1 text-xs border border-red-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-red-400 bg-white"
                    placeholder="Reason for rejection…"
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleReject(approval.id);
                      if (e.key === "Escape") { setRejectingId(null); setRejectReason(""); }
                    }}
                    autoFocus
                  />
                  <Button
                    size="sm"
                    className="h-7 text-xs bg-red-600 hover:bg-red-700"
                    onClick={() => handleReject(approval.id)}
                  >
                    Confirm
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 text-xs"
                    onClick={() => { setRejectingId(null); setRejectReason(""); }}
                  >
                    Cancel
                  </Button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
