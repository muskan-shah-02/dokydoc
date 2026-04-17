"use client";

/**
 * P5C-02: RequestUploadModal
 * Lets the BA notify tech leads/developers to upload specific code files.
 */

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { useTeamMembers } from "@/hooks/useTeamMembers";
import { API_BASE_URL } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  documentId: number;
  suggestedFilenames: string[];
}

export function RequestUploadModal({ open, onClose, documentId, suggestedFilenames }: Props) {
  const { teamMembers, isLoading } = useTeamMembers(open ? documentId : null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  // Pre-select tech leads when members load
  useEffect(() => {
    if (teamMembers.length > 0) {
      const techLeadIds = teamMembers
        .filter(m => m.roles?.includes("tech_lead"))
        .map(m => m.id);
      setSelectedIds(new Set(techLeadIds));
    }
  }, [teamMembers]);

  const toggle = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleSend = async () => {
    if (selectedIds.size === 0) return;
    setSending(true);
    try {
      const res = await fetch(`${API_BASE_URL}/documents/${documentId}/request-uploads`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_ids: Array.from(selectedIds),
          message,
          suggested_filenames: suggestedFilenames,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSent(true);
      setTimeout(() => { setSent(false); onClose(); }, 1500);
    } catch {
      // swallow — user can retry
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Request Code Upload</DialogTitle>
        </DialogHeader>

        {suggestedFilenames.length > 0 && (
          <div className="rounded-md bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-700 p-3 text-xs">
            <p className="font-medium text-amber-800 dark:text-amber-300 mb-1">Files needed:</p>
            {suggestedFilenames.map(f => (
              <code key={f} className="block text-amber-700 dark:text-amber-400">{f}</code>
            ))}
          </div>
        )}

        <div className="space-y-1 max-h-52 overflow-y-auto">
          <p className="text-xs font-medium text-muted-foreground mb-2">Select recipients:</p>
          {isLoading && <p className="text-xs text-muted-foreground">Loading team…</p>}
          {teamMembers.map(member => (
            <label key={member.id} className="flex items-center gap-2 cursor-pointer py-1 hover:bg-muted/50 rounded px-1">
              <Checkbox
                checked={selectedIds.has(member.id)}
                onCheckedChange={() => toggle(member.id)}
              />
              <span className="text-sm flex-1">{member.name}</span>
              <span className="text-xs text-muted-foreground">
                {member.roles?.join(", ") || "member"}
              </span>
            </label>
          ))}
        </div>

        <Textarea
          placeholder="Optional: add a note for your team…"
          value={message}
          onChange={e => setMessage(e.target.value)}
          rows={2}
          className="text-sm"
        />

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} size="sm">Cancel</Button>
          <Button
            onClick={handleSend}
            disabled={selectedIds.size === 0 || sending || sent}
            size="sm"
          >
            {sent ? "Sent!" : sending ? "Sending…" : `Send to ${selectedIds.size} member(s)`}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
