/**
 * P5C-02: Hook for fetching team members for upload request notifications.
 */

import { useState, useEffect } from 'react';
import { API_BASE_URL } from '@/lib/api';

export interface TeamMember {
  id: number;
  name: string;
  email: string;
  roles: string[] | null;
}

export function useTeamMembers(documentId: number | null) {
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!documentId) return;
    setIsLoading(true);
    fetch(`${API_BASE_URL}/documents/${documentId}/team-members`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(data => setTeamMembers(data.team_members ?? []))
      .catch(() => setTeamMembers([]))
      .finally(() => setIsLoading(false));
  }, [documentId]);

  return { teamMembers, isLoading };
}
