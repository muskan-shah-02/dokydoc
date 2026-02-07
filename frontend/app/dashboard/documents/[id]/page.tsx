/*
  frontend/app/dashboard/documents/[id]/page.tsx
  -----------------------------------------------
  Status: FINAL MASTER
  Features: Pulse Pipeline + Vital Signs + Narrative Report + Live Terminal + Billing Notifications
*/
"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  FileText,
  GitCommit,
  Clock,
  AlertCircle,
  BrainCircuit,
  ChevronDown,
  FileCode,
  BookOpen,
  Database,
  HelpCircle,
  Loader2,
  CheckCircle,
  PlayCircle,
  Terminal,
  Cpu,
  ScanLine,
  Split,
  Sparkles,
  Download,
  Share2,
  RefreshCw,
  LayoutDashboard,
  ArrowRight,
  StopCircle,
  Activity,
  List,
  XCircle,
  PauseCircle,
  ShieldAlert,
  AlertTriangle,
  Target,
  Printer,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useBillingNotification } from "@/components/BillingToast";
import { api } from "@/lib/api";
import SmartAnalysisView from "@/components/analysis/SmartAnalysisView";
import DynamicAnalysisView from "@/components/analysis/DynamicAnalysisView";

// --- 1. Types ---

interface Document {
  id: number;
  filename: string;
  document_type: string;
  version: string;
  created_at: string;
  raw_text: string | null;
  composition_analysis: any | null;
  status: string | null;
  progress: number | null;
  file_size_kb?: number | null;
  error_message?: string | null;
  ai_cost_inr?: number | null;
  token_count_input?: number | null;
  token_count_output?: number | null;
}

interface DocumentSegment {
  id: number;
  segment_type: string;
  start_char_index: number;
  end_char_index: number;
  document_id: number;
  created_at: string;
}

interface AnalysisResult {
  id: number;
  segment_id: number;
  document_id: number | null;
  structured_data: any;
  created_at: string;
}

interface AnalyzedSegment {
  segment: DocumentSegment;
  analysis_result: AnalysisResult | null;
  status: "analyzed" | "pending" | "failed";
}

// --- 2. Helpers ---

const getStatusStep = (status: string | null) => {
  if (!status) return 0;
  if (status === "uploaded") return 1;
  if (status === "parsing") return 2;
  if (status === "analyzing" || status === "pass_1_composition") return 3;
  if (status === "pass_2_segmenting") return 4;
  if (status === "pass_3_extraction") return 5;
  if (status === "completed") return 6;
  if (status === "stopped") return -2;
  if (status.includes("failed")) return -1;
  return 1;
};

const ACTIVE_STATES = [
  "uploaded",
  "processing",
  "parsing",
  "analyzing",
  "pass_1_composition",
  "pass_2_segmenting",
  "pass_3_extraction",
];

// --- 3. Components ---

