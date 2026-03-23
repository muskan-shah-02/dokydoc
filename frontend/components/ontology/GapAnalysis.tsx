"use client";

import { AlertTriangle, FileText, Code, CheckCircle2, XCircle } from "lucide-react";

/**
 * GapAnalysis — Dashboard showing unmapped concepts, undocumented code,
 * and contradictions between document and code layers.
 */

interface MismatchData {
  gaps: Array<{ id: number; name: string; concept_type: string }>;
  undocumented: Array<{ id: number; name: string; concept_type: string }>;
  contradictions: Array<{
    id: number;
    document_concept_name: string;
    code_concept_name: string;
    relationship_type: string;
  }>;
  total_gaps: number;
  total_undocumented: number;
  total_contradictions: number;
}

interface GapAnalysisProps {
  data: MismatchData | null;
  loading: boolean;
}

function GapCard({
  title,
  count,
  icon: Icon,
  color,
  description,
}: {
  title: string;
  count: number;
  icon: any;
  color: string;
  description: string;
}) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500">{title}</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{count}</p>
          <p className="mt-0.5 text-[10px] text-gray-400">{description}</p>
        </div>
        <div className={`rounded-lg p-2.5 ${color}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

export function GapAnalysis({ data, loading }: GapAnalysisProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-400">
        <AlertTriangle className="mb-2 h-8 w-8" />
        <p className="text-sm">Run mapping pipeline first to see gap analysis</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3">
        <GapCard
          title="Documentation Gaps"
          count={data.total_gaps}
          icon={FileText}
          color="bg-red-50 text-red-600"
          description="Doc concepts with no code match"
        />
        <GapCard
          title="Undocumented Code"
          count={data.total_undocumented}
          icon={Code}
          color="bg-amber-50 text-amber-600"
          description="Code concepts with no doc match"
        />
        <GapCard
          title="Contradictions"
          count={data.total_contradictions}
          icon={AlertTriangle}
          color="bg-purple-50 text-purple-600"
          description="Conflicting doc/code mappings"
        />
      </div>

      {/* Gap details */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Documentation gaps */}
        <div className="rounded-lg border bg-white">
          <div className="flex items-center gap-2 border-b px-4 py-3">
            <XCircle className="h-4 w-4 text-red-500" />
            <h4 className="text-sm font-semibold text-gray-900">
              Documentation Gaps ({data.gaps.length})
            </h4>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {data.gaps.length === 0 ? (
              <div className="flex items-center gap-2 px-4 py-6 text-sm text-gray-400">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                All document concepts have code matches
              </div>
            ) : (
              <div className="divide-y">
                {data.gaps.map((g) => (
                  <div key={g.id} className="flex items-center gap-3 px-4 py-2.5">
                    <FileText className="h-4 w-4 flex-shrink-0 text-blue-500" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-gray-800">{g.name}</p>
                      <p className="text-[10px] text-gray-400">{g.concept_type}</p>
                    </div>
                    <span className="flex-shrink-0 rounded bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-600">
                      No code match
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Undocumented code */}
        <div className="rounded-lg border bg-white">
          <div className="flex items-center gap-2 border-b px-4 py-3">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            <h4 className="text-sm font-semibold text-gray-900">
              Undocumented Code ({data.undocumented.length})
            </h4>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {data.undocumented.length === 0 ? (
              <div className="flex items-center gap-2 px-4 py-6 text-sm text-gray-400">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                All code concepts have document matches
              </div>
            ) : (
              <div className="divide-y">
                {data.undocumented.map((u) => (
                  <div key={u.id} className="flex items-center gap-3 px-4 py-2.5">
                    <Code className="h-4 w-4 flex-shrink-0 text-green-500" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-gray-800">{u.name}</p>
                      <p className="text-[10px] text-gray-400">{u.concept_type}</p>
                    </div>
                    <span className="flex-shrink-0 rounded bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-600">
                      No docs
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Contradictions */}
      {data.contradictions.length > 0 && (
        <div className="rounded-lg border border-purple-200 bg-purple-50">
          <div className="flex items-center gap-2 border-b border-purple-200 px-4 py-3">
            <AlertTriangle className="h-4 w-4 text-purple-600" />
            <h4 className="text-sm font-semibold text-purple-900">
              Contradictions ({data.contradictions.length})
            </h4>
          </div>
          <div className="divide-y divide-purple-200">
            {data.contradictions.map((c) => (
              <div key={c.id} className="flex items-center gap-2 px-4 py-2.5 text-xs">
                <span className="font-medium text-blue-700">{c.document_concept_name}</span>
                <span className="rounded bg-purple-200 px-1.5 py-0.5 text-[10px] font-medium text-purple-800">
                  {c.relationship_type}
                </span>
                <span className="font-medium text-green-700">{c.code_concept_name}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
