"use client";

import React, { useState } from "react";
import Link from "next/link";
import { AppLayout } from "@/components/layout/AppLayout";
import {
  GitBranch,
  Upload,
  Zap,
  Eye,
  RefreshCw,
  ArrowRight,
  CheckCircle,
  Lock,
  User,
  BarChart2,
  Code,
  Layers,
  Network,
  ChevronDown,
  ChevronRight,
  CreditCard,
  Play,
  Search,
  Repeat,
  Star,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const PERSONAS = [
  {
    id: "developer",
    label: "Developer",
    icon: Code,
    color: "blue",
    tagline: "Technical mermaid diagrams, function-level call graphs",
  },
  {
    id: "ba",
    label: "Business Analyst / PM",
    icon: BarChart2,
    color: "amber",
    tagline: "Plain-English simplified diagrams, requirement traceability",
  },
  {
    id: "cxo",
    label: "CXO / Admin",
    icon: Star,
    color: "purple",
    tagline: "High-level system flow, backfill management across repositories",
  },
];

const colorMap: Record<string, { bg: string; text: string; border: string; badge: string }> = {
  blue:   { bg: "bg-blue-50",   text: "text-blue-700",   border: "border-blue-200",  badge: "bg-blue-100 text-blue-700" },
  amber:  { bg: "bg-amber-50",  text: "text-amber-700",  border: "border-amber-200", badge: "bg-amber-100 text-amber-700" },
  purple: { bg: "bg-purple-50", text: "text-purple-700", border: "border-purple-200",badge: "bg-purple-100 text-purple-700" },
  green:  { bg: "bg-green-50",  text: "text-green-700",  border: "border-green-200", badge: "bg-green-100 text-green-700" },
  gray:   { bg: "bg-gray-50",   text: "text-gray-700",   border: "border-gray-200",  badge: "bg-gray-100 text-gray-600" },
  rose:   { bg: "bg-rose-50",   text: "text-rose-700",   border: "border-rose-200",  badge: "bg-rose-100 text-rose-700" },
};

interface JourneyStep {
  number: number;
  title: string;
  description: string;
  detail: string;
  icon: React.ElementType;
  color: string;
  personas: string[];
  badge?: string;
  action?: { label: string; href: string };
}

const JOURNEY_STEPS: JourneyStep[] = [
  {
    number: 1,
    title: "Connect a Repository",
    description: "Add your GitHub or GitLab repository to DokuDoc.",
    detail:
      "Navigate to Code → Add Repository. Paste your repo URL or upload a ZIP. DokuDoc discovers all source files automatically.",
    icon: Upload,
    color: "blue",
    personas: ["developer", "cxo"],
    action: { label: "Go to Code", href: "/dashboard/code" },
  },
  {
    number: 2,
    title: "Run Code Analysis",
    description: "AI analyses every file and extracts structured metadata.",
    detail:
      "After connecting a repo, analysis starts automatically. DokuDoc reads each file's purpose, outbound calls, data models, and dependencies and stores them as structured JSON — the raw material for data-flow edges.",
    icon: Zap,
    color: "amber",
    personas: ["developer", "ba", "cxo"],
    badge: "Auto",
  },
  {
    number: 3,
    title: "Upgrade to Professional",
    description: "Data flow diagrams are a premium feature.",
    detail:
      "Free-tier tenants can run analysis but cannot generate data-flow edges. Upgrade to Professional, Pro, or Enterprise in Settings → Billing to unlock the feature. Edges are built at zero extra LLM cost — they are derived deterministically from the structured analysis that already ran.",
    icon: CreditCard,
    color: "purple",
    personas: ["developer", "ba", "cxo"],
    badge: "Premium",
    action: { label: "View Plans", href: "/settings/billing" },
  },
  {
    number: 4,
    title: "Trigger a Data-Flow Backfill",
    description: "Build edges for every analysed component in a repository.",
    detail:
      "Go to Code → select a repository → click Rebuild Data Flow. A Celery background task processes all completed components, extracts 10 edge types (HTTP_TRIGGER, SERVICE_CALL, DB_READ/WRITE, CACHE_READ/WRITE, EVENT_PUBLISH/CONSUME, SCHEMA_VALIDATION, EXTERNAL_API) and writes them to the database. Progress updates every 5 components.",
    icon: Play,
    color: "green",
    personas: ["developer", "cxo"],
    badge: "One-time",
  },
  {
    number: 5,
    title: "Navigate to a Component",
    description: "Open any analysed source file or service.",
    detail:
      "Go to Code, search or browse your repository, and click a component (e.g. AuthService, PaymentController). The component detail page has multiple tabs: Overview, Analysis, Ontology, and — for premium tenants — Data Flow.",
    icon: Search,
    color: "blue",
    personas: ["developer", "ba"],
    action: { label: "Browse Code", href: "/dashboard/code" },
  },
  {
    number: 6,
    title: "Open the Data Flow Tab",
    description: "View the egocentric data-flow diagram for this component.",
    detail:
      "Click the 'Data Flow' tab (GitBranch icon). DokuDoc renders a Mermaid flowchart showing all services, models, and external systems this component communicates with. Nodes are grouped into swimlanes by file role. If this is your first visit, click 'Build Diagram' to generate edges for just this component.",
    icon: GitBranch,
    color: "purple",
    personas: ["developer", "ba", "cxo"],
  },
  {
    number: 7,
    title: "Switch Between Technical and Simple Views",
    description: "Choose the right level of detail for your role.",
    detail:
      "Developers default to Technical mode — showing function names, edge types (badges), step indices, and data_in/data_out descriptions. BAs, PMs, and CXOs are automatically switched to Simple mode — a plain-language narrative diagram. Toggle the mode with the selector in the top-right of the diagram panel.",
    icon: Layers,
    color: "amber",
    personas: ["developer", "ba", "cxo"],
  },
  {
    number: 8,
    title: "Explore the Edge List",
    description: "See every call this component makes and every caller.",
    detail:
      "Below the diagram, the Edge List Panel shows two columns: Calls (outbound) and Called By (inbound). Each edge shows the edge type badge, a linked component name, the calling function pair (source_function → target_function), a human label, and data_in / data_out descriptions. Click any component name to navigate directly to its own Data Flow tab.",
    icon: Network,
    color: "green",
    personas: ["developer", "ba"],
  },
  {
    number: 9,
    title: "Trace a Request End-to-End",
    description: "Follow a request through the entire call chain.",
    detail:
      "Switch to 'Request Trace' mode and choose a trace depth (3, 5, or 8 hops). DokuDoc runs a BFS traversal from the current component and renders a single Mermaid diagram showing the full path. Useful for understanding the complete flow of an HTTP request from API gateway to database.",
    icon: Repeat,
    color: "rose",
    personas: ["developer"],
    badge: "Advanced",
  },
  {
    number: 10,
    title: "Rebuild After Code Changes",
    description: "Keep diagrams fresh when the codebase evolves.",
    detail:
      "After modifying a component, click 'Rebuild' in the Data Flow tab. DokuDoc queues a single-component rebuild task. The diagram header shows a progress indicator while the task runs, then auto-reloads when complete. The 'Built X ago' timestamp helps you know when the diagram was last generated.",
    icon: RefreshCw,
    color: "blue",
    personas: ["developer", "cxo"],
  },
];

const EDGE_TYPES = [
  { type: "HTTP_TRIGGER",      color: "bg-blue-100 text-blue-800",     desc: "Incoming HTTP request to a route/controller" },
  { type: "SERVICE_CALL",      color: "bg-purple-100 text-purple-800", desc: "Internal service-to-service call" },
  { type: "DB_READ",           color: "bg-amber-100 text-amber-800",   desc: "Database SELECT / ORM .get() / .filter()" },
  { type: "DB_WRITE",          color: "bg-orange-100 text-orange-800", desc: "Database INSERT / UPDATE / DELETE" },
  { type: "SCHEMA_VALIDATION", color: "bg-gray-100 text-gray-700",     desc: "Pydantic, Zod, or schema validation call" },
  { type: "EXTERNAL_API",      color: "bg-pink-100 text-pink-800",     desc: "Call to a third-party HTTP API" },
  { type: "CACHE_READ",        color: "bg-teal-100 text-teal-700",     desc: "Redis GET, memcached read" },
  { type: "CACHE_WRITE",       color: "bg-cyan-100 text-cyan-800",     desc: "Redis SET/SETEX, cache write" },
  { type: "EVENT_PUBLISH",     color: "bg-green-100 text-green-800",   desc: "Kafka/RabbitMQ produce, event emit" },
  { type: "EVENT_CONSUME",     color: "bg-lime-100 text-lime-800",     desc: "Kafka/RabbitMQ consume, event handler" },
];

const FAQ_ITEMS = [
  {
    q: "Why is the Data Flow tab not visible on my component?",
    a: "The Data Flow tab only appears for Professional, Pro, or Enterprise tenants. Free-tier tenants see a premium gate card instead. Upgrade in Settings → Billing.",
  },
  {
    q: "What does 'No data flow diagram yet' mean?",
    a: "Edges have never been built for this component. Click 'Build Diagram' to trigger a single-component rebuild, or run the full backfill from the repository page to build edges for all components at once.",
  },
  {
    q: "What's the difference between 'No data flow diagram yet' and 'No connections found'?",
    a: "'No data flow diagram yet' means edges have never been extracted. 'No connections found' means edges were extracted but this component makes zero external calls (e.g. a pure utility or constant file).",
  },
  {
    q: "How does DokuDoc detect edge types without running the code?",
    a: "Edge types are inferred deterministically from the structured_analysis JSON that already ran during code analysis. DokuDoc checks function names, import names, and outbound_calls entries against keyword frozensets for each edge type. No additional LLM calls are made.",
  },
  {
    q: "Can I see the diagram for a component in a different repository?",
    a: "Yes. Click any linked component name in the Edge List Panel — it navigates to that component's detail page in the same or a different repository where you can view its own Data Flow tab.",
  },
  {
    q: "The diagram is outdated after I pushed new code. How do I refresh it?",
    a: "Click 'Rebuild' in the Data Flow tab to queue a single-component rebuild. For a full repository refresh, go to Code → select the repository → click Rebuild Data Flow to backfill all components.",
  },
];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PersonaSelector({
  selected,
  onChange,
}: {
  selected: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-3">
      {PERSONAS.map((p) => {
        const Icon = p.icon;
        const c = colorMap[p.color];
        const isSelected = selected === p.id;
        return (
          <button
            key={p.id}
            onClick={() => onChange(p.id)}
            className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl border-2 text-sm font-medium transition-all ${
              isSelected
                ? `${c.bg} ${c.border} ${c.text} shadow-sm`
                : "border-gray-200 text-gray-600 hover:border-gray-300 bg-white"
            }`}
          >
            <Icon className="h-4 w-4" />
            {p.label}
          </button>
        );
      })}
    </div>
  );
}

function StepCard({ step, isFiltered }: { step: JourneyStep; isFiltered: boolean }) {
  const Icon = step.icon;
  const c = colorMap[step.color];
  return (
    <div
      className={`relative flex gap-5 p-5 rounded-2xl border transition-all ${
        isFiltered
          ? "opacity-30 scale-95"
          : "border-gray-200 bg-white shadow-sm hover:border-purple-200 hover:shadow-md"
      }`}
    >
      {/* Step number + icon */}
      <div className="flex flex-col items-center gap-2 flex-shrink-0">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${c.bg}`}>
          <Icon className={`h-5 w-5 ${c.text}`} />
        </div>
        <span className="text-xs font-bold text-gray-300">#{step.number}</span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">{step.title}</h3>
            <p className="text-xs text-gray-500 mt-0.5">{step.description}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {step.badge && (
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${c.badge}`}>
                {step.badge}
              </span>
            )}
            <div className="flex gap-1">
              {step.personas.map((pid) => {
                const persona = PERSONAS.find((p) => p.id === pid);
                if (!persona) return null;
                const pc = colorMap[persona.color];
                return (
                  <span key={pid} className={`text-[9px] px-1.5 py-0.5 rounded-full ${pc.badge}`}>
                    {persona.label.split(" ")[0]}
                  </span>
                );
              })}
            </div>
          </div>
        </div>

        <p className="text-xs text-gray-600 leading-relaxed mt-2">{step.detail}</p>

        {step.action && (
          <Link
            href={step.action.href}
            className="inline-flex items-center gap-1.5 mt-3 text-xs font-medium text-purple-600 hover:text-purple-800"
          >
            {step.action.label}
            <ArrowRight className="h-3 w-3" />
          </Link>
        )}
      </div>
    </div>
  );
}

function EdgeTypesTab() {
  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-600">
        DokuDoc extracts 10 edge types deterministically from structured analysis — no extra LLM calls.
      </p>
      <div className="overflow-hidden rounded-xl border border-gray-200">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-3 font-semibold text-gray-700 w-48">Edge Type</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-700">Detected When…</th>
            </tr>
          </thead>
          <tbody>
            {EDGE_TYPES.map((et, i) => (
              <tr key={et.type} className={i % 2 === 0 ? "bg-white" : "bg-gray-50/50"}>
                <td className="px-4 py-3">
                  <span className={`text-xs font-mono px-2 py-1 rounded-full font-semibold ${et.color}`}>
                    {et.type}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-600 text-xs">{et.desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
            {openIndex === i
              ? <ChevronDown className="h-4 w-4 text-gray-400 flex-shrink-0" />
              : <ChevronRight className="h-4 w-4 text-gray-400 flex-shrink-0" />}
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

type TabId = "journey" | "edge-types" | "faq";

const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: "journey",     label: "User Journey",  icon: GitBranch },
  { id: "edge-types",  label: "Edge Types",    icon: Network },
  { id: "faq",         label: "FAQ",           icon: Eye },
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DataFlowJourneyPage() {
  const [activeTab, setActiveTab] = useState<TabId>("journey");
  const [persona, setPersona] = useState("developer");

  const filteredSteps = JOURNEY_STEPS.map((step) => ({
    ...step,
    isFiltered: !step.personas.includes(persona),
  }));

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto px-6 py-8">

        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-3">
            <Link href="/dashboard/help" className="hover:text-purple-600">Help &amp; Docs</Link>
            <ChevronRight className="h-3 w-3" />
            <span>Data Flow Journey</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <GitBranch className="h-7 w-7 text-purple-600" />
            Data Flow Diagram — User Journey
          </h1>
          <p className="text-gray-500 mt-1 text-sm max-w-2xl">
            A step-by-step guide to the Request Data Flow feature: from connecting a repository
            to reading interactive diagrams and keeping them fresh as your codebase evolves.
          </p>

          {/* Premium badge */}
          <div className="mt-4 inline-flex items-center gap-2 bg-purple-50 border border-purple-200 rounded-xl px-4 py-2">
            <Lock className="h-4 w-4 text-purple-600" />
            <span className="text-sm text-purple-700 font-medium">
              Data Flow is a Professional / Enterprise feature.
            </span>
            <Link
              href="/settings/billing"
              className="text-sm text-purple-800 font-semibold underline hover:text-purple-900"
            >
              Upgrade
            </Link>
          </div>
        </div>

        {/* Tab Bar */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1 mb-6">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
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
        {activeTab === "journey" && (
          <div className="space-y-6">
            {/* Role filter */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Show journey for:
              </p>
              <PersonaSelector selected={persona} onChange={setPersona} />
            </div>

            {/* Legend */}
            <div className="flex flex-wrap gap-3 items-center text-xs text-gray-500">
              <span className="font-medium">Applies to:</span>
              {PERSONAS.map((p) => {
                const c = colorMap[p.color];
                return (
                  <span key={p.id} className={`px-2 py-0.5 rounded-full ${c.badge}`}>
                    {p.label.split(" ")[0]}
                  </span>
                );
              })}
              <span className="ml-2 text-gray-400">— steps not matching your role are dimmed</span>
            </div>

            {/* Steps */}
            <div className="space-y-3">
              {filteredSteps.map((step, i) => (
                <React.Fragment key={step.number}>
                  <StepCard step={step} isFiltered={step.isFiltered} />
                  {i < filteredSteps.length - 1 && !step.isFiltered && !filteredSteps[i + 1].isFiltered && (
                    <div className="flex justify-center">
                      <ArrowRight className="h-4 w-4 text-gray-300 rotate-90" />
                    </div>
                  )}
                </React.Fragment>
              ))}
            </div>

            {/* Summary card */}
            <div className="mt-6 bg-gradient-to-br from-purple-50 to-blue-50 border border-purple-200 rounded-2xl p-6">
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-purple-600" />
                What you get at the end of this journey
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-gray-700">
                {[
                  "Interactive Mermaid diagrams per component",
                  "Two rendering modes: Technical and Simple",
                  "10 edge types with colour-coded badges",
                  "Clickable node links to related components",
                  "Function-level call context (source → target)",
                  "Data in/out descriptions per edge",
                  "BFS request trace across up to 8 hops",
                  "Auto-rebuild on code change with progress tracking",
                ].map((item) => (
                  <div key={item} className="flex items-start gap-2">
                    <CheckCircle className="h-4 w-4 text-purple-500 flex-shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === "edge-types" && <EdgeTypesTab />}
        {activeTab === "faq" && <FAQTab />}
      </div>
    </AppLayout>
  );
}
