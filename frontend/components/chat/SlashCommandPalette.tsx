"use client";

import React, { useEffect, useRef, useState } from "react";
import { Zap, Search, BarChart2, Download, Clock, FileText, Code, GitCompare } from "lucide-react";

export interface SlashCommand {
  command: string;
  description: string;
  example: string;
  type: "simple" | "ai";
  icon: React.ElementType;
}

export const SLASH_COMMANDS: SlashCommand[] = [
  { command: "/help", description: "Show all available commands", example: "/help", type: "simple", icon: Zap },
  { command: "/status", description: "System overview: docs, analyses, pending", example: "/status", type: "simple", icon: BarChart2 },
  { command: "/search", description: "Semantic search across your knowledge base", example: '/search "auth flow"', type: "simple", icon: Search },
  { command: "/export", description: "Export the current conversation as JSON", example: "/export", type: "simple", icon: Download },
  { command: "/pending", description: "List your pending approval requests", example: "/pending", type: "simple", icon: Clock },
  { command: "/summarize", description: "Summarize a document by name (AI)", example: "/summarize Requirements.pdf", type: "ai", icon: FileText },
  { command: "/analyze", description: "Analyze a code component by name (AI)", example: "/analyze AuthService", type: "ai", icon: Code },
  { command: "/compare", description: "Compare two documents or components (AI)", example: "/compare v1.pdf vs v2.pdf", type: "ai", icon: GitCompare },
];

interface SlashCommandPaletteProps {
  query: string; // text after '/'
  onSelect: (command: SlashCommand) => void;
  onClose: () => void;
}

export function SlashCommandPalette({ query, onSelect, onClose }: SlashCommandPaletteProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  const filtered = SLASH_COMMANDS.filter((cmd) =>
    cmd.command.slice(1).startsWith(query.toLowerCase()) ||
    cmd.description.toLowerCase().includes(query.toLowerCase())
  );

  // Reset selection when filter changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        onSelect(filtered[selectedIndex]);
      } else if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [filtered, selectedIndex, onSelect, onClose]);

  if (filtered.length === 0) return null;

  return (
    <div
      ref={listRef}
      className="absolute bottom-full left-0 right-0 mb-2 bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden z-50 max-h-72 overflow-y-auto"
    >
      <div className="px-3 py-2 border-b border-gray-100 bg-gray-50">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Commands</span>
      </div>
      {filtered.map((cmd, i) => {
        const Icon = cmd.icon;
        const isSelected = i === selectedIndex;
        return (
          <button
            key={cmd.command}
            className={`w-full flex items-start gap-3 px-3 py-2.5 text-left transition-colors ${
              isSelected ? "bg-purple-50" : "hover:bg-gray-50"
            }`}
            onMouseEnter={() => setSelectedIndex(i)}
            onClick={() => onSelect(cmd)}
          >
            <div
              className={`flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center mt-0.5 ${
                cmd.type === "ai"
                  ? "bg-purple-100 text-purple-600"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-semibold text-gray-800">{cmd.command}</span>
                {cmd.type === "ai" && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-600 font-medium">
                    AI
                  </span>
                )}
              </div>
              <div className="text-xs text-gray-500 truncate">{cmd.description}</div>
              <div className="text-xs text-gray-400 font-mono mt-0.5">{cmd.example}</div>
            </div>
          </button>
        );
      })}
      <div className="px-3 py-1.5 border-t border-gray-100 bg-gray-50">
        <span className="text-[10px] text-gray-400">↑↓ navigate  ↵ select  Esc close</span>
      </div>
    </div>
  );
}
