import { useState, useRef, useCallback } from 'react';

interface ProcessingState {
  status: 'idle' | 'uploading' | 'processing' | 'completed' | 'error';
  progress: number;
  currentStep: string; // e.g., "Parsing Text", "Generating Embeddings"
  error: string | null;
  documentId: number | null;
}

export function useDocumentProcessing() {
  const [state, setState] = useState<ProcessingState>({
    status: 'idle',
    progress: 0,
    currentStep: '',
    error: null,
    documentId: null
  });

  const pollInterval = useRef<NodeJS.Timeout | null>(null);

  const startPolling = useCallback((docId: number, token: string) => {
    // Clear any existing poller
    if (pollInterval.current) clearInterval(pollInterval.current);

    pollInterval.current = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/v1/documents/${docId}/status`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        
        if (!res.ok) throw new Error("Failed to fetch status");
        
        const data = await res.json();
        // data = { status: "parsing", progress: 25, error_message: null }

        if (data.status === 'completed') {
          setState(prev => ({ ...prev, status: 'completed', progress: 100, currentStep: 'Analysis Complete' }));
          if (pollInterval.current) clearInterval(pollInterval.current);
        } else if (data.status.includes('failed')) {
          setState(prev => ({ 
            ...prev, 
            status: 'error', 
            error: data.error_message || "Analysis failed",
            progress: 100 
          }));
          if (pollInterval.current) clearInterval(pollInterval.current);
        } else {
          // Still processing
          setState(prev => ({
            ...prev,
            status: 'processing',
            progress: data.progress,
            currentStep: formatStatusMessage(data.status)
          }));
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2000); // Poll every 2 seconds
  }, []);

  return { state, setState, startPolling };
}

// Helper to make status codes user-friendly
function formatStatusMessage(status: string): string {
  switch (status) {
    case 'uploaded': return 'Document Uploaded';
    case 'parsing': return 'Extracting Text & Images...';
    case 'analyzing': return 'Running AI Analysis...';
    case 'pass_1_composition': return 'Classifying Document Type...';
    case 'pass_2_segmenting': return 'Segmenting Content...';
    default: return 'Processing...';
  }
}