/**
 * P5C-04: Hook for fetching UAT checklist items for a document.
 */

import { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '@/lib/api';

export interface UATChecklistSummary {
  total: number;
  checked: number;
  pending: number;
  passed: number;
  failed: number;
  completion_pct: number;
}

export interface UATChecklistItem {
  id: number;
  atom_id: string;
  atom_type: string;
  content: string;
  criticality: string;
  result: 'pass' | 'fail' | 'blocked' | null;
  notes: string | null;
  checked_by_user_id: number | null;
  checked_at: string | null;
}

interface UATChecklist {
  summary: UATChecklistSummary;
  items: UATChecklistItem[];
}

const EMPTY: UATChecklist = {
  summary: { total: 0, checked: 0, pending: 0, passed: 0, failed: 0, completion_pct: 0 },
  items: [],
};

export function useUATChecklist(documentId: number | null) {
  const [checklist, setChecklist] = useState<UATChecklist>(EMPTY);
  const [isLoading, setIsLoading] = useState(false);

  const mutate = useCallback(async () => {
    if (!documentId) return;
    setIsLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/validation/${documentId}/uat-checklist`,
        { credentials: 'include' }
      );
      if (res.ok) {
        const data = await res.json();
        setChecklist({ summary: data.summary, items: data.items ?? [] });
      }
    } finally {
      setIsLoading(false);
    }
  }, [documentId]);

  useEffect(() => { mutate(); }, [mutate]);

  return { checklist, isLoading, mutate };
}
