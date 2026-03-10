"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  CheckSquare,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Search,
  Filter,
  RefreshCw,
  Loader2,
  FileText,
  Code,
  GitBranch,
  Send,
  Eye,
  MessageSquare,
} from "lucide-react";

interface Approval {
  id: number;
  tenant_id: number;
  entity_type: string;
  entity_id: number;
  entity_name: string | null;
  status: string;
  requested_by_id: number;
  requested_by_email: string | null;
  resolved_by_id: number | null;
  resolved_by_email: string | null;
  approval_level: number;
  request_notes: string | null;
  resolution_notes: string | null;
  created_at: string | null;
  updated_at: string | null;
  resolved_at: string | null;
}

interface ApprovalStats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  revision_requested: number;
  by_entity_type: Record<string, number>;
}

const STATUS_CONFIG: Record<string, { color: string; bg: string; icon: React.ElementType; label: string }> = {
  pending: { color: "text-yellow-700", bg: "bg-yellow-100", icon: Clock, label: "Pending" },
  approved: { color: "text-green-700", bg: "bg-green-100", icon: CheckCircle, label: "Approved" },
  rejected: { color: "text-red-700", bg: "bg-red-100", icon: XCircle, label: "Rejected" },
  revision_requested: { color: "text-orange-700", bg: "bg-orange-100", icon: AlertCircle, label: "Revision Requested" },
};

const ENTITY_ICONS: Record<string, React.ElementType> = {
  document: FileText,
  repository: GitBranch,
  mismatch_resolution: AlertCircle,
  requirement_trace: Code,
  validation_report: CheckSquare,
};