// A. Pipeline Node (Pulse & Predict)
const PipelineStepNode = ({
  step,
  currentStep,
  isComplete,
  isFailed,
  isStopped,
}: {
  step: any;
  currentStep: number;
  isComplete: boolean;
  isFailed: boolean;
  isStopped: boolean;
}) => {
  const isActive = currentStep === step.id;
  const isPast = currentStep > step.id || isComplete;
  const Icon = step.icon;

  return (
    <div className="relative flex flex-col items-center group cursor-default z-10 w-12">
      {/* Tooltip */}
      <div className="absolute bottom-full mb-3 opacity-0 group-hover:opacity-100 transition-all duration-300 transform translate-y-2 group-hover:translate-y-0 pointer-events-none min-w-[140px] left-1/2 -translate-x-1/2 z-50">
        <div className="bg-slate-900 text-white text-xs rounded-lg p-3 shadow-xl border border-slate-700 relative">
          <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-slate-900 rotate-45 border-b border-r border-slate-700"></div>
          <div className="font-semibold mb-1 flex items-center gap-2">
            <Icon className="w-3 h-3 text-blue-400" /> {step.label}
          </div>
          <div className="text-slate-400 mb-1.5 border-b border-slate-800 pb-1">
            {isActive
              ? "Processing now..."
              : isPast
              ? "Completed"
              : isFailed
              ? "Failed here"
              : "Waiting..."}
          </div>
          <div className="flex items-center justify-between text-[10px] font-mono">
            <span className="text-slate-500">Est. Time:</span>
            <span className="text-green-400">{step.estTime}</span>
          </div>
        </div>
      </div>

      {/* Pulse Ring */}
      {isActive && !isFailed && !isStopped && (
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-10 h-10 bg-blue-400/30 rounded-full animate-ping -z-10"></div>
      )}

      {/* Icon Circle */}
      <div
        className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-500 bg-white ${
          isActive
            ? "border-blue-600 text-blue-600 shadow-[0_0_15px_rgba(37,99,235,0.3)] scale-110"
            : isPast
            ? "border-green-500 bg-green-50 text-green-600"
            : "border-gray-200 text-gray-300"
        } ${isFailed && isActive ? "border-red-500 text-red-500" : ""} ${
          isStopped && isActive ? "border-orange-500 text-orange-500" : ""
        }`}
      >
        {isPast ? (
          <CheckCircle className="w-5 h-5" />
        ) : isFailed && isActive ? (
          <XCircle className="w-5 h-5" />
        ) : isStopped && isActive ? (
          <PauseCircle className="w-5 h-5" />
        ) : isActive ? (
          <Icon className="w-5 h-5 animate-pulse" />
        ) : (
          <Icon className="w-5 h-5" />
        )}
      </div>

      {/* Label */}
      <span
        className={`mt-3 text-[10px] font-bold uppercase tracking-wider transition-colors duration-300 text-center ${
          isActive
            ? "text-blue-700 scale-105"
            : isPast
            ? "text-green-600"
            : "text-gray-400"
        }`}
      >
        {step.label}
      </span>
    </div>
  );
};

// B. Interactive Pipeline
const InteractivePipeline = ({
  status,
  progress,
}: {
  status: string | null;
  progress: number;
}) => {
  const currentStep = getStatusStep(status);
  const isComplete = currentStep === 6;
  const isFailed = currentStep === -1;
  const isStopped = currentStep === -2;
  const displayStep =
    isFailed || isStopped
      ? status?.includes("parsing")
        ? 2
        : status?.includes("analyzing")
        ? 3
        : 4
      : currentStep;

  const steps = [
    { id: 1, label: "Queued", icon: Clock, estTime: "< 1s" },
    { id: 2, label: "Parsing", icon: ScanLine, estTime: "~5-10s" },
    { id: 3, label: "Classify", icon: BrainCircuit, estTime: "~2-4s" },
    { id: 4, label: "Segment", icon: Split, estTime: "~3-5s" },
    { id: 5, label: "Extract", icon: Cpu, estTime: "~20s+" },
    { id: 6, label: "Ready", icon: CheckCircle, estTime: "Done" },
  ];

  return (
    <div className="w-full py-6 px-4">
      <div className="relative">
        <div className="absolute top-5 left-0 w-full h-0.5 bg-gray-100 -z-20 rounded-full" />
        <div
          className={`absolute top-5 left-0 h-0.5 transition-all duration-1000 ease-out -z-10 rounded-full ${
            isFailed
              ? "bg-red-500"
              : isStopped
              ? "bg-orange-500"
              : "bg-gradient-to-r from-blue-600 via-blue-400 to-blue-600 bg-[length:200%_100%] animate-[shimmer_2s_infinite_linear]"
          }`}
          style={{ width: `${Math.min(((displayStep - 1) / 5) * 100, 100)}%` }}
        />
        <div className="flex justify-between w-full">
          {steps.map((step) => (
            <PipelineStepNode
              key={step.id}
              step={step}
              currentStep={displayStep}
              isComplete={isComplete}
              isFailed={isFailed}
              isStopped={isStopped}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

// C. Live Terminal
const LiveTerminal = ({
  status,
  progress,
  error,
}: {
  status: string | null;
  progress: number;
  error?: string | null;
}) => {
  const currentStep = getStatusStep(status);
  const logs = useMemo(() => {
    if (error) return [{ time: "ERROR", msg: error, type: "error" }];
    const l = [];
    if (currentStep >= 1)
      l.push({ time: "00:00", msg: "Document upload verified.", type: "info" });
    if (currentStep >= 2)
      l.push({ time: "00:02", msg: "Initializing Parser...", type: "info" });
    if (currentStep === 2)
      l.push({
        time: "00:05",
        msg: `Reading stream... ${progress}%`,
        type: "process",
      });
    if (currentStep >= 3)
      l.push({ time: "00:12", msg: "AI Classification: Started", type: "ai" });
    if (currentStep >= 4)
      l.push({ time: "00:18", msg: "Segmentation: Active", type: "ai" });
    if (currentStep >= 5)
      l.push({ time: "00:25", msg: "Extraction: Running...", type: "ai" });
    if (currentStep === 6)
      l.push({
        time: "00:32",
        msg: "Completed Successfully.",
        type: "success",
      });
    return l;
  }, [currentStep, progress, error]);

  return (
    <div className="bg-slate-950 rounded-lg border border-slate-800 p-4 font-mono text-xs h-48 overflow-y-auto shadow-inner custom-scrollbar">
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-800">
        <Terminal className="w-3 h-3 text-slate-400" />
        <span className="text-slate-400 font-semibold uppercase tracking-wider">
          System Log
        </span>
      </div>
      <div className="space-y-1.5">
        {logs.map((log, idx) => (
          <div
            key={idx}
            className="flex gap-3 animate-in fade-in slide-in-from-left-2 duration-300"
          >
            <span className="text-slate-600 flex-shrink-0">[{log.time}]</span>
            <span
              className={`${
                log.type === "success"
                  ? "text-emerald-400 font-bold"
                  : log.type === "error"
                  ? "text-red-400 font-bold"
                  : log.type === "ai"
                  ? "text-purple-400"
                  : log.type === "process"
                  ? "text-yellow-400 animate-pulse"
                  : "text-blue-300"
              }`}
            >
              {log.type === "success"
                ? "✓ "
                : log.type === "error"
                ? "✗ "
                : "> "}
              {log.msg}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// D. Analysis HUD Wrapper
const AnalysisStatusHUD = ({
  doc,
  onStop,
}: {
  doc: Document;
  onStop: () => void;
}) => {
  const [showTerminal, setShowTerminal] = useState(false);
  const isProcessing = ACTIVE_STATES.includes(doc.status || "");
  const isFailed = doc.status?.includes("failed");
  const isStopped = doc.status === "stopped";
  const isComplete = doc.status === "completed";

  useEffect(() => {
    if (isProcessing) setShowTerminal(true);
  }, [isProcessing]);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden mb-8 print:hidden">
      <div className="p-6 bg-gradient-to-r from-white via-gray-50/30 to-white">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              {isComplete ? (
                <span className="text-green-600 flex items-center">
                  <CheckCircle className="w-5 h-5 mr-2" /> Analysis Complete
                </span>
              ) : isStopped ? (
                <span className="text-orange-600 flex items-center">
                  <PauseCircle className="w-5 h-5 mr-2" /> Analysis Stopped
                </span>
              ) : isFailed ? (
                <span className="text-red-600 flex items-center">
                  <AlertCircle className="w-5 h-5 mr-2" /> Analysis Failed
                </span>
              ) : (
                <span className="text-blue-600 flex items-center">
                  <Activity className="w-5 h-5 mr-2 animate-pulse" />{" "}
                  Processing...
                </span>
              )}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              {isStopped
                ? "User halted the process."
                : doc.error_message ||
                  "Orchestrating multi-pass AI analysis pipeline..."}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowTerminal(!showTerminal)}
              className={showTerminal ? "bg-slate-100" : ""}
            >
              <Terminal className="w-4 h-4 mr-2" />{" "}
              {showTerminal ? "Hide Logs" : "Show Logs"}
            </Button>
            {isProcessing && (
              <Button
                variant="destructive"
                size="sm"
                onClick={onStop}
                className="shadow-sm hover:bg-red-600"
              >
                <StopCircle className="w-4 h-4 mr-2" /> Stop
              </Button>
            )}
          </div>
        </div>
        <InteractivePipeline status={doc.status} progress={doc.progress || 0} />
      </div>
      {showTerminal && (
        <div className="bg-slate-50 p-4 border-t border-gray-100 animate-in slide-in-from-top-2 duration-200">
          <LiveTerminal
            status={doc.status}
            progress={doc.progress || 0}
            error={doc.error_message}
          />
        </div>
      )}
    </div>
  );
};

// E. Vital Signs Bar (Replaces Big Tabs)
const VitalSignsBar = ({
  segments,
  composition,
}: {
  segments: AnalyzedSegment[];
  composition: any;
}) => {
  const analyzedCount = segments.filter((s) => s.analysis_result).length;
  const totalCount = segments.length;
  const insightsCount = segments.reduce(
    (acc, s) =>
      acc +
      (s.analysis_result?.structured_data
        ? Object.keys(s.analysis_result.structured_data).length
        : 0),
    0
  );
  const coverage =
    totalCount > 0 ? Math.round((analyzedCount / totalCount) * 100) : 0;

  let dominantType = "Unknown";
  let maxVal = 0;
  if (composition?.composition) {
    Object.entries(composition.composition).forEach(([k, v]: any) => {
      if (v > maxVal) {
        maxVal = v;
        dominantType = k;
      }
    });
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 print:hidden">
      <div className="bg-white p-3 rounded-xl border border-gray-200 flex items-center gap-3 shadow-sm">
        <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
          <BrainCircuit className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs text-gray-500 font-medium uppercase">
            Type
          </div>
          <div className="text-sm font-bold text-gray-900">
            {dominantType}{" "}
            <span className="text-xs font-normal text-gray-400">
              ({maxVal}%)
            </span>
          </div>
        </div>
      </div>
      <div className="bg-white p-3 rounded-xl border border-gray-200 flex items-center gap-3 shadow-sm">
        <div className="p-2 bg-purple-50 text-purple-600 rounded-lg">
          <Sparkles className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs text-gray-500 font-medium uppercase">
            Insights
          </div>
          <div className="text-sm font-bold text-gray-900">
            {insightsCount}{" "}
            <span className="text-xs font-normal text-gray-400">Points</span>
          </div>
        </div>
      </div>
      <div className="bg-white p-3 rounded-xl border border-gray-200 flex items-center gap-3 shadow-sm">
        <div className="p-2 bg-green-50 text-green-600 rounded-lg">
          <Activity className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs text-gray-500 font-medium uppercase">
            Coverage
          </div>
          <div className="text-sm font-bold text-gray-900">
            {coverage}%{" "}
            <span className="text-xs font-normal text-gray-400">
              ({analyzedCount}/{totalCount})
            </span>
          </div>
        </div>
      </div>
      <div className="bg-white p-3 rounded-xl border border-gray-200 flex items-center gap-3 shadow-sm">
        <div className="p-2 bg-orange-50 text-orange-600 rounded-lg">
          <ShieldAlert className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs text-gray-500 font-medium uppercase">
            Risk Scan
          </div>
          <div className="text-sm font-bold text-gray-900">
            Pass{" "}
            <span className="text-xs font-normal text-gray-400">(Auto)</span>
          </div>
        </div>
      </div>
    </div>
  );
};

// F. Narrative Section & Report (The Human Readability Layer)
const NarrativeSection = ({
  title,
  data,
  type,
}: {
  title: string;
  data: any;
  type: "list" | "text" | "risk" | "kv";
}) => {
  if (!data) return null;
  const cleanKey = (k: string) =>
    k.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());

  return (
    <div className="mb-8 break-inside-avoid">
      <h3 className="text-lg font-bold text-gray-800 mb-3 border-b border-gray-100 pb-2 flex items-center gap-2">
        {type === "risk" && <AlertTriangle className="w-5 h-5 text-red-500" />}
        {type === "list" && <List className="w-5 h-5 text-blue-500" />}
        {type === "kv" && <Target className="w-5 h-5 text-purple-500" />}
        {title}
      </h3>
      <div className="text-sm text-gray-600 leading-relaxed">
        {type === "text" && <p>{String(data)}</p>}
        {type === "list" && Array.isArray(data) && (
          <ul className="space-y-2">
            {data.map((item: any, i: number) => (
              <li key={i} className="flex items-start gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-2 flex-shrink-0" />
                <span>
                  {typeof item === "object" ? JSON.stringify(item) : item}
                </span>
              </li>
            ))}
          </ul>
        )}
        {type === "risk" && Array.isArray(data) && (
          <div className="grid gap-3">
            {data.map((item: any, i: number) => (
              <div
                key={i}
                className="bg-red-50 border border-red-100 p-3 rounded-lg text-red-800 flex gap-3"
              >
                <ShieldAlert className="w-5 h-5 flex-shrink-0" />
                <div>
                  {typeof item === "object" ? JSON.stringify(item) : item}
                </div>
              </div>
            ))}
          </div>
        )}
        {type === "kv" && typeof data === "object" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(data).map(([k, v], i) => (
              <div
                key={i}
                className="bg-gray-50 p-3 rounded-lg border border-gray-100"
              >
                <div className="text-xs font-semibold text-gray-500 uppercase mb-1">
                  {cleanKey(k)}
                </div>
                <div className="font-medium text-gray-900">{String(v)}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const ExecutiveReport = ({ segments }: { segments: AnalyzedSegment[] }) => {
  const businessReqs: any[] = [];
  const techSpecs: any[] = [];
  const risks: any[] = [];
  const summaries: string[] = [];

  segments.forEach((s) => {
    const data = s.analysis_result?.structured_data;
    if (!data) return;
    Object.entries(data).forEach(([key, value]) => {
      const lowerKey = key.toLowerCase();
      if (
        lowerKey.includes("requirement") ||
        lowerKey.includes("business") ||
        lowerKey.includes("feature")
      ) {
        if (Array.isArray(value)) businessReqs.push(...value);
        else businessReqs.push(value);
      } else if (
        lowerKey.includes("risk") ||
        lowerKey.includes("security") ||
        lowerKey.includes("compliance")
      ) {
        if (Array.isArray(value)) risks.push(...value);
        else risks.push(value);
      } else if (
        lowerKey.includes("summary") ||
        lowerKey.includes("description")
      ) {
        summaries.push(String(value));
      } else {
        if (typeof value === "object") techSpecs.push({ [key]: value });
      }
    });
  });

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="space-y-6">
      <Card className="border-0 shadow-lg print:shadow-none print:border-0">
        <CardHeader className="bg-gray-50 border-b border-gray-100 print:hidden">
          <div className="flex justify-between items-center">
            <div>
              <CardTitle className="text-xl">
                Comprehensive Analysis Report
              </CardTitle>
              <CardDescription>
                Auto-generated executive summary
              </CardDescription>
            </div>
            <Button onClick={handlePrint} variant="outline" className="gap-2">
              <Printer className="w-4 h-4" /> Print / Save as PDF
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-8 md:p-12 min-h-[600px] bg-white">
          <div className="max-w-3xl mx-auto">
            {summaries.length > 0 && (
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">
                  Executive Summary
                </h2>
                <div className="prose text-gray-600">
                  <p>{summaries[0]}</p>
                </div>
              </div>
            )}
            {risks.length > 0 && (
              <NarrativeSection
                title="Risks & Compliance"
                data={risks}
                type="risk"
              />
            )}
            {businessReqs.length > 0 && (
              <NarrativeSection
                title="Key Business Requirements"
                data={businessReqs}
                type="list"
              />
            )}
            {techSpecs.length > 0 && (
              <div className="mt-8 pt-8 border-t border-gray-100">
                <h3 className="text-lg font-bold text-gray-800 mb-4">
                  Technical Appendices
                </h3>
                <div className="grid grid-cols-1 gap-4">
                  {techSpecs.slice(0, 6).map((spec, i) => (
                    <NarrativeSection
                      key={i}
                      title={Object.keys(spec)[0].replace(/_/g, " ")}
                      data={Object.values(spec)[0]}
                      type="kv"
                    />
                  ))}
                </div>
              </div>
            )}
            {summaries.length === 0 && businessReqs.length === 0 && (
              <div className="text-center py-12 text-gray-400">
                <FileText className="w-12 h-12 mx-auto mb-4 opacity-20" />
                <p>No structured insights extracted yet.</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

// G. Segment Card (Technical View)
const SegmentCard = ({
  item,
  index,
}: {
  item: AnalyzedSegment;
  index: number;
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const { segment, analysis_result } = item;

  const renderRawData = (data: any) => {
    if (typeof data !== "object" || data === null) return String(data);
    return (
      <ul className="pl-4 border-l border-gray-200 space-y-1 mt-1">
        {Object.entries(data).map(([k, v], i) => (
          <li key={i} className="text-xs font-mono">
            <span className="text-blue-600">{k}:</span>{" "}
            <span className="text-gray-600">
              {typeof v === "object" ? renderRawData(v) : String(v)}
            </span>
          </li>
        ))}
      </ul>
    );
  };

  const getIcon = (type: string) => {
    switch (type) {
      case "BRD":
        return BookOpen;
      case "SRS":
        return FileCode;
      case "API_DOCS":
        return Database;
      default:
        return HelpCircle;
    }
  };
  const Icon = getIcon(segment.segment_type);

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className="border rounded-xl bg-white overflow-hidden"
    >
      <CollapsibleTrigger className="w-full flex items-center justify-between p-4 bg-gray-50/50 hover:bg-gray-100 text-left">
        <div className="flex items-center gap-4">
          <div className="p-2 bg-white rounded border">
            <Icon className="w-4 h-4 text-gray-500" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="bg-white">
                {segment.segment_type}
              </Badge>
              <span className="text-xs font-mono text-gray-400">
                Seg #{index + 1}
              </span>
            </div>
          </div>
          {analysis_result ? (
            <span className="text-xs text-green-600 font-medium flex items-center">
              <CheckCircle className="w-3 h-3 mr-1" /> Analyzed
            </span>
          ) : (
            <span className="text-xs text-gray-400 flex items-center">
              <Clock className="w-3 h-3 mr-1" /> Pending
            </span>
          )}
        </div>
        <ChevronDown
          className={`w-4 h-4 text-gray-400 transition-transform ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="p-6 border-t border-gray-100">
        {analysis_result ? (
          <div className="overflow-x-auto">
            {renderRawData(analysis_result.structured_data)}
            <div className="mt-4 pt-4 border-t border-gray-100 flex justify-end gap-2">
              <Button variant="outline" size="sm" className="h-8 text-xs">
                <Download className="w-3 h-3 mr-2" /> Export JSON
              </Button>
            </div>
          </div>
        ) : (
          <div className="text-center text-gray-400 italic">
            Data pending...
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
};

// --- 4. Main Page Logic ---
export default function DocumentDetailPage() {
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [doc, setDoc] = useState<Document | null>(null);
  const [segments, setSegments] = useState<AnalyzedSegment[]>([]);
  const [isLive, setIsLive] = useState(false);
  const [loading, setLoading] = useState(true);
  const notifiedProcessingRef = useRef(false);
  const previousStatusRef = useRef<string | null>(null);
  const billingNotification = useBillingNotification();

  useEffect(() => {
    if (typeof window !== "undefined") {
      const parts = window.location.pathname.split("/");
      setDocumentId(parts[parts.length - 1]);
    }
  }, []);

  const fetchFullAnalysis = useCallback(async () => {
    if (!documentId) return;
    const token = localStorage.getItem("accessToken");
    try {
      const res = await fetch(
        `http://localhost:8000/api/v1/documents/${documentId}/analysis`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        setDoc(data.document);
        setSegments(data.segments || []);
        if (ACTIVE_STATES.includes(data.document.status)) setIsLive(true);
        else setIsLive(false);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    fetchFullAnalysis();
  }, [fetchFullAnalysis]);

  // Polling with billing notifications
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isLive && documentId) {
      interval = setInterval(async () => {
        const token = localStorage.getItem("accessToken");
        try {
          const res = await fetch(
            `http://localhost:8000/api/v1/documents/${documentId}/status`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          if (res.ok) {
            const statusData = await res.json();
            const newStatus = statusData.status;
            const prevStatus = previousStatusRef.current;

            // Show "Processing Started" notification when entering AI phases
            const aiStates = ["analyzing", "pass_1_composition", "pass_2_segmenting", "pass_3_extraction"];
            if (aiStates.includes(newStatus) && !notifiedProcessingRef.current) {
              notifiedProcessingRef.current = true;
              const balance = await billingNotification.refreshBalance();
              if (balance !== null) {
                billingNotification.showProcessingStarted(balance);
              }
            }

            setDoc((prev) =>
              prev
                ? {
                    ...prev,
                    status: newStatus,
                    progress: statusData.progress,
                    error_message: statusData.error_message,
                  }
                : null
            );

            // Check if processing just completed
            if (!ACTIVE_STATES.includes(newStatus)) {
              setIsLive(false);

              // Show completion or error notification
              if (newStatus === "completed") {
                try {
                  // Fetch both cost and full document data for tokens
                  const [costData, docData, newBalance] = await Promise.all([
                    api.get<{ ai_cost_inr: number }>(`/billing/documents/${documentId}/cost`),
                    api.get<Document>(`/documents/${documentId}`),
                    billingNotification.refreshBalance(),
                  ]);
                  const cost = costData?.ai_cost_inr || 0;
                  const tokens = docData?.token_count_input && docData?.token_count_output
                    ? { input: docData.token_count_input, output: docData.token_count_output }
                    : undefined;
                  billingNotification.showProcessingComplete(cost, newBalance || 0, tokens);
                } catch (err) {
                  console.error("Failed to fetch document cost:", err);
                }
              } else if (newStatus.includes("failed")) {
                billingNotification.showError(statusData.error_message || "Document processing failed");
              }

              // Reset notification flag for next run
              notifiedProcessingRef.current = false;
              fetchFullAnalysis();
            }

            previousStatusRef.current = newStatus;
          }
        } catch (e) {
          console.error(e);
        }
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [isLive, documentId, fetchFullAnalysis, billingNotification]);

  const handleRunAnalysis = async () => {
    if (!documentId) return;
    const token = localStorage.getItem("accessToken");

    // Reset notification flag when starting new analysis
    notifiedProcessingRef.current = false;

    setIsLive(true);
    setDoc((prev) =>
      prev ? { ...prev, status: "processing", progress: 0 } : null
    );
    await fetch(
      `http://localhost:8000/api/v1/documents/${documentId}/analyze`,
      { method: "POST", headers: { Authorization: `Bearer ${token}` } }
    );
  };

  const handleStopAnalysis = async () => {
    if (!documentId) return;
    const token = localStorage.getItem("accessToken");
    try {
      await fetch(`http://localhost:8000/api/v1/documents/${documentId}/stop`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      setDoc((prev) => (prev ? { ...prev, status: "stopping" } : null));
    } catch (e) {
      alert("Failed to stop");
    }
  };

  if (loading)
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="w-10 h-10 animate-spin text-blue-600" />
      </div>
    );
  if (!doc) return <div className="p-8 text-center">Document not found</div>;

  return (
    <div className="min-h-screen bg-gray-50/30 p-6 max-w-7xl mx-auto space-y-8">
      <div className="flex items-center justify-between print:hidden">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-white border border-gray-200 rounded-xl shadow-sm">
            <FileText className="w-8 h-8 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{doc.filename}</h1>
            <div className="flex items-center gap-4 mt-1 text-sm text-gray-500">
              <Badge variant="outline">{doc.document_type}</Badge>
              <span className="flex items-center">
                <GitCommit className="w-3 h-3 mr-1" /> v{doc.version}
              </span>
              <span className="flex items-center">
                <Clock className="w-3 h-3 mr-1" />{" "}
                {new Date(doc.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        </div>
        <div>
          {!isLive && (
            <Button
              onClick={handleRunAnalysis}
              className="bg-blue-600 hover:bg-blue-700 shadow-md"
            >
              {doc.status === "completed" ? (
                <RefreshCw className="w-4 h-4 mr-2" />
              ) : (
                <PlayCircle className="w-4 h-4 mr-2" />
              )}
              {doc.status === "completed"
                ? "Re-Run Analysis"
                : "Start Analysis"}
            </Button>
          )}
          <Button
            variant="ghost"
            className="text-gray-500 ml-2"
            onClick={() => window.history.back()}
          >
            <ArrowRight className="w-4 h-4 mr-2" /> Back
          </Button>
        </div>
      </div>

      <AnalysisStatusHUD doc={doc} onStop={handleStopAnalysis} />

      <Tabs defaultValue="insights" className="space-y-6">
        <TabsList className="bg-white border shadow-sm p-1 h-12 w-full justify-start print:hidden">
          <TabsTrigger
            value="insights"
            className="data-[state=active]:bg-blue-50 data-[state=active]:text-blue-700 h-10 px-6"
          >
            <Sparkles className="w-4 h-4 mr-2" /> Insights
          </TabsTrigger>
          <TabsTrigger
            value="smart"
            className="data-[state=active]:bg-gray-100 h-10 px-6"
          >
            <BrainCircuit className="w-4 h-4 mr-2" /> Detailed View
          </TabsTrigger>
          <TabsTrigger
            value="technical"
            className="data-[state=active]:bg-gray-100 h-10 px-6"
          >
            <Database className="w-4 h-4 mr-2" /> Technical
          </TabsTrigger>
          <TabsTrigger
            value="raw"
            className="data-[state=active]:bg-gray-100 h-10 px-6"
          >
            <FileCode className="w-4 h-4 mr-2" /> Raw Text
          </TabsTrigger>
        </TabsList>

        {/* Dynamic Analysis View - Adapts to Document Type & User Role */}
        <TabsContent value="insights">
          <DynamicAnalysisView segments={segments} document={doc} />
        </TabsContent>

        {/* Smart Analysis View - Detailed Structured View */}
        <TabsContent value="smart">
          <SmartAnalysisView segments={segments} document={doc} />
        </TabsContent>

        <TabsContent value="technical">
          <Card className="border-gray-200 shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center">
                <List className="w-5 h-5 mr-2" /> Segment Analysis Breakdown
              </CardTitle>
              <CardDescription>
                Detailed view of all {segments.length} identified document
                segments.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {segments.length > 0 ? (
                segments.map((item, idx) => (
                  <SegmentCard key={idx} index={idx} item={item} />
                ))
              ) : (
                <div className="text-center py-12 text-gray-400 border-2 border-dashed rounded-xl">
                  No segments found. Run analysis to populate this list.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="raw">
          <div className="bg-slate-900 text-slate-300 p-6 rounded-xl font-mono text-xs h-96 overflow-y-auto shadow-inner">
            {doc.raw_text || "No text extracted."}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
