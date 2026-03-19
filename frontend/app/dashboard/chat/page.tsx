"use client";

import React, { useState, useEffect, useCallback, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { MarkdownRenderer } from "@/components/chat/MarkdownRenderer";
import { SlashCommandPalette, SLASH_COMMANDS, type SlashCommand } from "@/components/chat/SlashCommandPalette";
import { InlineApprovalActions } from "@/components/chat/InlineApprovalActions";
import {
  MessageCircle,
  Plus,
  Send,
  Loader2,
  Trash2,
  Bot,
  User,
  Sparkles,
  FileText,
  Code,
  Brain,
  FolderKanban,
  PanelLeftClose,
  PanelLeftOpen,
  ThumbsUp,
  ThumbsDown,
  Search,
  ChevronDown,
  Zap,
  ExternalLink,
  Download,
  Copy,
  Check,
  BookOpen,
  Settings,
  ArrowRight,
  Shield,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// --- Types ---

interface Conversation {
  id: number;
  title: string;
  context_type: string;
  context_id: number | null;
  model_preference: string;
  message_count: number;
  total_tokens: number;
  total_cost_usd: number;
  created_at: string;
  updated_at: string | null;
}

interface Citation {
  citation_type: string;
  name: string;
  entity_id: number | null;
  entity_type: string | null;
}

interface ChatMessage {
  id: number;
  conversation_id: number;
  role: "user" | "assistant";
  content: string;
  context_used: Record<string, any> | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  model_used: string | null;
  feedback_rating: number | null;
  created_at: string;
}

interface SuggestedPrompt {
  text: string;
  category: string;
}

// --- Helpers ---

function getHeaders() {
  const token = localStorage.getItem("accessToken");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

const CONTEXT_ICONS: Record<string, React.ElementType> = {
  general: Brain,
  document: FileText,
  repository: Code,
  initiative: FolderKanban,
};

const CONTEXT_LABELS: Record<string, string> = {
  general: "General",
  document: "Document",
  repository: "Repository",
  initiative: "Initiative",
};

const MODEL_OPTIONS = [
  { value: "gemini", label: "Gemini 2.5 Flash", subtitle: "Fast", cost: "~$0.001/query" },
  { value: "claude", label: "Claude Sonnet", subtitle: "Deep Reasoning", cost: "~$0.01/query" },
  { value: "auto", label: "Auto", subtitle: "Smart Routing", cost: "varies" },
];

function getCitationUrl(citation: Citation): string | null {
  if (!citation.entity_id) return null;
  switch (citation.citation_type) {
    case "document": return `/dashboard/documents?highlight=${citation.entity_id}`;
    case "code": return `/dashboard/code?highlight=${citation.entity_id}`;
    case "concept": return `/dashboard/ontology?concept=${citation.entity_id}`;
    default: return null;
  }
}

// --- Query Plan Steps ---

const QUERY_STEPS = [
  "Analyzing query...",
  "Searching knowledge base...",
  "Retrieving relevant context...",
  "Synthesizing answer...",
];

// --- Main Component ---

function ChatContent() {
  const searchParams = useSearchParams();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [suggestedPrompts, setSuggestedPrompts] = useState<SuggestedPrompt[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [contextDropdownOpen, setContextDropdownOpen] = useState(false);
  const [queryStep, setQueryStep] = useState(0);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [approvalRefs, setApprovalRefs] = useState<Record<number, any[]>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const modelDropdownRef = useRef<HTMLDivElement>(null);
  const inputAreaRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // --- Data Loading ---

  const loadConversations = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/conversations?limit=50`, { headers: getHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      setConversations(data.conversations || []);
    } catch (e) {
      console.error("Failed to load conversations:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMessages = useCallback(async (convId: number) => {
    try {
      const res = await fetch(`${API_BASE}/chat/conversations/${convId}/messages?limit=200`, {
        headers: getHeaders(),
      });
      if (!res.ok) return;
      const data = await res.json();
      // Deduplicate by id in case of concurrent updates
      const seen = new Set<number>();
      const unique = (data.messages || []).filter((m: ChatMessage) => {
        if (seen.has(m.id)) return false;
        seen.add(m.id);
        return true;
      });
      setMessages(unique);
      setTimeout(scrollToBottom, 100);
    } catch (e) {
      console.error("Failed to load messages:", e);
    }
  }, [scrollToBottom]);

  const loadSuggestedPrompts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/suggested-prompts`, { headers: getHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      setSuggestedPrompts(data.prompts || []);
    } catch (e) {
      console.error("Failed to load suggested prompts:", e);
    }
  }, []);

  const searchConversations = useCallback(async (q: string) => {
    if (!q.trim()) {
      loadConversations();
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE}/chat/conversations/search?q=${encodeURIComponent(q)}&limit=20`,
        { headers: getHeaders() }
      );
      if (!res.ok) return;
      const data = await res.json();
      setConversations(data.conversations || []);
    } catch (e) {
      console.error("Failed to search conversations:", e);
    }
  }, [loadConversations]);

  useEffect(() => {
    loadConversations();
    loadSuggestedPrompts();
  }, [loadConversations, loadSuggestedPrompts]);

  useEffect(() => {
    if (activeConv) loadMessages(activeConv.id);
  }, [activeConv, loadMessages]);

  // Handle URL params for contextual entry (e.g., /chat?doc=123)
  useEffect(() => {
    const docId = searchParams.get("doc");
    const repoId = searchParams.get("repo");
    const conceptId = searchParams.get("concept");

    if (docId || repoId || conceptId) {
      const contextType = docId ? "document" : repoId ? "repository" : "initiative";
      const contextId = parseInt(docId || repoId || conceptId || "0");
      createConversation(contextType, contextId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Actions ---

  const createConversation = async (contextType: string = "general", contextId?: number) => {
    try {
      const res = await fetch(`${API_BASE}/chat/conversations`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          title: "New Conversation",
          context_type: contextType,
          context_id: contextId || null,
          model_preference: "auto",
        }),
      });
      if (!res.ok) return;
      const conv = await res.json();
      setConversations((prev) => [conv, ...prev]);
      setActiveConv(conv);
      setMessages([]);
      inputRef.current?.focus();
    } catch (e) {
      console.error("Failed to create conversation:", e);
    }
  };

  const deleteConversation = async (convId: number) => {
    try {
      await fetch(`${API_BASE}/chat/conversations/${convId}`, {
        method: "DELETE",
        headers: getHeaders(),
      });
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConv?.id === convId) {
        setActiveConv(null);
        setMessages([]);
      }
    } catch (e) {
      console.error("Failed to delete conversation:", e);
    }
  };

  const updateModelPreference = async (model: string) => {
    if (!activeConv) return;
    try {
      const res = await fetch(`${API_BASE}/chat/conversations/${activeConv.id}/model`, {
        method: "PUT",
        headers: getHeaders(),
        body: JSON.stringify({ model_preference: model }),
      });
      if (!res.ok) return;
      const updated = await res.json();
      setActiveConv(updated);
      setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    } catch (e) {
      console.error("Failed to update model:", e);
    }
    setModelDropdownOpen(false);
  };

  const submitFeedback = async (messageId: number, rating: number) => {
    try {
      await fetch(`${API_BASE}/chat/messages/${messageId}/feedback?rating=${rating}`, {
        method: "POST",
        headers: getHeaders(),
      });
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, feedback_rating: rating } : m))
      );
    } catch (e) {
      console.error("Failed to submit feedback:", e);
    }
  };

  const exportConversation = async (convId: number) => {
    try {
      const res = await fetch(`${API_BASE}/chat/conversations/${convId}/export?format=json`, {
        headers: getHeaders(),
      });
      if (!res.ok) return;
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `conversation-${convId}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Failed to export:", e);
    }
  };

  const copyMessage = async (content: string, msgId: number) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedId(msgId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (e) {
      console.error("Failed to copy:", e);
    }
  };

  // Query plan animation during sending
  useEffect(() => {
    if (!sending) {
      setQueryStep(0);
      return;
    }
    let step = 0;
    setQueryStep(0);
    const interval = setInterval(() => {
      step++;
      if (step < QUERY_STEPS.length) {
        setQueryStep(step);
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [sending]);

  const sendMessage = async () => {
    if (!input.trim() || sending) return;

    let conv = activeConv;

    if (!conv) {
      try {
        const res = await fetch(`${API_BASE}/chat/conversations`, {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify({
            title: "New Conversation",
            context_type: "general",
            model_preference: "auto",
          }),
        });
        if (!res.ok) return;
        conv = await res.json();
        setConversations((prev) => [conv!, ...prev]);
        setActiveConv(conv);
      } catch (e) {
        console.error("Failed to auto-create conversation:", e);
        return;
      }
    }

    const userContent = input.trim();
    setInput("");
    setSending(true);

    const optimisticMsg: ChatMessage = {
      id: Date.now(),
      conversation_id: conv!.id,
      role: "user",
      content: userContent,
      context_used: null,
      input_tokens: 0,
      output_tokens: 0,
      cost_usd: 0,
      model_used: null,
      feedback_rating: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticMsg]);
    setTimeout(scrollToBottom, 50);

    try {
      const res = await fetch(`${API_BASE}/chat/conversations/${conv!.id}/messages`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ content: userContent }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed to send message" }));
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== optimisticMsg.id),
          optimisticMsg,
          {
            ...optimisticMsg,
            id: Date.now() + 1,
            role: "assistant",
            content: `Error: ${err.detail || "Something went wrong. Please try again."}`,
          },
        ]);
        return;
      }

      const data = await res.json();

      // Merge real messages, deduplicating by ID to prevent duplicate-key React errors
      // (race condition: loadMessages may have already added these while AI was thinking)
      setMessages((prev) => {
        const incoming = [data.user_message, data.assistant_message];
        const incomingIds = new Set(incoming.map((m: ChatMessage) => m.id));
        const filtered = prev.filter(
          (m) => m.id !== optimisticMsg.id && !incomingIds.has(m.id)
        );
        return [...filtered, ...incoming];
      });

      // Store approval references for this assistant message
      if (data.approval_references && data.approval_references.length > 0) {
        setApprovalRefs((prev) => ({
          ...prev,
          [data.assistant_message.id]: data.approval_references,
        }));
      }

      setConversations((prev) =>
        prev.map((c) =>
          c.id === conv!.id
            ? {
                ...c,
                title: data.user_message.content.slice(0, 80) || c.title,
                message_count: c.message_count + 2,
                updated_at: new Date().toISOString(),
              }
            : c
        )
      );

      setTimeout(scrollToBottom, 100);
    } catch (e) {
      console.error("Failed to send message:", e);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showCommandPalette && (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Escape")) {
      return; // Let palette handle these
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!showCommandPalette) sendMessage();
    }
  };

  const handleInputChange = (value: string) => {
    setInput(value);
    if (value.startsWith("/") && !value.includes(" ")) {
      setCommandQuery(value.slice(1));
      setShowCommandPalette(true);
    } else {
      setShowCommandPalette(false);
      setCommandQuery("");
    }
  };

  const handleCommandSelect = async (cmd: SlashCommand) => {
    setShowCommandPalette(false);
    // Fill example into input for AI commands, or execute simple commands directly
    if (cmd.type === "ai") {
      setInput(cmd.command + " ");
      setCommandQuery("");
      inputRef.current?.focus();
      return;
    }
    // Simple commands: execute immediately
    setInput("");
    setCommandQuery("");
    if (!activeConv) {
      // Create a conversation first
      try {
        const res = await fetch(`${API_BASE}/chat/conversations`, {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify({ title: cmd.command, context_type: "general", model_preference: "auto" }),
        });
        if (!res.ok) return;
        const conv = await res.json();
        setConversations((prev) => [conv, ...prev]);
        setActiveConv(conv);
        await executeSlashCommand(cmd.command, "", conv.id);
      } catch (e) {
        console.error("Failed to create conversation:", e);
      }
      return;
    }
    await executeSlashCommand(cmd.command, "", activeConv.id);
  };

  const executeSlashCommand = async (command: string, args: string, convId: number) => {
    setSending(true);
    const optimisticUser: ChatMessage = {
      id: Date.now(),
      conversation_id: convId,
      role: "user",
      content: args ? `${command} ${args}` : command,
      context_used: null,
      input_tokens: 0,
      output_tokens: 0,
      cost_usd: 0,
      model_used: null,
      feedback_rating: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUser]);
    setTimeout(scrollToBottom, 50);
    try {
      const res = await fetch(`${API_BASE}/chat/conversations/${convId}/command`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ command, args }),
      });
      if (!res.ok) throw new Error("Command failed");
      const data = await res.json();
      const assistantMsg: ChatMessage = {
        id: Date.now() + 1,
        conversation_id: convId,
        role: "assistant",
        content: data.content,
        context_used: null,
        input_tokens: 0,
        output_tokens: 0,
        cost_usd: 0,
        model_used: "command",
        feedback_rating: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setTimeout(scrollToBottom, 100);
    } catch (e) {
      console.error("Command execution failed:", e);
    } finally {
      setSending(false);
    }
  };

  const formatTime = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return d.toLocaleDateString([], { weekday: "short" });
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  };

  const filteredConversations = searchQuery.trim()
    ? conversations
    : conversations;

  const currentModel = MODEL_OPTIONS.find((m) => m.value === (activeConv?.model_preference || "auto"));

  // Close model dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(e.target as Node)) {
        setModelDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="flex h-[calc(100vh-4rem)] bg-gray-50">
      {/* Conversation Sidebar */}
      <div
        className={`flex flex-col border-r border-gray-200 bg-white transition-all duration-300 ${
          sidebarOpen ? "w-80" : "w-0 overflow-hidden"
        }`}
      >
        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-purple-600" />
            AskyDoc
          </h2>
          <button
            onClick={() => createConversation()}
            className="p-2 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
            title="New conversation"
          >
            <Plus className="h-5 w-5" />
          </button>
        </div>

        {/* Conversation Search */}
        <div className="px-3 py-2 border-b border-gray-100">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                searchConversations(e.target.value);
              }}
              className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent placeholder-gray-400"
            />
          </div>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center p-8 text-gray-400">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              Loading...
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">
              {searchQuery ? "No matching conversations." : "No conversations yet. Start a new one!"}
            </div>
          ) : (
            filteredConversations.map((conv) => {
              const isActive = activeConv?.id === conv.id;
              const CtxIcon = CONTEXT_ICONS[conv.context_type] || Brain;
              return (
                <div
                  key={conv.id}
                  className={`group flex items-center px-4 py-3 cursor-pointer border-b border-gray-50 transition-colors ${
                    isActive ? "bg-purple-50 border-l-2 border-l-purple-500" : "hover:bg-gray-50"
                  }`}
                  onClick={() => setActiveConv(conv)}
                >
                  <CtxIcon className={`h-4 w-4 flex-shrink-0 mr-3 ${isActive ? "text-purple-600" : "text-gray-400"}`} />
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate ${isActive ? "text-purple-700" : "text-gray-700"}`}>
                      {conv.title || "New Conversation"}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {conv.message_count} msgs &middot; {formatTime(conv.updated_at || conv.created_at)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteConversation(conv.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 rounded transition-all"
                    title="Delete"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Chat Header */}
        <div className="flex items-center px-4 py-3 border-b border-gray-200 bg-white">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg mr-2 transition-colors"
          >
            {sidebarOpen ? <PanelLeftClose className="h-5 w-5" /> : <PanelLeftOpen className="h-5 w-5" />}
          </button>

          {activeConv ? (
            <>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-gray-800 truncate">
                    {activeConv.title}
                  </h3>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                    {CONTEXT_LABELS[activeConv.context_type] || "General"}
                  </span>
                </div>
                <p className="text-xs text-gray-400">
                  {activeConv.message_count} messages &middot; {activeConv.total_tokens.toLocaleString()} tokens
                  {activeConv.total_cost_usd > 0 && ` \u00b7 $${activeConv.total_cost_usd.toFixed(4)}`}
                </p>
              </div>

              {/* Model Selector Dropdown */}
              <div className="relative ml-3" ref={modelDropdownRef}>
                <button
                  onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors"
                >
                  <Zap className="h-3.5 w-3.5 text-purple-500" />
                  <span className="font-medium">{currentModel?.label || "Auto"}</span>
                  <ChevronDown className={`h-3 w-3 text-gray-400 transition-transform ${modelDropdownOpen ? "rotate-180" : ""}`} />
                </button>

                {modelDropdownOpen && (
                  <div className="absolute right-0 top-full mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
                    <div className="p-2 border-b border-gray-100">
                      <p className="text-xs font-semibold text-gray-500 px-2">AI Model</p>
                    </div>
                    {MODEL_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => updateModelPreference(opt.value)}
                        className={`w-full flex items-center justify-between px-3 py-2.5 text-sm hover:bg-gray-50 transition-colors ${
                          activeConv.model_preference === opt.value ? "bg-purple-50" : ""
                        }`}
                      >
                        <div>
                          <p className={`font-medium ${activeConv.model_preference === opt.value ? "text-purple-700" : "text-gray-700"}`}>
                            {opt.label}
                          </p>
                          <p className="text-xs text-gray-400">{opt.subtitle}</p>
                        </div>
                        <span className="text-xs text-gray-400">{opt.cost}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Context Type Selector */}
              <div className="relative ml-2">
                <button
                  onClick={() => setContextDropdownOpen(!contextDropdownOpen)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors"
                >
                  {React.createElement(CONTEXT_ICONS[activeConv.context_type] || Brain, { className: "h-3.5 w-3.5 text-gray-500" })}
                  <span className="font-medium">{CONTEXT_LABELS[activeConv.context_type]}</span>
                </button>

                {contextDropdownOpen && (
                  <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
                    {Object.entries(CONTEXT_LABELS).map(([key, label]) => {
                      const Icon = CONTEXT_ICONS[key] || Brain;
                      return (
                        <button
                          key={key}
                          onClick={() => setContextDropdownOpen(false)}
                          className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50 ${
                            activeConv.context_type === key ? "bg-purple-50 text-purple-700" : "text-gray-700"
                          }`}
                        >
                          <Icon className="h-4 w-4" />
                          {label}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Export */}
              <button
                onClick={() => exportConversation(activeConv.id)}
                className="ml-2 p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                title="Export conversation"
              >
                <Download className="h-4 w-4" />
              </button>
            </>
          ) : (
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-purple-500" />
                AskyDoc
              </h3>
              <p className="text-xs text-gray-400">Ask questions about your documents, code, and knowledge graphs</p>
            </div>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center max-w-2xl mx-auto">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center mb-4">
                <Sparkles className="h-8 w-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold text-gray-800 mb-2">AskyDoc</h3>
              <p className="text-gray-500 max-w-md mb-6">
                Your AI assistant for documents, code repositories, and business knowledge graphs.
                Powered by RAG with role-aware intelligence.
              </p>

              {/* First-time onboarding card (shown when user has no conversations) */}
              {conversations.length === 0 && !loading && (
                <div className="w-full mb-6 rounded-xl border border-purple-200 bg-gradient-to-r from-purple-50 to-blue-50 p-5 text-left">
                  <div className="flex items-start gap-3 mb-4">
                    <BookOpen className="h-5 w-5 text-purple-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <h4 className="text-sm font-semibold text-gray-800">Welcome to AskyDoc!</h4>
                      <p className="text-xs text-gray-500 mt-1">
                        AskyDoc searches your knowledge base — documents, code, and business concepts — to give you
                        contextual, role-aware answers. Here&apos;s what you can do:
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                    <div className="flex items-start gap-2 text-left">
                      <FileText className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-xs font-medium text-gray-700">Ask about documents</p>
                        <p className="text-xs text-gray-400">PRDs, specs, requirements</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2 text-left">
                      <Code className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-xs font-medium text-gray-700">Ask about code</p>
                        <p className="text-xs text-gray-400">Architecture, components, patterns</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2 text-left">
                      <Brain className="h-4 w-4 text-purple-500 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-xs font-medium text-gray-700">Ask about concepts</p>
                        <p className="text-xs text-gray-400">Business ontology, relationships</p>
                      </div>
                    </div>
                  </div>

                  {/* Org profile prompt for CXO/Admin */}
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-white/60 border border-purple-100">
                    <Shield className="h-4 w-4 text-purple-500 flex-shrink-0" />
                    <p className="text-xs text-gray-600 flex-1">
                      <span className="font-medium">CXO/Admin?</span> Set up your{" "}
                      <a href="/settings/organization" className="text-purple-600 hover:text-purple-700 underline">
                        org profile
                      </a>{" "}
                      for better, context-aware answers tailored to your organization.
                    </p>
                    <a
                      href="/settings/organization"
                      className="flex items-center gap-1 text-xs font-medium text-purple-600 hover:text-purple-700 whitespace-nowrap"
                    >
                      Set up <ArrowRight className="h-3 w-3" />
                    </a>
                  </div>
                </div>
              )}

              {/* Suggested prompts */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
                {(suggestedPrompts.length > 0
                  ? suggestedPrompts.slice(0, 4)
                  : [
                      { text: "What are the main business concepts in my knowledge base?", category: "general" },
                      { text: "Summarize the authentication architecture in my code", category: "technical" },
                      { text: "What documents mention billing or payment?", category: "document" },
                      { text: "What are the relationships between my top concepts?", category: "ontology" },
                    ]
                ).map((prompt, index) => (
                  <button
                    key={`prompt-${index}-${prompt.text}`}
                    onClick={() => {
                      setInput(prompt.text);
                      inputRef.current?.focus();
                    }}
                    className="text-left text-sm px-4 py-3 rounded-xl border border-gray-200 text-gray-600 hover:bg-purple-50 hover:border-purple-200 hover:text-purple-700 transition-colors"
                  >
                    {prompt.text}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-6">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {msg.role === "assistant" && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center">
                      <Bot className="h-4 w-4 text-white" />
                    </div>
                  )}
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                      msg.role === "user"
                        ? "bg-purple-600 text-white"
                        : "bg-white border border-gray-200 text-gray-800"
                    }`}
                  >
                    {msg.role === "assistant" ? (
                      <MarkdownRenderer content={msg.content} />
                    ) : (
                      <div className="text-sm whitespace-pre-wrap break-words leading-relaxed">
                        {msg.content}
                      </div>
                    )}

                    {/* Source Citations */}
                    {msg.role === "assistant" && msg.context_used && (
                      <div className="mt-2 pt-2 border-t border-gray-100">
                        <div className="flex flex-wrap items-center gap-2 text-xs text-gray-400">
                          {msg.context_used.concept_count > 0 && (
                            <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-purple-50 text-purple-600">
                              <Brain className="h-3 w-3" />
                              {msg.context_used.concept_count} concepts
                            </span>
                          )}
                          {msg.context_used.document_segment_count > 0 && (
                            <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-blue-50 text-blue-600">
                              <FileText className="h-3 w-3" />
                              {msg.context_used.document_segment_count} docs
                            </span>
                          )}
                          {msg.context_used.code_summary_count > 0 && (
                            <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-green-50 text-green-600">
                              <Code className="h-3 w-3" />
                              {msg.context_used.code_summary_count} files
                            </span>
                          )}
                          {/* Clickable citation chips */}
                          {msg.context_used.citations?.map((c: Citation, i: number) => {
                            const url = getCitationUrl(c);
                            return url ? (
                              <a
                                key={`${c.citation_type}-${c.entity_id ?? i}-${c.name}`}
                                href={url}
                                className="flex items-center gap-1 px-2 py-1 rounded-full bg-gray-100 text-gray-600 hover:bg-purple-100 hover:text-purple-700 transition-colors"
                              >
                                <ExternalLink className="h-3 w-3" />
                                {c.name}
                              </a>
                            ) : null;
                          })}
                        </div>

                        {/* Model + cost info */}
                        <div className="flex items-center justify-between mt-2 text-xs text-gray-400">
                          {msg.model_used && (
                            <span className="flex items-center gap-1">
                              <Zap className="h-3 w-3" />
                              {msg.model_used}
                            </span>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Feedback + Copy buttons for assistant messages */}
                    {msg.role === "assistant" && (
                      <div className="flex items-center gap-1 mt-2 pt-1">
                        <button
                          onClick={() => submitFeedback(msg.id, msg.feedback_rating === 1 ? 0 : 1)}
                          className={`p-1.5 rounded-lg transition-colors ${
                            msg.feedback_rating === 1
                              ? "text-green-600 bg-green-50"
                              : "text-gray-300 hover:text-green-500 hover:bg-green-50"
                          }`}
                          title="Helpful"
                        >
                          <ThumbsUp className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => submitFeedback(msg.id, msg.feedback_rating === -1 ? 0 : -1)}
                          className={`p-1.5 rounded-lg transition-colors ${
                            msg.feedback_rating === -1
                              ? "text-red-600 bg-red-50"
                              : "text-gray-300 hover:text-red-500 hover:bg-red-50"
                          }`}
                          title="Not helpful"
                        >
                          <ThumbsDown className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => copyMessage(msg.content, msg.id)}
                          className="p-1.5 rounded-lg text-gray-300 hover:text-gray-500 hover:bg-gray-100 transition-colors ml-1"
                          title="Copy"
                        >
                          {copiedId === msg.id ? (
                            <Check className="h-3.5 w-3.5 text-green-500" />
                          ) : (
                            <Copy className="h-3.5 w-3.5" />
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                  {/* Inline Approval Actions — shown below assistant message bubble */}
                  {msg.role === "assistant" && approvalRefs[msg.id] && (
                    <InlineApprovalActions approvals={approvalRefs[msg.id]} />
                  )}

                  {msg.role === "user" && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
                      <User className="h-4 w-4 text-gray-600" />
                    </div>
                  )}
                </div>
              ))}

              {/* Query Plan Animation */}
              {sending && (
                <div className="flex gap-3 justify-start">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-white" />
                  </div>
                  <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3">
                    <div className="space-y-2">
                      {QUERY_STEPS.map((step, i) => (
                        <div
                          key={step}
                          className={`flex items-center gap-2 text-sm transition-all duration-300 ${
                            i < queryStep
                              ? "text-green-600"
                              : i === queryStep
                              ? "text-purple-600"
                              : "text-gray-300"
                          }`}
                        >
                          {i < queryStep ? (
                            <Check className="h-3.5 w-3.5" />
                          ) : i === queryStep ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <div className="h-3.5 w-3.5" />
                          )}
                          {step}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-200 bg-white p-4">
          <div className="max-w-3xl mx-auto flex items-end gap-3">
            <div className="flex-1 relative" ref={inputAreaRef}>
              {showCommandPalette && (
                <SlashCommandPalette
                  query={commandQuery}
                  onSelect={handleCommandSelect}
                  onClose={() => setShowCommandPalette(false)}
                />
              )}
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => handleInputChange(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask AskyDoc… or type / for commands"
                rows={1}
                className="w-full resize-none rounded-xl border border-gray-300 px-4 py-3 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent placeholder-gray-400"
                style={{ maxHeight: "120px", minHeight: "44px" }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = "auto";
                  target.style.height = Math.min(target.scrollHeight, 120) + "px";
                }}
                disabled={sending}
              />
            </div>
            <button
              onClick={sendMessage}
              disabled={!input.trim() || sending}
              className="flex-shrink-0 p-3 rounded-xl bg-purple-600 text-white hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {sending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
            </button>
          </div>
          <p className="text-center text-xs text-gray-400 mt-2">
            AskyDoc uses RAG from your knowledge base. Press Shift+Enter for new line.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return <Suspense fallback={<div className="flex h-screen items-center justify-center"><div className="animate-spin h-8 w-8 border-2 border-purple-600 rounded-full border-t-transparent" /></div>}><ChatContent /></Suspense>;
}
