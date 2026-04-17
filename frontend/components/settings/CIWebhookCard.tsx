"use client";

/**
 * P5C-06: CIWebhookCard
 * Lets admins generate/rotate the CI webhook secret and see the webhook URL.
 * Displayed in Settings > Integrations alongside Jira and GitHub cards.
 */

import { useState, useEffect } from "react";
import { Copy, RefreshCw, CheckCircle2, Circle } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface CIStatus {
  configured: boolean;
  webhook_url: string | null;
  created_at: string | null;
}

export function CIWebhookCard() {
  const [status, setStatus] = useState<CIStatus | null>(null);
  const [secret, setSecret] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/integrations/ci/status`, { credentials: "include" });
      if (res.ok) setStatus(await res.json());
    } catch {
      // silently ignore
    }
  };

  useEffect(() => { fetchStatus(); }, []);

  const handleSetup = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`${API_BASE_URL}/integrations/ci/setup`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setSecret(data.secret);
        await fetchStatus();
      }
    } finally {
      setGenerating(false);
    }
  };

  const copySecret = () => {
    if (secret) {
      navigator.clipboard.writeText(secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const webhookUrl = status?.webhook_url || `${API_BASE_URL.replace("/api/v1", "")}/api/v1/webhooks/ci/test-results`;

  return (
    <div className="rounded-lg border p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold">CI Pipeline Integration</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Send test results from GitHub Actions / Jenkins to auto-create mismatches on failure.
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          {status?.configured ? (
            <><CheckCircle2 className="h-4 w-4 text-green-500" /><span className="text-green-600">Connected</span></>
          ) : (
            <><Circle className="h-4 w-4 text-muted-foreground" /><span className="text-muted-foreground">Not configured</span></>
          )}
        </div>
      </div>

      {secret && (
        <div className="rounded-md bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-700 p-3 space-y-2">
          <p className="text-xs font-medium text-amber-800 dark:text-amber-300">
            Save this secret now — it won&apos;t be shown again:
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs font-mono bg-white dark:bg-black border border-amber-200 px-2 py-1 rounded truncate">
              {secret}
            </code>
            <button
              onClick={copySecret}
              className="p-1 hover:bg-amber-100 dark:hover:bg-amber-900 rounded"
            >
              {copied ? (
                <CheckCircle2 className="h-4 w-4 text-green-500" />
              ) : (
                <Copy className="h-4 w-4 text-amber-700 dark:text-amber-400" />
              )}
            </button>
          </div>
          <p className="text-xs text-amber-700 dark:text-amber-400">
            Add as <code className="font-mono">DOKYDOC_WEBHOOK_SECRET</code> in your CI environment.
          </p>
        </div>
      )}

      <div className="rounded-md bg-muted/30 border p-3 text-xs space-y-1">
        <p className="font-medium">Webhook URL:</p>
        <code className="text-muted-foreground break-all">{webhookUrl}</code>
      </div>

      <div className="rounded-md bg-muted/30 border p-3">
        <p className="text-xs font-medium mb-2">GitHub Actions example:</p>
        <pre className="text-xs text-muted-foreground overflow-x-auto whitespace-pre-wrap">{`- name: Send results to DokyDoc
  run: |
    PAYLOAD=$(cat test_results.json)
    SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$DOKYDOC_WEBHOOK_SECRET" | cut -d' ' -f2)
    curl -X POST "$DOKYDOC_WEBHOOK_URL" \\
      -H "Content-Type: application/json" \\
      -H "X-DokyDoc-Signature: sha256=$SIG" \\
      -d "$PAYLOAD"`}</pre>
      </div>

      <Button
        onClick={handleSetup}
        disabled={generating}
        variant="outline"
        size="sm"
        className="flex items-center gap-1.5"
      >
        <RefreshCw className={`h-4 w-4 ${generating ? "animate-spin" : ""}`} />
        {status?.configured ? "Rotate Secret" : "Generate Webhook Secret"}
      </Button>
    </div>
  );
}
