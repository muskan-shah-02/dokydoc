/**
 * Phase 3 (P3.8): Data flow diagram hooks.
 *
 * useEgocentricFlow  — loads the 1-hop neighbourhood for a component
 * useRequestTrace    — BFS forward from an ENDPOINT
 * useTaskStatus      — polls a Celery task until done
 */

import { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '@/lib/api';

export interface FlowNode {
  id: number;
  name: string;
  location: string;
  file_role: string | null;
}

export interface FlowEdge {
  id: number;
  source_component_id: number;
  target_component_id: number | null;
  edge_type: string;
  data_summary: string;
  metadata: Record<string, any> | null;
  target_ref: string | null;
}

export interface FlowDiagram {
  component_id?: number;
  root_component_id?: number;
  nodes: FlowNode[];
  edges: FlowEdge[];
  mermaid: string;
  mode: string;
  depth_reached?: number;
}

async function fetchJson(url: string): Promise<any> {
  const res = await fetch(url, { credentials: 'include' });
  if (res.status === 403) {
    const body = await res.json().catch(() => ({}));
    throw { type: 'PREMIUM_REQUIRED', detail: body?.detail };
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function useEgocentricFlow(componentId: number | null, mode: 'technical' | 'simple' = 'technical') {
  const [data, setData] = useState<FlowDiagram | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  const load = useCallback(async () => {
    if (!componentId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchJson(
        `${API_BASE_URL}/code-components/${componentId}/data-flow/egocentric?mode=${mode}`
      );
      setData(result);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [componentId, mode]);

  useEffect(() => { load(); }, [load]);

  return { data, loading, error, reload: load };
}

export function useRequestTrace(
  componentId: number | null,
  mode: 'technical' | 'simple' = 'technical',
  maxDepth: number = 5,
) {
  const [data, setData] = useState<FlowDiagram | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  const load = useCallback(async () => {
    if (!componentId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchJson(
        `${API_BASE_URL}/code-components/${componentId}/data-flow/request-trace?mode=${mode}&max_depth=${maxDepth}`
      );
      setData(result);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [componentId, mode, maxDepth]);

  useEffect(() => { load(); }, [load]);

  return { data, loading, error, reload: load };
}

export type TaskState = 'PENDING' | 'STARTED' | 'PROGRESS' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'REVOKED';

export interface TaskStatus {
  task_id: string;
  state: TaskState;
  meta: Record<string, any> | null;
  ready: boolean;
  successful: boolean | null;
}

export function useTaskStatus(taskId: string | null, intervalMs = 2000) {
  const [status, setStatus] = useState<TaskStatus | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!taskId) return;
    let stopped = false;

    const poll = async () => {
      setLoading(true);
      try {
        const result = await fetchJson(`${API_BASE_URL}/tasks/${taskId}/status`);
        if (!stopped) setStatus(result);
        if (!stopped && !result.ready) {
          setTimeout(poll, intervalMs);
        } else {
          setLoading(false);
        }
      } catch {
        if (!stopped) setLoading(false);
      }
    };

    poll();
    return () => { stopped = true; };
  }, [taskId, intervalMs]);

  return { status, loading };
}