const LEVEL_LABELS: Record<number, string> = {
  1: "Peer Review",
  2: "Managerial",
  3: "Executive",
};

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [stats, setStats] = useState<ApprovalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"pending" | "all" | "history">("pending");
  const [searchTerm, setSearchTerm] = useState("");
  const [entityTypeFilter, setEntityTypeFilter] = useState("");
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  const getHeaders = () => {
    const token = localStorage.getItem("accessToken");
    return {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
  };

  const fetchApprovals = useCallback(async () => {
    setLoading(true);
    try {
      const headers = getHeaders();
      let url = "http://localhost:8000/api/v1/approvals/";

      if (activeTab === "pending") {
        url = "http://localhost:8000/api/v1/approvals/pending";
      } else if (activeTab === "history") {
        url = "http://localhost:8000/api/v1/approvals/history";
      }

      const params = new URLSearchParams();
      if (entityTypeFilter) params.append("entity_type", entityTypeFilter);
      if (searchTerm) params.append("search", searchTerm);
      if (params.toString()) url += `?${params.toString()}`;

      const res = await fetch(url, { headers });
      if (res.ok) {
        const data = await res.json();
        setApprovals(data.items || []);
      }
    } catch (e) {
      console.error("Failed to fetch approvals:", e);
    } finally {
      setLoading(false);
    }
  }, [activeTab, entityTypeFilter, searchTerm]);

  const fetchStats = useCallback(async () => {
    try {
      const headers = getHeaders();
      const res = await fetch("http://localhost:8000/api/v1/approvals/stats", { headers });
      if (res.ok) {
        setStats(await res.json());
      }
    } catch (e) {
      console.error("Failed to fetch stats:", e);
    }
  }, []);

  useEffect(() => {
    fetchApprovals();
    fetchStats();
  }, [fetchApprovals, fetchStats]);

  const handleAction = async (approvalId: number, action: "approve" | "reject" | "request-revision") => {
    setActionLoading(approvalId);
    try {
      const headers = getHeaders();
      const res = await fetch(`http://localhost:8000/api/v1/approvals/${approvalId}/${action}`, {
        method: "POST",
        headers,
        body: JSON.stringify({ resolution_notes: resolutionNotes || null }),
      });
      if (res.ok) {
        setResolutionNotes("");
        setShowDetailModal(false);
        setSelectedApproval(null);
        fetchApprovals();
        fetchStats();
      }
    } catch (e) {
      console.error(`Failed to ${action}:`, e);
    } finally {
      setActionLoading(null);
    }
  };

  const handleCreateApproval = async (entityType: string, entityId: number, entityName: string, level: number, notes: string) => {
    try {
      const headers = getHeaders();
      const res = await fetch("http://localhost:8000/api/v1/approvals/", {
        method: "POST",
        headers,
        body: JSON.stringify({
          entity_type: entityType,
          entity_id: entityId,
          entity_name: entityName,
          approval_level: level,
          request_notes: notes,
        }),
      });
      if (res.ok) {
        fetchApprovals();
        fetchStats();
      }
    } catch (e) {
      console.error("Failed to create approval:", e);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <CheckSquare className="h-8 w-8 text-blue-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Approvals</h1>
            <p className="text-sm text-gray-500">Manage approval requests and review pending items</p>
          </div>
        </div>
        <button
          onClick={() => { fetchApprovals(); fetchStats(); }}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <p className="text-sm text-gray-500">Total</p>
            <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
          </div>
          <div className="bg-yellow-50 rounded-lg border border-yellow-200 p-4">
            <p className="text-sm text-yellow-700">Pending</p>
            <p className="text-2xl font-bold text-yellow-800">{stats.pending}</p>
          </div>
          <div className="bg-green-50 rounded-lg border border-green-200 p-4">
            <p className="text-sm text-green-700">Approved</p>
            <p className="text-2xl font-bold text-green-800">{stats.approved}</p>
          </div>
          <div className="bg-red-50 rounded-lg border border-red-200 p-4">
            <p className="text-sm text-red-700">Rejected</p>
            <p className="text-2xl font-bold text-red-800">{stats.rejected}</p>
          </div>
          <div className="bg-orange-50 rounded-lg border border-orange-200 p-4">
            <p className="text-sm text-orange-700">Revision</p>
            <p className="text-2xl font-bold text-orange-800">{stats.revision_requested}</p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-lg w-fit">
        {[
          { key: "pending" as const, label: "Pending", count: stats?.pending },
          { key: "all" as const, label: "All Approvals", count: stats?.total },
          { key: "history" as const, label: "History", count: undefined },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              activeTab === tab.key
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-700">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by entity name, notes, or email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select
          value={entityTypeFilter}
          onChange={(e) => setEntityTypeFilter(e.target.value)}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Types</option>
          <option value="document">Document</option>
          <option value="repository">Repository</option>
          <option value="mismatch_resolution">Mismatch Resolution</option>
          <option value="requirement_trace">Requirement Trace</option>
          <option value="validation_report">Validation Report</option>
        </select>
      </div>

      {/* Approval List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <span className="ml-3 text-gray-500">Loading approvals...</span>
        </div>
      ) : approvals.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 bg-white rounded-lg border border-gray-200">
          <CheckSquare className="h-12 w-12 text-gray-300 mb-3" />
          <p className="text-gray-500 text-lg font-medium">No approvals found</p>
          <p className="text-gray-400 text-sm mt-1">
            {activeTab === "pending" ? "You're all caught up!" : "No approvals match your filters."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {approvals.map((approval) => {
            const statusConf = STATUS_CONFIG[approval.status] || STATUS_CONFIG.pending;
            const StatusIcon = statusConf.icon;
            const EntityIcon = ENTITY_ICONS[approval.entity_type] || FileText;

            return (
              <div
                key={approval.id}
                className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-gray-100 rounded-lg">
                      <EntityIcon className="h-5 w-5 text-gray-600" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium text-gray-900">
                          {approval.entity_name || `${approval.entity_type} #${approval.entity_id}`}
                        </h3>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full ${statusConf.bg} ${statusConf.color}`}>
                          <StatusIcon className="h-3 w-3" />
                          {statusConf.label}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">
                          Level {approval.approval_level}: {LEVEL_LABELS[approval.approval_level] || "Unknown"}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 mt-1">
                        Requested by <span className="font-medium">{approval.requested_by_email || "Unknown"}</span>
                        {approval.created_at && (
                          <> on {new Date(approval.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" })}</>
                        )}
                      </p>
                      {approval.request_notes && (
                        <p className="text-sm text-gray-600 mt-1 italic">"{approval.request_notes}"</p>
                      )}
                      {approval.resolved_by_email && (
                        <p className="text-xs text-gray-400 mt-1">
                          Resolved by {approval.resolved_by_email}
                          {approval.resolved_at && (
                            <> on {new Date(approval.resolved_at).toLocaleDateString()}</>
                          )}
                        </p>
                      )}
                      {approval.resolution_notes && (
                        <p className="text-xs text-gray-500 mt-1">
                          Notes: {approval.resolution_notes}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Action buttons for pending items */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        setSelectedApproval(approval);
                        setShowDetailModal(true);
                        setResolutionNotes("");
                      }}
                      className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                      title="View Details"
                    >
                      <Eye className="h-4 w-4" />
                    </button>

                    {approval.status === "pending" && (
                      <>
                        <button
                          onClick={() => handleAction(approval.id, "approve")}
                          disabled={actionLoading === approval.id}
                          className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 transition-colors disabled:opacity-50"
                        >
                          {actionLoading === approval.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <CheckCircle className="h-3.5 w-3.5" />
                          )}
                          Approve
                        </button>
                        <button
                          onClick={() => handleAction(approval.id, "reject")}
                          disabled={actionLoading === approval.id}
                          className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition-colors disabled:opacity-50"
                        >
                          <XCircle className="h-3.5 w-3.5" />
                          Reject
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Detail Modal */}
      {showDetailModal && selectedApproval && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-900">Approval Details</h2>
              <button
                onClick={() => { setShowDetailModal(false); setSelectedApproval(null); }}
                className="p-1 hover:bg-gray-100 rounded-lg"
              >
                <XCircle className="h-5 w-5 text-gray-400" />
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-gray-500">Entity Type</p>
                  <p className="font-medium capitalize">{selectedApproval.entity_type.replace("_", " ")}</p>
                </div>
                <div>
                  <p className="text-gray-500">Entity</p>
                  <p className="font-medium">{selectedApproval.entity_name || `#${selectedApproval.entity_id}`}</p>
                </div>
                <div>
                  <p className="text-gray-500">Status</p>
                  <p className="font-medium capitalize">{selectedApproval.status.replace("_", " ")}</p>
                </div>
                <div>
                  <p className="text-gray-500">Approval Level</p>
                  <p className="font-medium">Level {selectedApproval.approval_level} ({LEVEL_LABELS[selectedApproval.approval_level]})</p>
                </div>
                <div>
                  <p className="text-gray-500">Requested By</p>
                  <p className="font-medium">{selectedApproval.requested_by_email || "Unknown"}</p>
                </div>
                <div>
                  <p className="text-gray-500">Requested On</p>
                  <p className="font-medium">
                    {selectedApproval.created_at ? new Date(selectedApproval.created_at).toLocaleString() : "—"}
                  </p>
                </div>
              </div>

              {selectedApproval.request_notes && (
                <div>
                  <p className="text-gray-500">Request Notes</p>
                  <p className="font-medium bg-gray-50 p-2 rounded-lg mt-1">{selectedApproval.request_notes}</p>
                </div>
              )}

              {selectedApproval.resolved_by_email && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-gray-500">Resolved By</p>
                    <p className="font-medium">{selectedApproval.resolved_by_email}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Resolved On</p>
                    <p className="font-medium">
                      {selectedApproval.resolved_at ? new Date(selectedApproval.resolved_at).toLocaleString() : "—"}
                    </p>
                  </div>
                </div>
              )}

              {selectedApproval.resolution_notes && (
                <div>
                  <p className="text-gray-500">Resolution Notes</p>
                  <p className="font-medium bg-gray-50 p-2 rounded-lg mt-1">{selectedApproval.resolution_notes}</p>
                </div>
              )}

              {/* Actions for pending */}
              {selectedApproval.status === "pending" && (
                <div className="border-t border-gray-200 pt-4 mt-4">
                  <label className="block text-gray-500 mb-1">Resolution Notes (optional)</label>
                  <textarea
                    value={resolutionNotes}
                    onChange={(e) => setResolutionNotes(e.target.value)}
                    placeholder="Add notes for your decision..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                    rows={3}
                  />
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => handleAction(selectedApproval.id, "approve")}
                      disabled={actionLoading === selectedApproval.id}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
                    >
                      {actionLoading === selectedApproval.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <CheckCircle className="h-4 w-4" />
                      )}
                      Approve
                    </button>
                    <button
                      onClick={() => handleAction(selectedApproval.id, "request-revision")}
                      disabled={actionLoading === selectedApproval.id}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-orange-700 bg-orange-50 border border-orange-200 rounded-lg hover:bg-orange-100 transition-colors disabled:opacity-50"
                    >
                      <MessageSquare className="h-4 w-4" />
                      Request Revision
                    </button>
                    <button
                      onClick={() => handleAction(selectedApproval.id, "reject")}
                      disabled={actionLoading === selectedApproval.id}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
                    >
                      <XCircle className="h-4 w-4" />
                      Reject
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
