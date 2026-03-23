"use client";

import React, { useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import {
  Zap,
  BookOpen,
  HelpCircle,
  Sparkles,
  FileText,
  Code,
  GitBranch,
  Key,
  Link2,
  BarChart2,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Search,
  Clock,
  Download,
  CheckSquare,
  GitCompare,
  MessageSquare,
} from "lucide-react";

// --- Slash Commands ---
const COMMANDS = [
  { command: "/help", description: "Show all available commands", example: "/help", type: "simple" },
  { command: "/status", description: "System overview: docs, analyses, pending items", example: "/status", type: "simple" },
  { command: "/search", description: "Semantic search across your knowledge base", example: '/search "auth flow"', type: "simple" },
  { command: "/export", description: "Export the current conversation as JSON", example: "/export", type: "simple" },
  { command: "/pending", description: "List your pending approval requests", example: "/pending", type: "simple" },
  { command: "/summarize", description: "Summarize a document by name (AI — uses credits)", example: "/summarize Requirements.pdf", type: "ai" },
  { command: "/analyze", description: "Analyze a code component by name (AI — uses credits)", example: "/analyze AuthService", type: "ai" },
  { command: "/compare", description: "Compare two documents or components (AI — uses credits)", example: "/compare v1.pdf vs v2.pdf", type: "ai" },
];

// --- Getting Started Steps ---
const STEPS = [
  { icon: FileText, title: "Upload your first document", desc: "Go to Documents → Upload. Supports PDF, DOCX, TXT, MD. Analysis runs automatically." },
  { icon: Code, title: "Connect a code repository", desc: "Go to Code → Add Repository. Paste your GitHub/GitLab URL or upload a ZIP." },
  { icon: BarChart2, title: "Run your first analysis", desc: "After uploading, analysis starts automatically. Watch the status badge change to 'Complete'." },
  { icon: Sparkles, title: "Ask AskyDoc a question", desc: 'Open AskyDoc in the sidebar. Try asking "What are the main requirements?" or type / for commands.' },
  { icon: BookOpen, title: "Generate your first BRD", desc: "Go to Auto Docs → BRD Generator. Link a project with documents and code, then click Generate." },
  { icon: Link2, title: "Connect an external integration", desc: "Go to Integrations. Connect Notion, Jira, Confluence, or SharePoint to sync docs automatically." },
];

// --- Feature Cards ---
const FEATURES = [
  { icon: FileText, title: "Documents", desc: "Upload, tag, version, and analyze documentation. Track changes over time with diff view.", href: "/dashboard/documents", color: "blue" },
  { icon: Code, title: "Code", desc: "Sync repositories, compare code versions, and get AI analysis of your components.", href: "/dashboard/code", color: "green" },
  { icon: Sparkles, title: "AskyDoc", desc: "Conversational AI over your entire knowledge base. Slash commands for power users.", href: "/dashboard/chat", color: "purple" },
  { icon: BookOpen, title: "Auto Docs", desc: "AI-generated BRDs, architecture diagrams, API summaries, and test cases.", href: "/dashboard/auto-docs", color: "amber" },
  { icon: Link2, title: "Integrations", desc: "Connect Notion, Jira, Confluence, and SharePoint to sync docs automatically.", href: "/dashboard/integrations", color: "rose" },
  { icon: Key, title: "API Keys", desc: "Create API keys for CI/CD pipelines and external integrations with scope control.", href: "/settings", color: "gray" },
  { icon: GitBranch, title: "Visual Architecture", desc: "5-level knowledge graph: organization → system → domain → file. Drill-down exploration.", href: "/dashboard/brain", color: "indigo" },
  { icon: CheckSquare, title: "Validation Panel", desc: "Detect mismatches between docs and code. Approval workflows with multi-level review.", href: "/dashboard/validation-panel", color: "teal" },
];

// --- FAQ ---
const FAQ_ITEMS = [
  {
    q: "How does document analysis work?",
    a: "When you upload a document, DokuDoc extracts text, runs AI analysis to identify requirements, business rules, actors, and data models, then builds an ontology graph. The process takes 30 seconds to a few minutes depending on document size.",
  },
  {
    q: "What file types are supported?",
    a: "PDF, DOCX, DOC, TXT, and MD (Markdown). For code repositories: any GitHub or GitLab URL, or a ZIP file containing your source code.",
  },
  {
    q: "How are costs calculated?",
    a: "Each AI operation (document analysis, chat message, BRD generation) uses AI credits. You can see cost estimates before expensive operations. Top up credits in Settings → Billing.",
  },
  {
    q: "How do I give a teammate access?",
    a: "Go to Settings → User Management (Admin/CXO only). Click 'Invite User', enter their email, and assign a role: Developer, BA, QA, CXO, or Admin.",
  },
  {
    q: "What's the difference between a Project and a Repository?",
    a: "A Repository is a single codebase (e.g., GitHub repo). A Project (Initiative) is a higher-level grouping that links multiple repositories and documents together for cross-cutting analysis like BRD generation.",
  },
  {
    q: "How do I use slash commands in AskyDoc?",
    a: "Open AskyDoc and type / at the start of the input. A command palette appears showing all available commands. Use arrow keys to navigate, Enter to select. Simple commands (/help, /status) execute instantly without using AI credits.",
  },
  {
    q: "Why did my analysis fail?",
    a: "Common causes: (1) Insufficient credits — check Settings → Billing. (2) File too large — max 50MB. (3) Password-protected PDF — upload an unprotected version. (4) Empty or corrupted file. Check the error message in the document status badge for specifics.",
  },
  {
    q: "What is the Brain / Knowledge Graph?",
    a: "The Brain is a 5-level visual knowledge graph: L5 (Organization) → L4 (Project) → L3 (System) → L2 (Domain) → L1 (File). It shows how your documents, code, and concepts relate to each other. Navigate it at Dashboard → Brain.",
  },
];

const colorMap: Record<string, string> = {
  blue: "bg-blue-100 text-blue-600",
  green: "bg-green-100 text-green-600",
  purple: "bg-purple-100 text-purple-600",
  amber: "bg-amber-100 text-amber-600",
  rose: "bg-rose-100 text-rose-600",
  gray: "bg-gray-100 text-gray-600",
  indigo: "bg-indigo-100 text-indigo-600",
  teal: "bg-teal-100 text-teal-600",
};

type TabId = "commands" | "getting-started" | "features" | "faq" | "changelog" | "support";

const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: "commands", label: "Slash Commands", icon: Zap },
  { id: "getting-started", label: "Getting Started", icon: CheckSquare },
  { id: "features", label: "Features", icon: BookOpen },
  { id: "faq", label: "FAQ", icon: HelpCircle },
  { id: "changelog", label: "What's New", icon: Clock },
  { id: "support", label: "Support", icon: MessageSquare },
];

