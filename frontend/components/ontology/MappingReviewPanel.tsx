"use client";

import { useState } from "react";
import { Check, X, ChevronDown, ChevronUp, ArrowRight, Loader2 } from "lucide-react";

/**
 * MappingReviewPanel — Side panel for reviewing and approving/rejecting concept mappings.
 */

interface MappingItem {
  id: number;
  document_concept_id: number;
  code_concept_id: number;
  document_concept_name: string;
  document_concept_type: string;
  code_concept_name: string;
  code_concept_type: string;
  mapping_method: string;
  confidence_score: number;
  status: string;
  relationship_type: string;
  ai_reasoning: string | null;
}

interface MappingReviewPanelProps {
  mappings: MappingItem[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  onConfirm: (id: number) => Promise<void>;
  onReject: (id: number) => Promise<void>;
  statusFilter: string;
  onStatusFilterChange: (status: string) => void;
}

const METHOD_BADGES: Record<string, { bg: string; text: string; label: string }> = {
  exact: { bg: "bg-green-100", text: "text-green-700", label: "Exact" },
  fuzzy: { bg: "bg-amber-100", text: "text-amber-700", label: "Fuzzy" },
  ai_validated: { bg: "bg-purple-100", text: "text-purple-700", label: "AI" },
};

const STATUS_BADGES: Record<string, { bg: string; text: string }> = {
  confirmed: { bg: "bg-green-100", text: "text-green-700" },
  candidate: { bg: "bg-amber-100", text: "text-amber-700" },
  rejected: { bg: "bg-red-100", text: "text-red-700" },
};

const RELATIONSHIP_LABELS: Record<string, string> = {
  implements: "Implements",
  partially_implements: "Partially implements",
  enforces: "Enforces",
  contradicts: "Contradicts",
  extends: "Extends",
};

export function MappingReviewPanel({
  mappings,
  selectedId,
  onSelect,
  onConfirm,
  onReject,
  statusFilter,
  onStatusFilterChange,
}: MappingReviewPanelProps) {
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const handleConfirm = async (id: number) => {
    setActionLoading(id);
    try {
      await onConfirm(id);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (id: number) => {
    setActionLoading(id);
    try {
      await onReject(id);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-900">Mapping Review</h3>
        <p className="mt-0.5 text-xs text-gray-500">{mappings.length} mappings</p>
      </div>

      {/* Status filter tabs */}
      <div className="flex border-b px-2">
        {["all", "candidate", "confirmed", "rejected"].map((s) => (
          <button
            key={s}
            onClick={() => onStatusFilterChange(s)}
            className={`flex-1 px-2 py-2 text-xs font-medium capitalize transition-colors ${
              statusFilter === s
                ? "border-b-2 border-blue-600 text-blue-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Mapping list */}
      <div className="flex-1 overflow-y-auto">
        {mappings.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <p className="text-sm">No mappings found</p>
          </div>
        ) : (
          <div className="divide-y">
            {mappings.map((m) => {
              const isSelected = m.id === selectedId;
              const isExpanded = m.id === expandedId;
              const methodBadge = METHOD_BADGES[m.mapping_method] || METHOD_BADGES.exact;
              const statusBadge = STATUS_BADGES[m.status] || STATUS_BADGES.candidate;

              return (
                <div
                  key={m.id}
                  className={`cursor-pointer px-4 py-3 transition-colors ${
                    isSelected ? "bg-blue-50" : "hover:bg-gray-50"
                  }`}
                  onClick={() => onSelect(m.id === selectedId ? null : m.id)}
                >
                  {/* Mapping summary */}
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1 text-xs">
                        <span className="truncate font-medium text-blue-700">
                          {m.document_concept_name}
                        </span>
                        <ArrowRight className="h-3 w-3 flex-shrink-0 text-gray-400" />
                        <span className="truncate font-medium text-green-700">
                          {m.code_concept_name}
                        </span>
                      </div>
                      <div className="mt-1.5 flex items-center gap-1.5">
                        <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${methodBadge.bg} ${methodBadge.text}`}>
                          {methodBadge.label}
                        </span>
                        <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${statusBadge.bg} ${statusBadge.text}`}>
                          {m.status}
                        </span>
                        <span className="text-[10px] text-gray-400">
                          {Math.round(m.confidence_score * 100)}%
                        </span>
                      </div>
                    </div>

                    {/* Expand toggle */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedId(isExpanded ? null : m.id);
                      }}
                      className="rounded p-1 hover:bg-gray-200"
                    >
                      {isExpanded ? (
                        <ChevronUp className="h-3 w-3 text-gray-400" />
                      ) : (
                        <ChevronDown className="h-3 w-3 text-gray-400" />
                      )}
                    </button>
                  </div>

                  {/* Expanded details */}
                  {isExpanded && (
                    <div className="mt-3 rounded-md border bg-gray-50 p-3">
                      <div className="space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Relationship:</span>
                          <span className="font-medium">{RELATIONSHIP_LABELS[m.relationship_type] || m.relationship_type}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Method:</span>
                          <span className="font-medium">{m.mapping_method}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Confidence:</span>
                          <div className="flex items-center gap-1.5">
                            <div className="h-1.5 w-16 rounded-full bg-gray-200">
                              <div
                                className={`h-full rounded-full ${
                                  m.confidence_score >= 0.8 ? "bg-green-500" : m.confidence_score >= 0.5 ? "bg-amber-500" : "bg-red-500"
                                }`}
                                style={{ width: `${m.confidence_score * 100}%` }}
                              />
                            </div>
                            <span className="font-medium">{Math.round(m.confidence_score * 100)}%</span>
                          </div>
                        </div>
                        {m.ai_reasoning && (
                          <div>
                            <span className="text-gray-500">AI Reasoning:</span>
                            <p className="mt-1 text-xs italic text-gray-600">{m.ai_reasoning}</p>
                          </div>
                        )}
                      </div>

                      {/* Action buttons for candidates */}
                      {m.status === "candidate" && (
                        <div className="mt-3 flex gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleConfirm(m.id);
                            }}
                            disabled={actionLoading === m.id}
                            className="flex flex-1 items-center justify-center gap-1 rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
                          >
                            {actionLoading === m.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                            Confirm
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleReject(m.id);
                            }}
                            disabled={actionLoading === m.id}
                            className="flex flex-1 items-center justify-center gap-1 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                          >
                            {actionLoading === m.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <X className="h-3 w-3" />}
                            Reject
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
