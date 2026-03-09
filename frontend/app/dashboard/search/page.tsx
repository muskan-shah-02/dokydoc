"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Search,
  X,
  Loader2,
  FileText,
  Code,
  Brain,
  Network,
  Filter,
  ArrowRight,
  Clock,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";

// --- Types ---

interface UnifiedResult {
  id: number;
  name: string;
  category: string;
  relevance?: number;
  similarity?: number;
  // concept fields
  concept_type?: string;
  description?: string | null;
  source_type?: string;
  confidence_score?: number | null;
  match_type?: string;
  // document fields
  document_type?: string;
  status?: string;
  file_size_kb?: number;
  snippet?: string;
  // code fields
  component_type?: string;
  location?: string;
  analysis_status?: string;
  summary?: string;
  repo_name?: string;
  // graph fields
  source_id?: number;
  version?: number;
  // common
  created_at?: string;
}

interface SearchResponse {
  query: string;
  total_count: number;
  results: UnifiedResult[];
  facets: {
    concepts: number;
    documents: number;
    code: number;
    graphs: number;
  };
}

interface Suggestion {
  text: string;
  source: string;
}

const CATEGORY_ALL = "all";
const CATEGORIES = [
  { key: CATEGORY_ALL, label: "All", icon: Sparkles },
  { key: "concepts", label: "Concepts", icon: Brain },
  { key: "documents", label: "Documents", icon: FileText },
  { key: "code", label: "Code", icon: Code },
  { key: "graphs", label: "Graphs", icon: Network },
];

