/**
 * P5C-03: Hook for fetching clarification threads for a mismatch.
 */

import { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '@/lib/api';

export interface Clarification {
  id: number;
  question: string;
  answer: string | null;
  status: 'open' | 'answered' | 'closed';
  requested_by_user_id: number;
  assignee_user_id: number | null;
  created_at: string;
  answered_at: string | null;
}

export function useClarifications(mismatchId: number | null) {
  const [clarifications, setClarifications] = useState<Clarification[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const mutate = useCallback(async () => {
    if (!mismatchId) return;
    setIsLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/validation/mismatches/${mismatchId}/clarifications`,
        { credentials: 'include' }
      );
      if (res.ok) {
        const data = await res.json();
        setClarifications(data.clarifications ?? []);
      }
    } finally {
      setIsLoading(false);
    }
  }, [mismatchId]);

  useEffect(() => { mutate(); }, [mutate]);

  return { clarifications, isLoading, mutate };
}