const CHANGELOG = [
  { version: "v1.7", date: "Mar 2026", items: ["AskyDoc slash commands (/help, /status, /search, /summarize, /analyze, /compare, /pending, /export)", "ChatGPT-style rich markdown rendering for AI responses", "Help & Docs module with command reference, FAQ, and onboarding guide"] },
  { version: "v1.6", date: "Mar 2026", items: ["Document version comparison with side-by-side diff viewer", "Upload New Version button on document detail page", "In-app notification preferences (control which alerts you receive)"] },
  { version: "v1.5", date: "Feb 2026", items: ["Security/Audit Dashboard with activity charts and anomaly detection", "AskyDoc in-dock approve/reject buttons for pending approvals", "Compliance report export (JSON format)"] },
  { version: "v1.4", date: "Feb 2026", items: ["Export module (JSON, CSV, PDF)", "Sync Timeline viewer", "Approval workflow with multi-level review (L1/L2/L3)"] },
];

function CommandsTab() {
  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-600">
        Type <code className="bg-gray-100 text-purple-700 px-1.5 py-0.5 rounded font-mono text-xs">/</code> in the AskyDoc input to open the command palette. Use <kbd className="text-xs bg-gray-100 border border-gray-300 px-1.5 py-0.5 rounded">↑↓</kbd> to navigate, <kbd className="text-xs bg-gray-100 border border-gray-300 px-1.5 py-0.5 rounded">↵</kbd> to select.
      </p>
      <div className="overflow-hidden rounded-xl border border-gray-200">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-3 font-semibold text-gray-700 w-36">Command</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-700">Description</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-700 w-52">Example</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-700 w-20">Type</th>
            </tr>
          </thead>
          <tbody>
            {COMMANDS.map((cmd, i) => (
              <tr key={cmd.command} className={i % 2 === 0 ? "bg-white" : "bg-gray-50/50"}>
                <td className="px-4 py-3">
                  <code className="font-mono font-semibold text-purple-700">{cmd.command}</code>
                </td>
                <td className="px-4 py-3 text-gray-600">{cmd.description}</td>
                <td className="px-4 py-3">
                  <code className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded font-mono">{cmd.example}</code>
                </td>
                <td className="px-4 py-3">
                  {cmd.type === "ai" ? (
                    <span className="text-xs px-2 py-1 rounded-full bg-purple-100 text-purple-700 font-medium">AI</span>
                  ) : (
                    <span className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-600 font-medium">Simple</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800">
        <strong>Tip:</strong> Simple commands execute instantly without using AI credits. AI commands (/summarize, /analyze, /compare) run through the full RAG pipeline and consume credits.
      </div>
    </div>
  );
}

function GettingStartedTab() {
  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-600">Complete these steps to get the most out of DokuDoc.</p>
      <div className="space-y-3">
        {STEPS.map((step, i) => {
          const Icon = step.icon;
          return (
            <div key={i} className="flex gap-4 p-4 rounded-xl border border-gray-200 bg-white hover:border-purple-200 transition-colors">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center text-purple-600 font-bold text-sm">
                {i + 1}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <Icon className="h-4 w-4 text-gray-500" />
                  <span className="font-semibold text-gray-800 text-sm">{step.title}</span>
                </div>
                <p className="text-xs text-gray-500 leading-relaxed">{step.desc}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FeaturesTab() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {FEATURES.map((f) => {
        const Icon = f.icon;
        return (
          <a
            key={f.title}
            href={f.href}
            className="flex gap-4 p-4 rounded-xl border border-gray-200 bg-white hover:border-purple-200 hover:shadow-sm transition-all group"
          >
            <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${colorMap[f.color]}`}>
              <Icon className="h-5 w-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1">
                <span className="font-semibold text-gray-800 text-sm group-hover:text-purple-700">{f.title}</span>
                <ExternalLink className="h-3 w-3 text-gray-400 group-hover:text-purple-500" />
              </div>
              <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{f.desc}</p>
            </div>
          </a>
        );
      })}
    </div>
  );
}

function FAQTab() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  return (
    <div className="space-y-2">
      {FAQ_ITEMS.map((item, i) => (
        <div key={i} className="border border-gray-200 rounded-xl overflow-hidden">
          <button
            className="w-full flex items-center justify-between px-4 py-3.5 text-left hover:bg-gray-50 transition-colors"
            onClick={() => setOpenIndex(openIndex === i ? null : i)}
          >
            <span className="font-medium text-gray-800 text-sm">{item.q}</span>
            {openIndex === i ? (
              <ChevronDown className="h-4 w-4 text-gray-400 flex-shrink-0" />
            ) : (
              <ChevronRight className="h-4 w-4 text-gray-400 flex-shrink-0" />
            )}
          </button>
          {openIndex === i && (
            <div className="px-4 pb-4 pt-1 border-t border-gray-100">
              <p className="text-sm text-gray-600 leading-relaxed">{item.a}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function ChangelogTab() {
  return (
    <div className="space-y-6">
      {CHANGELOG.map((entry) => (
        <div key={entry.version} className="flex gap-4">
          <div className="flex-shrink-0 text-right w-16">
            <span className="text-xs font-semibold text-purple-700 bg-purple-50 px-2 py-1 rounded-full">{entry.version}</span>
            <p className="text-xs text-gray-400 mt-1">{entry.date}</p>
          </div>
          <div className="flex-1 pt-0.5">
            <ul className="space-y-1.5">
              {entry.items.map((item, i) => (
                <li key={i} className="flex gap-2 text-sm text-gray-700">
                  <span className="mt-1.5 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-purple-400" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ))}
    </div>
  );
}

function SupportTab() {
  const [bugDesc, setBugDesc] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    if (!bugDesc.trim()) return;
    // In production this would POST to /api/v1/support/bug-report
    setSubmitted(true);
    setBugDesc("");
  };

  return (
    <div className="space-y-6 max-w-lg">
      {submitted && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-sm text-green-800">
          ✓ Bug report submitted. Thank you — we&apos;ll look into it.
        </div>
      )}

      <div className="space-y-3">
        <h3 className="font-semibold text-gray-800">Report a Bug</h3>
        <textarea
          value={bugDesc}
          onChange={(e) => setBugDesc(e.target.value)}
          placeholder="Describe the issue — what happened, what you expected, and how to reproduce it..."
          rows={4}
          className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-500"
        />
        <button
          onClick={handleSubmit}
          disabled={!bugDesc.trim()}
          className="px-4 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          Submit Report
        </button>
      </div>

      <div className="border-t border-gray-200 pt-4 space-y-3">
        <h3 className="font-semibold text-gray-800">Other Resources</h3>
        <div className="space-y-2">
          <a
            href="#"
            className="flex items-center gap-3 p-3 rounded-xl border border-gray-200 hover:border-purple-200 transition-colors group"
          >
            <ExternalLink className="h-4 w-4 text-gray-400 group-hover:text-purple-600" />
            <div>
              <div className="text-sm font-medium text-gray-700 group-hover:text-purple-700">Request a Feature</div>
              <div className="text-xs text-gray-500">Submit ideas on our feedback portal</div>
            </div>
          </a>
          <a
            href="#"
            className="flex items-center gap-3 p-3 rounded-xl border border-gray-200 hover:border-purple-200 transition-colors group"
          >
            <BookOpen className="h-4 w-4 text-gray-400 group-hover:text-purple-600" />
            <div>
              <div className="text-sm font-medium text-gray-700 group-hover:text-purple-700">Documentation</div>
              <div className="text-xs text-gray-500">Full API reference and integration guides</div>
            </div>
          </a>
        </div>
      </div>
    </div>
  );
}

export default function HelpPage() {
  const [activeTab, setActiveTab] = useState<TabId>("commands");

  const tabContent: Record<TabId, React.ReactNode> = {
    commands: <CommandsTab />,
    "getting-started": <GettingStartedTab />,
    features: <FeaturesTab />,
    faq: <FAQTab />,
    changelog: <ChangelogTab />,
    support: <SupportTab />,
  };

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <HelpCircle className="h-7 w-7 text-purple-600" />
            Help & Docs
          </h1>
          <p className="text-gray-500 mt-1 text-sm">
            Everything you need to get the most out of DokuDoc and AskyDoc.
          </p>
        </div>

        {/* Tab Bar */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1 mb-6 overflow-x-auto">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                  isActive
                    ? "bg-white text-purple-700 shadow-sm"
                    : "text-gray-600 hover:text-gray-800"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        <div>{tabContent[activeTab]}</div>
      </div>
    </AppLayout>
  );
}
