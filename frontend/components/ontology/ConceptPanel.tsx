"use client";

import { useState, useMemo } from "react";
import { Search, Circle, ChevronRight } from "lucide-react";

interface Concept {
  id: number;
  name: string;
  concept_type: string;
  description: string | null;
  confidence_score: number;
  is_active: boolean;
}

interface ConceptPanelProps {
  concepts: Concept[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  conceptTypes: string[];
}

const TYPE_DOT_COLORS: Record<string, string> = {
  Entity: "bg-blue-500",
  Process: "bg-green-500",
  Attribute: "bg-amber-500",
  Value: "bg-purple-500",
  Event: "bg-red-500",
  Role: "bg-teal-500",
  Service: "bg-indigo-500",
};

export function ConceptPanel({
  concepts,
  selectedId,
  onSelect,
  conceptTypes,
}: ConceptPanelProps) {
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState<string>("all");

  const filtered = useMemo(() => {
    let result = concepts;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.concept_type.toLowerCase().includes(q) ||
          c.description?.toLowerCase().includes(q)
      );
    }
    if (filterType !== "all") {
      result = result.filter((c) => c.concept_type === filterType);
    }
    return result;
  }, [concepts, search, filterType]);

  // Group by type
  const grouped = useMemo(() => {
    const groups: Record<string, Concept[]> = {};
    filtered.forEach((c) => {
      if (!groups[c.concept_type]) groups[c.concept_type] = [];
      groups[c.concept_type].push(c);
    });
    return groups;
  }, [filtered]);

  return (
    <div className="flex h-full flex-col">
      {/* Search */}
      <div className="border-b p-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search concepts..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border py-2 pl-8 pr-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        {/* Type filter */}
        <div className="mt-2 flex flex-wrap gap-1">
          <button
            onClick={() => setFilterType("all")}
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
              filterType === "all"
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            All ({concepts.length})
          </button>
          {conceptTypes.map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(filterType === type ? "all" : type)}
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
                filterType === type
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {/* Concept List */}
      <div className="flex-1 overflow-y-auto">
        {Object.keys(grouped).length === 0 ? (
          <div className="p-4 text-center text-sm text-gray-400">
            {search ? "No concepts match your search" : "No concepts yet"}
          </div>
        ) : (
          Object.entries(grouped).map(([type, items]) => (
            <div key={type}>
              {/* Group header */}
              <div className="sticky top-0 flex items-center gap-2 border-b bg-gray-50/90 px-3 py-1.5 backdrop-blur-sm">
                <span
                  className={`h-2 w-2 rounded-full ${TYPE_DOT_COLORS[type] || "bg-gray-400"}`}
                />
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  {type}
                </span>
                <span className="text-xs text-gray-400">({items.length})</span>
              </div>

              {/* Items */}
              {items.map((concept) => (
                <button
                  key={concept.id}
                  onClick={() => onSelect(concept.id)}
                  className={`flex w-full items-center gap-2 border-b px-3 py-2.5 text-left transition-colors ${
                    selectedId === concept.id
                      ? "bg-blue-50 border-l-2 border-l-blue-500"
                      : "hover:bg-gray-50 border-l-2 border-l-transparent"
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="truncate text-sm font-medium text-gray-900">
                        {concept.name}
                      </span>
                      {/* Confidence indicator */}
                      <Circle
                        className={`h-2 w-2 flex-shrink-0 ${
                          concept.confidence_score >= 0.8
                            ? "fill-green-500 text-green-500"
                            : concept.confidence_score >= 0.5
                              ? "fill-amber-500 text-amber-500"
                              : "fill-red-500 text-red-500"
                        }`}
                      />
                    </div>
                    {concept.description && (
                      <p className="mt-0.5 truncate text-xs text-gray-500">
                        {concept.description}
                      </p>
                    )}
                  </div>
                  <ChevronRight
                    className={`h-4 w-4 flex-shrink-0 ${
                      selectedId === concept.id ? "text-blue-500" : "text-gray-300"
                    }`}
                  />
                </button>
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