export default function SearchPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") || "";

  const [query, setQuery] = useState(initialQuery);
  const [activeCategory, setActiveCategory] = useState(CATEGORY_ALL);
  const [results, setResults] = useState<UnifiedResult[]>([]);
  const [facets, setFacets] = useState<SearchResponse["facets"]>({
    concepts: 0,
    documents: 0,
    code: 0,
    graphs: 0,
  });
  const [totalCount, setTotalCount] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Execute search
  const executeSearch = useCallback(
    async (q: string, category: string = CATEGORY_ALL) => {
      if (!q.trim() || q.length < 2) return;

      setIsSearching(true);
      setHasSearched(true);
      setShowSuggestions(false);

      try {
        const params = new URLSearchParams({ q, limit: "40" });
        if (category !== CATEGORY_ALL) {
          params.set("categories", category);
        }

        const data = await api.get<SearchResponse>(
          `/search/unified?${params.toString()}`
        );
        setResults(data.results || []);
        setFacets(data.facets || { concepts: 0, documents: 0, code: 0, graphs: 0 });
        setTotalCount(data.total_count || 0);
      } catch {
        setResults([]);
        setFacets({ concepts: 0, documents: 0, code: 0, graphs: 0 });
        setTotalCount(0);
      } finally {
        setIsSearching(false);
      }
    },
    []
  );

  // Fetch suggestions
  const fetchSuggestions = useCallback(async (q: string) => {
    if (!q.trim() || q.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    try {
      const data = await api.get<{ suggestions: Suggestion[] }>(
        `/search/suggestions?q=${encodeURIComponent(q)}&limit=6`
      );
      setSuggestions(data.suggestions || []);
      setShowSuggestions(true);
    } catch {
      setSuggestions([]);
    }
  }, []);

  // Handle input change with debounced suggestions
  const handleInputChange = useCallback(
    (value: string) => {
      setQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => fetchSuggestions(value), 200);
    },
    [fetchSuggestions]
  );

  // Handle search submit
  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      executeSearch(query, activeCategory);
    },
    [query, activeCategory, executeSearch]
  );

  // Handle category change
  const handleCategoryChange = useCallback(
    (category: string) => {
      setActiveCategory(category);
      if (hasSearched && query.trim()) {
        executeSearch(query, category);
      }
    },
    [query, hasSearched, executeSearch]
  );

  // Handle suggestion click
  const handleSuggestionClick = useCallback(
    (text: string) => {
      setQuery(text);
      setShowSuggestions(false);
      executeSearch(text, activeCategory);
    },
    [activeCategory, executeSearch]
  );

  // Navigate to result
  const navigateToResult = useCallback(
    (result: UnifiedResult) => {
      switch (result.category) {
        case "concept":
          router.push(`/dashboard/ontology?highlight=${result.id}`);
          break;
        case "document":
          router.push(`/dashboard/documents`);
          break;
        case "code":
          router.push(`/dashboard/code/${result.id}`);
          break;
        case "graph":
          router.push(`/dashboard/ontology`);
          break;
        default:
          break;
      }
    },
    [router]
  );

  // Run initial search if query param present
  useEffect(() => {
    if (initialQuery) {
      executeSearch(initialQuery);
    }
    inputRef.current?.focus();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Filter results by active category
  const filteredResults =
    activeCategory === CATEGORY_ALL
      ? results
      : results.filter((r) => {
          if (activeCategory === "concepts") return r.category === "concept";
          if (activeCategory === "documents") return r.category === "document";
          if (activeCategory === "code") return r.category === "code";
          if (activeCategory === "graphs") return r.category === "graph";
          return true;
        });

  return (
    <div className="min-h-screen bg-gray-50/50 p-4 lg:p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-blue-50 p-3">
            <Search className="h-6 w-6 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Search</h1>
            <p className="mt-0.5 text-sm text-gray-500">
              Search across concepts, documents, code, and knowledge graphs
            </p>
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div className="relative mb-6">
        <form onSubmit={handleSubmit} className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => handleInputChange(e.target.value)}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setShowSuggestions(false);
            }}
            placeholder="Search for anything... concepts, documents, code files, services"
            className="w-full rounded-xl border border-gray-300 bg-white py-3.5 pl-12 pr-24 text-base
                       placeholder-gray-400 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1.5">
            {query && (
              <button
                type="button"
                onClick={() => {
                  setQuery("");
                  setResults([]);
                  setHasSearched(false);
                  inputRef.current?.focus();
                }}
                className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            )}
            <button
              type="submit"
              disabled={isSearching || !query.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700
                         disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSearching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Search"
              )}
            </button>
          </div>
        </form>

        {/* Suggestions Dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute z-40 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg">
            {suggestions.map((s, idx) => (
              <button
                key={`${s.text}-${idx}`}
                onClick={() => handleSuggestionClick(s.text)}
                className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-gray-50 transition-colors"
              >
                <Search className="h-3.5 w-3.5 text-gray-400" />
                <span className="text-sm text-gray-700">{s.text}</span>
                <span className="ml-auto text-[10px] rounded-full bg-gray-100 px-2 py-0.5 text-gray-500">
                  {s.source}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Category Tabs */}
      <div className="mb-6 flex items-center gap-1 rounded-lg border bg-white p-1">
        {CATEGORIES.map((cat) => {
          const Icon = cat.icon;
          const count =
            cat.key === CATEGORY_ALL
              ? totalCount
              : facets[cat.key as keyof typeof facets] || 0;

          return (
            <button
              key={cat.key}
              onClick={() => handleCategoryChange(cat.key)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                activeCategory === cat.key
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{cat.label}</span>
              {hasSearched && (
                <span
                  className={`ml-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${
                    activeCategory === cat.key
                      ? "bg-blue-100 text-blue-700"
                      : "bg-gray-100 text-gray-500"
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Results */}
      {isSearching ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <p className="ml-3 text-sm text-gray-500">Searching across all sources...</p>
        </div>
      ) : hasSearched && filteredResults.length === 0 ? (
        <div className="flex h-64 flex-col items-center justify-center rounded-lg border bg-white">
          <Search className="mb-3 h-10 w-10 text-gray-300" />
          <p className="text-sm font-medium text-gray-600">
            No results found for &ldquo;{query}&rdquo;
          </p>
          <p className="mt-1 text-xs text-gray-400">
            Try different keywords or broaden your search
          </p>
        </div>
      ) : hasSearched ? (
        <div className="space-y-2">
          {filteredResults.map((result, idx) => (
            <ResultCard
              key={`${result.category}-${result.id}-${idx}`}
              result={result}
              onClick={() => navigateToResult(result)}
            />
          ))}
        </div>
      ) : (
        /* Empty state */
        <div className="flex h-64 flex-col items-center justify-center rounded-lg border bg-white">
          <Sparkles className="mb-3 h-10 w-10 text-gray-300" />
          <p className="text-sm font-medium text-gray-600">
            Search across your entire knowledge base
          </p>
          <p className="mt-1 text-xs text-gray-400">
            Find concepts, documents, code components, and knowledge graphs
          </p>
        </div>
      )}
    </div>
  );
}

// --- Result Card Component ---

function ResultCard({
  result,
  onClick,
}: {
  result: UnifiedResult;
  onClick: () => void;
}) {
  const getCategoryStyle = () => {
    switch (result.category) {
      case "concept":
        return {
          icon: <Brain className="h-4 w-4" />,
          color: "bg-purple-50 text-purple-700 border-purple-200",
          iconBg: "bg-purple-100",
          label: "Concept",
        };
      case "document":
        return {
          icon: <FileText className="h-4 w-4" />,
          color: "bg-blue-50 text-blue-700 border-blue-200",
          iconBg: "bg-blue-100",
          label: "Document",
        };
      case "code":
        return {
          icon: <Code className="h-4 w-4" />,
          color: "bg-green-50 text-green-700 border-green-200",
          iconBg: "bg-green-100",
          label: "Code",
        };
      case "graph":
        return {
          icon: <Network className="h-4 w-4" />,
          color: "bg-amber-50 text-amber-700 border-amber-200",
          iconBg: "bg-amber-100",
          label: "Graph",
        };
      default:
        return {
          icon: <Search className="h-4 w-4" />,
          color: "bg-gray-50 text-gray-700 border-gray-200",
          iconBg: "bg-gray-100",
          label: "Result",
        };
    }
  };

  const style = getCategoryStyle();
  const relevance = result.relevance ?? result.similarity ?? 0;

  return (
    <button
      onClick={onClick}
      className="flex w-full items-start gap-4 rounded-lg border bg-white p-4 text-left
                 hover:border-blue-200 hover:shadow-sm transition-all"
    >
      {/* Category Icon */}
      <div className={`mt-0.5 flex-shrink-0 rounded-lg p-2 ${style.iconBg}`}>
        {style.icon}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-gray-900 truncate">
            {result.name || result.summary?.slice(0, 60) || `Result #${result.id}`}
          </span>
          <span
            className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-medium ${style.color}`}
          >
            {style.label}
          </span>
          {/* Type badges */}
          {result.concept_type && (
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] text-gray-600">
              {result.concept_type}
            </span>
          )}
          {result.component_type && (
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] text-gray-600">
              {result.component_type}
            </span>
          )}
          {result.document_type && (
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] text-gray-600">
              {result.document_type}
            </span>
          )}
        </div>

        {/* Description/Summary/Snippet */}
        {(result.description || result.summary || result.snippet) && (
          <p className="mt-1 text-xs text-gray-500 line-clamp-2">
            {result.description || result.summary || result.snippet}
          </p>
        )}

        {/* Meta row */}
        <div className="mt-1.5 flex items-center gap-3 text-[10px] text-gray-400">
          {result.repo_name && (
            <span className="flex items-center gap-1">
              <Code className="h-3 w-3" /> {result.repo_name}
            </span>
          )}
          {result.location && (
            <span className="truncate max-w-[200px]">{result.location}</span>
          )}
          {result.source_type && (
            <span>Source: {result.source_type}</span>
          )}
          {result.match_type && (
            <span className="flex items-center gap-0.5">
              <Sparkles className="h-3 w-3" /> {result.match_type}
            </span>
          )}
          {result.created_at && (
            <span className="flex items-center gap-0.5">
              <Clock className="h-3 w-3" />{" "}
              {new Date(result.created_at).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>

      {/* Relevance Score */}
      <div className="flex flex-col items-end gap-1 flex-shrink-0">
        {relevance > 0 && (
          <div className="flex items-center gap-1">
            <div className="h-1.5 w-12 rounded-full bg-gray-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-blue-500"
                style={{ width: `${Math.min(relevance * 100, 100)}%` }}
              />
            </div>
            <span className="text-[10px] text-gray-400">
              {(relevance * 100).toFixed(0)}%
            </span>
          </div>
        )}
        <ArrowRight className="h-4 w-4 text-gray-300" />
      </div>
    </button>
  );
}
