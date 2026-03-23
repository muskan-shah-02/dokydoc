"use client";

import { useState, useEffect } from "react";
import {
  X,
  Save,
  Trash2,
  ArrowRight,
  ArrowLeft,
  PlusCircle,
  Loader2,
  AlertTriangle,
} from "lucide-react";

interface Concept {
  id: number;
  name: string;
  concept_type: string;
  description: string | null;
  confidence_score: number;
  is_active: boolean;
  created_at: string;
}

interface Relationship {
  id: number;
  source_concept_id: number;
  target_concept_id: number;
  relationship_type: string;
  description: string | null;
  confidence_score: number;
}

interface ConceptWithRelationships extends Concept {
  outgoing_relationships: (Relationship & { target_concept_name?: string })[];
  incoming_relationships: (Relationship & { source_concept_name?: string })[];
}

interface ConceptDetailProps {
  concept: ConceptWithRelationships | null;
  allConcepts: Concept[];
  onClose: () => void;
  onUpdate: (id: number, data: Partial<Concept>) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  onDeleteRelationship: (id: number) => Promise<void>;
  onAddRelationship: () => void;
  loading?: boolean;
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

export function ConceptDetail({
  concept,
  allConcepts,
  onClose,
  onUpdate,
  onDelete,
  onDeleteRelationship,
  onAddRelationship,
  loading,
}: ConceptDetailProps) {
  const [editName, setEditName] = useState("");
  const [editType, setEditType] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editConfidence, setEditConfidence] = useState(0);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Sync form with selected concept
  useEffect(() => {
    if (concept) {
      setEditName(concept.name);
      setEditType(concept.concept_type);
      setEditDescription(concept.description || "");
      setEditConfidence(concept.confidence_score);
      setShowDeleteConfirm(false);
    }
  }, [concept]);

  if (!concept) return null;

  const hasChanges =
    editName !== concept.name ||
    editType !== concept.concept_type ||
    editDescription !== (concept.description || "") ||
    editConfidence !== concept.confidence_score;

  const handleSave = async () => {
    if (!hasChanges) return;
    setSaving(true);
    try {
      await onUpdate(concept.id, {
        name: editName,
        concept_type: editType,
        description: editDescription || null,
        confidence_score: editConfidence,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await onDelete(concept.id);
    } finally {
      setDeleting(false);
    }
  };

  const getConceptName = (id: number) => {
    return allConcepts.find((c) => c.id === id)?.name || `#${id}`;
  };

  const outgoing = concept.outgoing_relationships || [];
  const incoming = concept.incoming_relationships || [];

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b p-3">
        <h3 className="text-sm font-semibold text-gray-900">Edit Concept</h3>
        <button
          onClick={onClose}
          className="rounded-md p-1 hover:bg-gray-100"
        >
          <X className="h-4 w-4 text-gray-500" />
        </button>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto p-3">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
          </div>
        ) : (
          <div className="space-y-4">
            {/* Name */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-700">
                Name
              </label>
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Type */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-700">
                Type
              </label>
              <select
                value={editType}
                onChange={(e) => setEditType(e.target.value)}
                className="w-full rounded-md border bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {CONCEPT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            {/* Description */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-700">
                Description
              </label>
              <textarea
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                rows={3}
                placeholder="Describe this concept..."
                className="w-full resize-none rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Confidence */}
            <div>
              <label className="mb-1 flex items-center justify-between text-xs font-medium text-gray-700">
                <span>Confidence Score</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-xs font-semibold ${
                    editConfidence >= 0.8
                      ? "bg-green-100 text-green-700"
                      : editConfidence >= 0.5
                        ? "bg-amber-100 text-amber-700"
                        : "bg-red-100 text-red-700"
                  }`}
                >
                  {(editConfidence * 100).toFixed(0)}%
                </span>
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={editConfidence}
                onChange={(e) => setEditConfidence(parseFloat(e.target.value))}
                className="w-full accent-blue-600"
              />
              <div className="mt-0.5 flex justify-between text-xs text-gray-400">
                <span>Low</span>
                <span>High</span>
              </div>
            </div>

            {/* Created */}
            <div className="rounded-md bg-gray-50 px-3 py-2 text-xs text-gray-500">
              Created: {new Date(concept.created_at).toLocaleDateString()}
            </div>

            {/* Save button */}
            {hasChanges && (
              <button
                onClick={handleSave}
                disabled={saving || !editName.trim()}
                className="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                Save Changes
              </button>
            )}

            {/* Relationships */}
            <div className="border-t pt-4">
              <div className="mb-2 flex items-center justify-between">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Relationships ({outgoing.length + incoming.length})
                </h4>
                <button
                  onClick={onAddRelationship}
                  className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50"
                >
                  <PlusCircle className="h-3 w-3" />
                  Add
                </button>
              </div>

              {outgoing.length + incoming.length === 0 ? (
                <p className="text-center text-xs text-gray-400">
                  No relationships
                </p>
              ) : (
                <div className="space-y-1.5">
                  {/* Outgoing */}
                  {outgoing.map((rel) => (
                    <div
                      key={`out-${rel.id}`}
                      className="group flex items-center gap-2 rounded-md bg-gray-50 px-2.5 py-2 text-xs"
                    >
                      <ArrowRight className="h-3 w-3 flex-shrink-0 text-blue-500" />
                      <div className="min-w-0 flex-1">
                        <span className="font-medium text-gray-700">
                          {rel.relationship_type}
                        </span>
                        <span className="text-gray-400"> &rarr; </span>
                        <span className="font-medium text-gray-900">
                          {getConceptName(rel.target_concept_id)}
                        </span>
                      </div>
                      <button
                        onClick={() => onDeleteRelationship(rel.id)}
                        className="hidden flex-shrink-0 rounded p-0.5 text-gray-400 hover:bg-red-50 hover:text-red-500 group-hover:block"
                        title="Remove"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}

                  {/* Incoming */}
                  {incoming.map((rel) => (
                    <div
                      key={`in-${rel.id}`}
                      className="group flex items-center gap-2 rounded-md bg-gray-50 px-2.5 py-2 text-xs"
                    >
                      <ArrowLeft className="h-3 w-3 flex-shrink-0 text-green-500" />
                      <div className="min-w-0 flex-1">
                        <span className="font-medium text-gray-900">
                          {getConceptName(rel.source_concept_id)}
                        </span>
                        <span className="text-gray-400"> &rarr; </span>
                        <span className="font-medium text-gray-700">
                          {rel.relationship_type}
                        </span>
                      </div>
                      <button
                        onClick={() => onDeleteRelationship(rel.id)}
                        className="hidden flex-shrink-0 rounded p-0.5 text-gray-400 hover:bg-red-50 hover:text-red-500 group-hover:block"
                        title="Remove"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Delete action */}
      <div className="border-t p-3">
        {showDeleteConfirm ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-red-700">
              <AlertTriangle className="h-4 w-4" />
              Delete "{concept.name}"?
            </div>
            <p className="mb-3 text-xs text-red-600">
              This will also remove all {outgoing.length + incoming.length}{" "}
              relationships. This cannot be undone.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 rounded-md border bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex flex-1 items-center justify-center gap-1 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Trash2 className="h-3 w-3" />
                )}
                Delete
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-red-200 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
          >
            <Trash2 className="h-4 w-4" />
            Delete Concept
          </button>
        )}
      </div>
    </div>
  );
}
