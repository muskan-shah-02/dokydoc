"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

interface ConceptDialogProps {
  open: boolean;
  onClose: () => void;
  onCreate: (data: {
    name: string;
    concept_type: string;
    description: string;
    confidence_score: number;
  }) => Promise<void>;
}

const CONCEPT_TYPES = [
  "Entity",
  "Process",
  "Attribute",
  "Value",
  "Event",
  "Role",
  "Service",
];

export function ConceptDialog({ open, onClose, onCreate }: ConceptDialogProps) {
  const [name, setName] = useState("");
  const [conceptType, setConceptType] = useState("Entity");
  const [description, setDescription] = useState("");
  const [confidence, setConfidence] = useState(0.85);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setError("");
    setCreating(true);
    try {
      await onCreate({
        name: name.trim(),
        concept_type: conceptType,
        description: description.trim(),
        confidence_score: confidence,
      });
      // Reset form
      setName("");
      setConceptType("Entity");
      setDescription("");
      setConfidence(0.85);
      onClose();
    } catch (err: any) {
      setError(err.detail || err.message || "Failed to create concept");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Dialog */}
      <div className="relative w-full max-w-md rounded-lg bg-white shadow-xl">
        <form onSubmit={handleSubmit}>
          <div className="border-b p-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Add New Concept
            </h2>
            <p className="mt-0.5 text-sm text-gray-500">
              Add a business concept to your knowledge graph
            </p>
          </div>

          <div className="space-y-4 p-4">
            {error && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
                {error}
              </div>
            )}

            {/* Name */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Concept Name *
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Customer, Payment Process"
                autoFocus
                className="w-full rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Type */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Type
              </label>
              <div className="grid grid-cols-4 gap-1.5">
                {CONCEPT_TYPES.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setConceptType(t)}
                    className={`rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                      conceptType === t
                        ? "bg-blue-600 text-white"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                placeholder="Brief description of this concept..."
                className="w-full resize-none rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
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
              disabled={creating || !name.trim()}
              className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {creating && <Loader2 className="h-4 w-4 animate-spin" />}
              Add Concept
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
