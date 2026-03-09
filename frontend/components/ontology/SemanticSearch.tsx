"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Search, X, Loader2, Brain, FileText, Code, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";

interface SearchResult {
  id: number;
  name: string;
  concept_type: string;
  description: string | null;
  source_type: string;
  confidence_score: number | null;
  initiative_id: number | null;
  similarity: number | null;
  match_type: string;
}

interface SearchResponse {
  query: string;
  results: SearchResult[];
  count: number;
}

interface SemanticSearchProps {
  onSelectConcept?: (concept: SearchResult) => void;
  initiativeId?: number;
  className?: string;
}

export default function SemanticSearch({
  onSelectConcept,
  initiativeId,
  className = "",
}: SemanticSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const doSearch = useCallback(
    async (q: string) => {
      if (!q.trim() || q.length < 2) {
        setResults([]);
        setIsOpen(false);
        return;
      }

      setIsSearching(true);
      try {
        const params = new URLSearchParams({ q, limit: "15" });
        if (initiativeId) params.set("initiative_id", String(initiativeId));

        const data = await api.get<SearchResponse>(
          `/ontology/search?${params.toString()}`
        );
        setResults(data.results || []);
        setIsOpen(true);
      } catch {
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    },
    [initiativeId]
  );

  const handleInputChange = useCallback(
    (value: string) => {
      setQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => doSearch(value), 300);
    },
    [doSearch]
  );

  const handleSelect = useCallback(
    (result: SearchResult) => {
      setIsOpen(false);
      setQuery("");
      onSelectConcept?.(result);
    },
    [onSelectConcept]
  );

  const handleClear = useCallback(() => {
    setQuery("");
    setResults([]);
    setIsOpen(false);
  }, []);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const getSourceIcon = (sourceType: string) => {
    switch (sourceType) {
      case "document":
        return <FileText className="h-3.5 w-3.5 text-blue-500" />;
      case "code":
        return <Code className="h-3.5 w-3.5 text-green-500" />;
      case "both":
        return <Brain className="h-3.5 w-3.5 text-purple-500" />;
      default:
        return <Brain className="h-3.5 w-3.5 text-gray-400" />;
    }
  };

  const getTypeBadgeColor = (type: string) => {
    const colors: Record<string, string> = {
      Entity: "bg-blue-100 text-blue-700",
      Process: "bg-green-100 text-green-700",
      Service: "bg-purple-100 text-purple-700",
      FEATURE: "bg-indigo-100 text-indigo-700",
      TECHNOLOGY: "bg-orange-100 text-orange-700",
    };
    return colors[type] || "bg-gray-100 text-gray-700";
  };

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {/* Search Input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => handleInputChange(e.target.value)}
          onFocus={() => results.length > 0 && setIsOpen(true)}
          placeholder="Search concepts, entities, services..."
          className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-10 pr-10 text-sm
                     placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        {isSearching ? (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-gray-400" />
        ) : query ? (
          <button
            onClick={handleClear}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      {/* Results Dropdown */}
      {isOpen && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg max-h-96 overflow-y-auto">
          <div className="px-3 py-2 text-xs font-medium text-gray-500 border-b">
            {results.length} result{results.length !== 1 ? "s" : ""} found
          </div>
          {results.map((result) => (
            <button
              key={result.id}
              onClick={() => handleSelect(result)}
              className="flex w-full items-start gap-3 px-3 py-2.5 text-left hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-b-0"
            >
              <div className="mt-0.5 flex-shrink-0">
                {getSourceIcon(result.source_type)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900 truncate">
                    {result.name}
                  </span>
                  <span
                    className={`inline-flex rounded-full px-1.5 py-0.5 text-[10px] font-medium ${getTypeBadgeColor(
                      result.concept_type
                    )}`}
                  >
                    {result.concept_type}
                  </span>
                </div>
                {result.description && (
                  <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">
                    {result.description}
                  </p>
                )}
                <div className="flex items-center gap-2 mt-0.5">
                  {result.similarity != null && (
                    <span className="text-[10px] text-gray-400">
                      {(result.similarity * 100).toFixed(0)}% match
                    </span>
                  )}
                  {result.confidence_score != null && (
                    <span className="text-[10px] text-gray-400">
                      {(result.confidence_score * 100).toFixed(0)}% confidence
                    </span>
                  )}
                </div>
              </div>
              <ArrowRight className="mt-1 h-3.5 w-3.5 flex-shrink-0 text-gray-300" />
            </button>
          ))}
        </div>
      )}

      {/* No Results */}
      {isOpen && results.length === 0 && query.length >= 2 && !isSearching && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg">
          <div className="px-4 py-6 text-center text-sm text-gray-500">
            No concepts found for &ldquo;{query}&rdquo;
          </div>
        </div>
      )}
    </div>
  );
}
