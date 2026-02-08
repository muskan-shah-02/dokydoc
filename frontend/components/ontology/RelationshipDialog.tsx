"use client";

import { useState } from "react";
import { Loader2, ArrowRight } from "lucide-react";

interface Concept {
  id: number;
  name: string;
  concept_type: string;
}

interface RelationshipDialogProps {
  open: boolean;
  onClose: () => void;
  concepts: Concept[];
  onCreate: (data: {
    source_concept_id: number;
    target_concept_id: number;
    relationship_type: string;
    description: string;
    confidence_score: number;
  }) => Promise<void>;
  preselectedSourceId?: number | null;
}

const RELATIONSHIP_TYPES = [
  "HAS",
  "DEPENDS_ON",
  "CONTAINS",
  "IMPLEMENTS",
  "USES",
  "PRODUCES",
  "CONSUMES",
  "VALIDATES",
  "EXTENDS",
  "is_synonym_of",
  "TRIGGERS",
  "MANAGES",
  "BELONGS_TO",
];

export function RelationshipDialog({
  open,
  onClose,
  concepts,
  onCreate,
  preselectedSourceId,
}: RelationshipDialogProps) {
  const [sourceId, setSourceId] = useState<number>(preselectedSourceId || 0);
  const [targetId, setTargetId] = useState<number>(0);
  const [relType, setRelType] = useState("HAS");
  const [description, setDescription] = useState("");
  const [confidence, setConfidence] = useState(0.85);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  // Reset when preselected changes
  if (preselectedSourceId && sourceId !== preselectedSourceId && open) {
    setSourceId(preselectedSourceId);
  }

  if (!open) return null;

  const sourceConcept = concepts.find((c) => c.id === sourceId);
  const targetConcept = concepts.find((c) => c.id === targetId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceId || !targetId) {
      setError("Select both source and target concepts");
      return;
    }
    if (sourceId === targetId) {
      setError("Source and target must be different concepts");
      return;
    }
    setError("");
    setCreating(true);
    try {
      await onCreate({
        source_concept_id: sourceId,
        target_concept_id: targetId,
        relationship_type: relType,
        description: description.trim(),
        confidence_score: confidence,
      });
      setTargetId(0);
      setDescription("");
      setConfidence(0.85);
      onClose();
    } catch (err: any) {
      setError(err.detail || err.message || "Failed to create relationship");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      <div className="relative w-full max-w-lg rounded-lg bg-white shadow-xl">
        <form onSubmit={handleSubmit}>
          <div className="border-b p-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Create Relationship
            </h2>
            <p className="mt-0.5 text-sm text-gray-500">
              Connect two concepts with a meaningful relationship
            </p>
          </div>

          <div className="space-y-4 p-4">
            {error && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
                {error}
              </div>
            )}

            {/* Visual preview */}
            <div className="flex items-center justify-center gap-3 rounded-lg bg-gray-50 px-4 py-3">
              <div
                className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                  sourceConcept
                    ? "bg-blue-100 text-blue-800"
                    : "bg-gray-200 text-gray-400"
                }`}
              >
                {sourceConcept?.name || "Source"}
              </div>
              <div className="flex items-center gap-1">
                <div className="h-px w-6 bg-gray-400" />
                <span className="text-xs font-semibold text-gray-600">
                  {relType}
                </span>
                <ArrowRight className="h-3.5 w-3.5 text-gray-400" />
              </div>
              <div
                className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                  targetConcept
                    ? "bg-green-100 text-green-800"
                    : "bg-gray-200 text-gray-400"
                }`}
              >
                {targetConcept?.name || "Target"}
              </div>
            </div>

            {/* Source concept */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                From (Source) *
              </label>
              <select
                value={sourceId}
                onChange={(e) => setSourceId(Number(e.target.value))}
                className="w-full rounded-md border bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value={0}>Select source concept...</option>
                {concepts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.concept_type})
                  </option>
                ))}
              </select>
            </div>

            {/* Relationship type */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Relationship Type
              </label>
              <div className="flex flex-wrap gap-1.5">
                {RELATIONSHIP_TYPES.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setRelType(t)}
                    className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                      relType === t
                        ? "bg-blue-600 text-white"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* Target concept */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                To (Target) *
              </label>
              <select
                value={targetId}
                onChange={(e) => setTargetId(Number(e.target.value))}
                className="w-full rounded-md border bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value={0}>Select target concept...</option>
                {concepts
                  .filter((c) => c.id !== sourceId)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.concept_type})
                    </option>
                  ))}
              </select>
            </div>

            {/* Description */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Description
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g., Customer HAS many Orders"
                className="w-full rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Confidence */}
            <div>
              <label className="mb-1 flex items-center justify-between text-sm font-medium text-gray-700">
                <span>Confidence</span>
                <span className="text-xs text-gray-500">
                  {(confidence * 100).toFixed(0)}%
                </span>
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={confidence}
                onChange={(e) => setConfidence(parseFloat(e.target.value))}
                className="w-full accent-blue-600"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 border-t px-4 py-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={creating || !sourceId || !targetId}
              className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {creating && <Loader2 className="h-4 w-4 animate-spin" />}
              Create Relationship
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
