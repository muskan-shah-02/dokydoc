/**
 * P5C-01: Hook for fetching AI-generated file suggestions for a document.
 */

import { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '@/lib/api';

export interface FileSuggestion {
  id: number;
  suggested_filename: string;
  reason: string;
  atom_ids: number[];
  atom_count: number;
  fulfilled: boolean;
  fulfilled_by_component_id: number | null;
  created_at: string | null;
}

interface FileSuggestionsState {
  suggestions: FileSuggestion[];
  total: number;
  loading: boolean;
  error: string | null;
}

export function useFileSuggestions(documentId: number | null) {
  const [state, setState] = useState<FileSuggestionsState>({
    suggestions: [],
    total: 0,
    loading: false,
    error: null,
  });

  const fetchSuggestions = useCallback(async () => {
    if (!documentId) return;
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      const res = await fetch(
        `${API_BASE_URL}/documents/${documentId}/file-suggestions`,
        { credentials: 'include' }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setState({ suggestions: data.suggestions ?? [], total: data.total ?? 0, loading: false, error: null });
    } catch (err: unknown) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to load suggestions',
      }));
    }
  }, [documentId]);

  const requestRefresh = useCallback(async () => {
    if (!documentId) return;
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      await fetch(
        `${API_BASE_URL}/documents/${documentId}/request-uploads`,
        { method: 'POST', credentials: 'include' }
      );
      await fetchSuggestions();
    } catch (err: unknown) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Refresh failed',
      }));
    }
  }, [documentId, fetchSuggestions]);

  useEffect(() => {
    fetchSuggestions();
  }, [fetchSuggestions]);

  return { ...state, refetch: fetchSuggestions, requestRefresh };
}
