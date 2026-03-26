/**
 * SPRINT 3: Enhanced Document Processing Hook (UI-02)
 *
 * Improvements:
 * - Exponential backoff: fast polling during active processing, slower when idle
 * - Step-level progress with pass names
 * - Handles new pass_2_segmentation status from CAE-04 fix
 * - Cleanup on unmount to prevent memory leaks
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { API_BASE_URL } from '@/lib/api';

interface ProcessingState {
  status: 'idle' | 'uploading' | 'processing' | 'completed' | 'error';
  progress: number;
  currentStep: string;
  currentPass: string; // e.g., "Pass 1", "Pass 2", "Pass 3"
  error: string | null;
  documentId: number | null;
}

export function useDocumentProcessing() {
  const [state, setState] = useState<ProcessingState>({
    status: 'idle',
    progress: 0,
    currentStep: '',
    currentPass: '',
    error: null,
    documentId: null
  });

  const pollTimeout = useRef<NodeJS.Timeout | null>(null);
  const isPolling = useRef(false);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollTimeout.current) clearTimeout(pollTimeout.current);
      isPolling.current = false;
    };
  }, []);

  const startPolling = useCallback((docId: number, token: string) => {
    // Clear any existing poller
    if (pollTimeout.current) clearTimeout(pollTimeout.current);
    isPolling.current = true;

    setState(prev => ({ ...prev, documentId: docId, status: 'processing' }));

    let consecutiveIdlePolls = 0;

    const poll = async () => {
      if (!isPolling.current) return;

      try {
        const res = await fetch(`${API_BASE_URL}/documents/${docId}/status`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        if (!res.ok) throw new Error("Failed to fetch status");

        const data = await res.json();

        if (data.status === 'completed') {
          setState(prev => ({
            ...prev,
            status: 'completed',
            progress: 100,
            currentStep: 'Analysis Complete',
            currentPass: 'Done',
          }));
          isPolling.current = false;
          return;
        }

        if (data.status === 'stopped') {
          setState(prev => ({
            ...prev,
            status: 'error',
            error: data.error_message || "Analysis stopped by user",
            currentStep: 'Stopped',
            currentPass: '',
          }));
          isPolling.current = false;
          return;
        }

        if (data.status.includes('failed') || data.status.includes('error')) {
          setState(prev => ({
            ...prev,
            status: 'error',
            error: data.error_message || "Analysis failed",
            progress: data.progress || 0,
            currentStep: 'Failed',
            currentPass: '',
          }));
          isPolling.current = false;
          return;
        }

        // Still processing — update with step-level detail
        const { step, pass } = formatStatusDetail(data.status);
        setState(prev => ({
          ...prev,
          status: 'processing',
          progress: data.progress || 0,
          currentStep: step,
          currentPass: pass,
        }));

        // Adaptive polling: fast during active processing, slower during idle states
        const activeStatuses = [
          'analyzing', 'pass_1_composition', 'pass_2_segmenting',
          'pass_2_segmentation', 'pass_3_extraction'
        ];

        if (activeStatuses.includes(data.status)) {
          consecutiveIdlePolls = 0;
          // Active: poll every 2s
          pollTimeout.current = setTimeout(poll, 2000);
        } else {
          consecutiveIdlePolls++;
          // Idle: exponential backoff up to 10s
          const delay = Math.min(2000 * Math.pow(1.5, consecutiveIdlePolls), 10000);
          pollTimeout.current = setTimeout(poll, delay);
        }
        return;

      } catch (err) {
        console.error("Polling error:", err);
        // Retry with backoff on error
        pollTimeout.current = setTimeout(poll, 5000);
        return;
      }
    };

    // Start first poll immediately
    poll();
  }, []);

  const stopPolling = useCallback(() => {
    isPolling.current = false;
    if (pollTimeout.current) clearTimeout(pollTimeout.current);
  }, []);

  return { state, setState, startPolling, stopPolling };
}

// Helper: step-level detail with pass name
function formatStatusDetail(status: string): { step: string; pass: string } {
  switch (status) {
    case 'uploaded':
      return { step: 'Document Uploaded', pass: 'Queued' };
    case 'processing':
      return { step: 'Starting Pipeline...', pass: 'Init' };
    case 'parsing':
      return { step: 'Extracting Text & Images...', pass: 'Parsing' };
    case 'analyzing':
      return { step: 'Running AI Analysis...', pass: 'Analyzing' };
    case 'pass_1_composition':
      return { step: 'Classifying Document Type...', pass: 'Pass 1' };
    case 'pass_2_segmenting':
    case 'pass_2_segmentation':
      return { step: 'Segmenting Content...', pass: 'Pass 2' };
    case 'pass_3_extraction':
      return { step: 'Extracting Structured Data...', pass: 'Pass 3' };
    default:
      return { step: 'Processing...', pass: '' };
  }
}
