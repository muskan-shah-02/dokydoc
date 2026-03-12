"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  MessageCircle,
  Plus,
  Send,
  Loader2,
  Trash2,
  ChevronLeft,
  Bot,
  User,
  Sparkles,
  FileText,
  Code,
  Brain,
  FolderKanban,
  Info,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface Conversation {
  id: number;
  title: string;
  context_type: string;
  context_id: number | null;
  message_count: number;
  total_tokens: number;
  total_cost_usd: number;
  created_at: string;
  updated_at: string | null;
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
  created_at: string;
}

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

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Load conversations
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

  // Load messages for a conversation
  const loadMessages = useCallback(async (convId: number) => {
    try {
      const res = await fetch(`${API_BASE}/chat/conversations/${convId}/messages?limit=200`, {
        headers: getHeaders(),
      });
      if (!res.ok) return;
      const data = await res.json();
      setMessages(data.messages || []);
      setTimeout(scrollToBottom, 100);
    } catch (e) {
      console.error("Failed to load messages:", e);
    }
  }, [scrollToBottom]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    if (activeConv) {
      loadMessages(activeConv.id);
    }
  }, [activeConv, loadMessages]);

  // Create new conversation
  const createConversation = async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/conversations`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ title: "New Conversation", context_type: "general" }),
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

  // Delete conversation
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

  // Send message
  const sendMessage = async () => {
    if (!input.trim() || sending) return;

    let conv = activeConv;

    // Auto-create conversation if none active
    if (!conv) {
      try {
        const res = await fetch(`${API_BASE}/chat/conversations`, {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify({ title: "New Conversation", context_type: "general" }),
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

    // Optimistic user message
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
        // Replace optimistic with error
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

      // Replace optimistic message with real ones
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimisticMsg.id),
        data.user_message,
        data.assistant_message,
      ]);

      // Update conversation in sidebar
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
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
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
            <MessageCircle className="h-5 w-5 text-blue-600" />
            Conversations
          </h2>
          <button
            onClick={createConversation}
            className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
            title="New conversation"
          >
            <Plus className="h-5 w-5" />
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center p-8 text-gray-400">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              Loading...
            </div>
          ) : conversations.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">
              No conversations yet. Start a new one!
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = activeConv?.id === conv.id;
              const CtxIcon = CONTEXT_ICONS[conv.context_type] || Brain;
              return (
                <div
                  key={conv.id}
                  className={`group flex items-center px-4 py-3 cursor-pointer border-b border-gray-50 transition-colors ${
                    isActive ? "bg-blue-50 border-l-2 border-l-blue-500" : "hover:bg-gray-50"
                  }`}
                  onClick={() => setActiveConv(conv)}
                >
                  <CtxIcon className={`h-4 w-4 flex-shrink-0 mr-3 ${isActive ? "text-blue-600" : "text-gray-400"}`} />
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate ${isActive ? "text-blue-700" : "text-gray-700"}`}>
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
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-gray-800 truncate">
                {activeConv.title}
              </h3>
              <p className="text-xs text-gray-400">
                {activeConv.message_count} messages &middot; {activeConv.total_tokens.toLocaleString()} tokens
                {activeConv.total_cost_usd > 0 && ` \u00b7 $${activeConv.total_cost_usd.toFixed(4)}`}
              </p>
            </div>
          ) : (
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-gray-800">DokyDoc AI Assistant</h3>
              <p className="text-xs text-gray-400">Ask questions about your documents, code, and knowledge graphs</p>
            </div>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mb-4">
                <Sparkles className="h-8 w-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold text-gray-800 mb-2">DokyDoc AI Assistant</h3>
              <p className="text-gray-500 max-w-md mb-6">
                Ask questions about your documents, code repositories, and business knowledge graphs.
                I use RAG to find relevant context from your knowledge base.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg">
                {[
                  "What are the main business concepts in my knowledge base?",
                  "Summarize the authentication architecture in my code",
                  "What documents mention billing or payment?",
                  "What are the relationships between my top concepts?",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => {
                      setInput(suggestion);
                      inputRef.current?.focus();
                    }}
                    className="text-left text-sm px-4 py-3 rounded-xl border border-gray-200 text-gray-600 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700 transition-colors"
                  >
                    {suggestion}
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
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                      <Bot className="h-4 w-4 text-white" />
                    </div>
                  )}
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                      msg.role === "user"
                        ? "bg-blue-600 text-white"
                        : "bg-white border border-gray-200 text-gray-800"
                    }`}
                  >
                    <div className="text-sm whitespace-pre-wrap break-words leading-relaxed">
                      {msg.content}
                    </div>
                    {msg.role === "assistant" && msg.context_used && (
                      <div className="mt-2 pt-2 border-t border-gray-100 flex items-center gap-3 text-xs text-gray-400">
                        {msg.context_used.concept_count > 0 && (
                          <span className="flex items-center gap-1">
                            <Brain className="h-3 w-3" />
                            {msg.context_used.concept_count} concepts
                          </span>
                        )}
                        {msg.context_used.document_segment_count > 0 && (
                          <span className="flex items-center gap-1">
                            <FileText className="h-3 w-3" />
                            {msg.context_used.document_segment_count} docs
                          </span>
                        )}
                        {msg.context_used.code_summary_count > 0 && (
                          <span className="flex items-center gap-1">
                            <Code className="h-3 w-3" />
                            {msg.context_used.code_summary_count} files
                          </span>
                        )}
                        {msg.model_used && (
                          <span className="ml-auto">{msg.model_used}</span>
                        )}
                      </div>
                    )}
                  </div>
                  {msg.role === "user" && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
                      <User className="h-4 w-4 text-gray-600" />
                    </div>
                  )}
                </div>
              ))}
              {sending && (
                <div className="flex gap-3 justify-start">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-white" />
                  </div>
                  <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3">
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Searching knowledge base and generating response...
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
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about your documents, code, or knowledge graphs..."
                rows={1}
                className="w-full resize-none rounded-xl border border-gray-300 px-4 py-3 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400"
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
              className="flex-shrink-0 p-3 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {sending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
            </button>
          </div>
          <p className="text-center text-xs text-gray-400 mt-2">
            Answers are generated using RAG from your knowledge base. Press Shift+Enter for new line.
          </p>
        </div>
      </div>
    </div>
  );
}
