"use client";

/**
 * P5C-03: MismatchClarificationPanel
 * Lets BA request clarification from a developer on an ambiguous mismatch.
 * Renders existing Q&A threads and a form to ask a new question.
 */

import { useState } from "react";
import { MessageSquare, Send, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useClarifications } from "@/hooks/useClarifications";
import { API_BASE_URL } from "@/lib/api";

interface TeamMember {
  id: number;
  name: string;
  roles: string[] | null;
}

interface Props {
  mismatchId: number;
  teamMembers: TeamMember[];
}

export function MismatchClarificationPanel({ mismatchId, teamMembers }: Props) {
  const { clarifications, mutate } = useClarifications(mismatchId);
  const [formOpen, setFormOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [assigneeId, setAssigneeId] = useState<number | "">("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openCount = clarifications.filter(c => c.status === "open").length;

  const handleAsk = async () => {
    if (question.trim().length < 10) {
      setError("Question must be at least 10 characters");
      return;
    }
    setSending(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/validation/mismatches/${mismatchId}/clarification`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          assignee_user_id: assigneeId || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      setQuestion("");
      setAssigneeId("");
      setFormOpen(false);
      mutate();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to send");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="border-t pt-3 mt-3">
      <button
        onClick={() => setFormOpen(v => !v)}
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <MessageSquare className="h-4 w-4" />
        <span>Request Clarification</span>
        {openCount > 0 && (
          <span className="ml-1 px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-xs rounded-full">
            {openCount} open
          </span>
        )}
      </button>

      {/* Existing clarification threads */}
      {clarifications.map(c => (
        <div key={c.id} className="mt-2 rounded border border-border p-2.5 text-xs space-y-1.5">
          <div className="flex items-start gap-2">
            <MessageSquare className="h-3.5 w-3.5 text-blue-500 mt-0.5 shrink-0" />
            <div>
              <span className="font-medium">Q: </span>
              <span className="text-muted-foreground">{c.question}</span>
            </div>
          </div>
          {c.answer ? (
            <div className="flex items-start gap-2 pl-4">
              <CheckCircle2 className="h-3.5 w-3.5 text-green-500 mt-0.5 shrink-0" />
              <div>
                <span className="font-medium">A: </span>
                <span className="text-muted-foreground">{c.answer}</span>
              </div>
            </div>
          ) : (
            <p className="pl-4 text-muted-foreground italic">Awaiting developer response…</p>
          )}
          <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${
            c.status === "answered" ? "bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300" :
            c.status === "open" ? "bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300" :
            "bg-muted text-muted-foreground"
          }`}>
            {c.status}
          </span>
        </div>
      ))}

      {/* New question form */}
      {formOpen && (
        <div className="mt-2 space-y-2">
          <select
            value={assigneeId}
            onChange={e => setAssigneeId(e.target.value ? Number(e.target.value) : "")}
            className="w-full text-xs border border-input rounded p-1.5 bg-background"
          >
            <option value="">— Select developer to notify (optional) —</option>
            {teamMembers.map(m => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.roles?.join(", ") || "member"})
              </option>
            ))}
          </select>
          <Textarea
            placeholder="What do you need clarified? (min 10 chars)"
            value={question}
            onChange={e => { setQuestion(e.target.value); setError(null); }}
            rows={3}
            className="text-xs"
          />
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => { setFormOpen(false); setError(null); }}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleAsk} disabled={sending}>
              <Send className="h-3.5 w-3.5 mr-1" />
              {sending ? "Sending…" : "Ask Developer"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
