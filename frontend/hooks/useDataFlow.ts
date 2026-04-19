/**
 * Phase 3 (P3.8 revised): Data flow diagram hooks.
 * GAP-4: useEgocentricFlow now returns edges_in + edges_out separately.
 * GAP-6: useRequestTrace accepts traceDepth parameter.
 */

import { useState, useEffect, useCallback } from "react";
import { API_BASE_URL } from "@/lib/api";

export interface FlowNode {
  component_id: number | null;
  id?: number;
  name: string;
  location: string | null;
  file_role: string | null;
  summary?: string | null;
  is_external?: boolean;
}

export interface FlowEdge {
  id: number;
  source_component_id: number;
  target_component_id: number | null;
  edge_type: string;
  source_function?: string | null;
  target_function?: string | null;
  data_in_description?: string | null;
  data_out_description?: string | null;
  human_label?: string | null;
  external_target_name?: string | null;
  step_index?: number | null;
  data_summary?: string | null;
  created_at?: string | null;
}

export interface EgocentricData {
  component_id: number;
  file_role: string | null;
  edges_in: FlowEdge[];
  edges_out: FlowEdge[];
  nodes: FlowNode[];
  mermaid_technical: string;
  mermaid_simple: string;
  total_edges: number;
  edges_built_at: string | null;
}

export interface TraceData {
  start_component_id: number;
  depth: number;
  nodes: FlowNode[];
  edges: FlowEdge[];
  mermaid_technical: string;
  mermaid_simple: string;
  total_nodes: number;
  total_edges: number;
  edges_built_at: string | null;
}

async function fetchJson(url: string): Promise<any> {
  const res = await fetch(url, { credentials: "include" });
  if (res.status === 403) {
    const body = await res.json().catch(() => ({}));
    const err: any = new Error("premium_required");
    err.type = "PREMIUM_REQUIRED";
    err.detail = body?.detail;
    throw err;
  }
  if (!res.ok) {
    const err: any = new Error(`HTTP ${res.status}`);
    throw err;
  }
  return res.json();
}

export function useEgocentricFlow(
  componentId: number | null,
  mode: "technical" | "simple" = "technical",
) {
  const [data, setData] = useState<EgocentricData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  const load = useCallback(async () => {
    if (!componentId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchJson(
        `${API_BASE_URL}/code-components/${componentId}/data-flow/egocentric`,
      );
      setData(result);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [componentId]);

  useEffect(() => { load(); }, [load]);

  return { data, loading, error, reload: load };
}

export function useRequestTrace(
  componentId: number | null,
  mode: "technical" | "simple" = "technical",
  maxDepth: number = 5,
) {
  const [data, setData] = useState<TraceData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  const load = useCallback(async () => {
    if (!componentId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchJson(
        `${API_BASE_URL}/code-components/${componentId}/data-flow/request-trace?max_depth=${maxDepth}`,
      );
      setData(result);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [componentId, maxDepth]);

  useEffect(() => { load(); }, [load]);

  return { data, loading, error, reload: load };
}

export type TaskState =
  | "PENDING" | "STARTED" | "PROGRESS"
  | "SUCCESS" | "FAILURE" | "RETRY" | "REVOKED";

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
          if (!stopped) setLoading(false);
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
