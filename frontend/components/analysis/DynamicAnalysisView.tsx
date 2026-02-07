/**
 * DynamicAnalysisView - Intelligent, Adaptive Document Analysis UI
 *
 * This component creates a DYNAMIC view based on:
 * 1. Document Type (BRD, SRS, Compliance, Contract, Policy, API Docs, etc.)
 * 2. User Role (CXO, BA, Developer, Auditor, Product Manager, Admin)
 *
 * The UI adapts to show relevant sections and insights for each persona.
 */
"use client";

import React, { useState, useMemo } from "react";
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  Info,
  ChevronRight,
  ChevronDown,
  Search,
  Filter,
  Download,
  Copy,
  Target,
  Shield,
  Zap,
  Users,
  Scale,
  FileCheck,
  Lightbulb,
  AlertCircle,
  CheckCircle,
  XCircle,
  MinusCircle,
  HelpCircle,
  ArrowUpRight,
  Sparkles,
  Box,
  ListChecks,
  BookOpen,
  Code,
  FileCode,
  Gavel,
  ClipboardCheck,
  Building2,
  Eye,
  TrendingUp,
  Clock,
  BarChart3,
  PieChart,
  GitBranch,
  Workflow,
  Database,
  Lock,
  Unlock,
  FileWarning,
  Layers,
  Cpu,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";

// ============================================================================
// TYPES
// ============================================================================

interface AnalyzedSegment {
  segment: {
    id: number;
    segment_type: string;
    start_char_index: number;
    end_char_index: number;
  };
  analysis_result: {
    structured_data: any;
  } | null;
  status: string;
}

interface Document {
  id: number;
  filename: string;
  document_type: string;
  ai_cost_inr?: number | null;
  token_count_input?: number | null;
  token_count_output?: number | null;
  composition_analysis?: any;
}

// Document categories we can detect
type DocumentCategory =
  | "REQUIREMENTS" // BRD, PRD, User Stories
  | "TECHNICAL"    // SRS, API Docs, Technical Specs
  | "COMPLIANCE"   // Compliance docs, Policies, Regulations
  | "LEGAL"        // Contracts, Agreements, Terms
  | "PROCESS"      // Workflows, SOPs, Procedures
  | "GENERAL";     // Fallback for unclassified

// User roles
type UserRole = "CXO" | "Admin" | "BA" | "Developer" | "Product Manager" | "Auditor";

// Section types that can be shown
interface DynamicSection {
  id: string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  component: React.ComponentType<{ data: any; role: UserRole }>;
  priority: number; // Lower = higher priority
  forRoles: UserRole[]; // Which roles see this section
  forDocTypes: DocumentCategory[]; // Which doc types show this
}

// ============================================================================
// DOCUMENT TYPE DETECTION
// ============================================================================

function detectDocumentCategory(compositionAnalysis: any, filename: string): DocumentCategory {
  const composition = compositionAnalysis?.composition || {};
  const filenameLower = filename.toLowerCase();

  // Check filename patterns first
  if (filenameLower.includes("brd") || filenameLower.includes("prd") ||
      filenameLower.includes("requirement") || filenameLower.includes("user_stor")) {
    return "REQUIREMENTS";
  }
  if (filenameLower.includes("srs") || filenameLower.includes("api") ||
      filenameLower.includes("tech") || filenameLower.includes("spec")) {
    return "TECHNICAL";
  }
  if (filenameLower.includes("compliance") || filenameLower.includes("audit") ||
      filenameLower.includes("policy") || filenameLower.includes("regulation") ||
      filenameLower.includes("control") || filenameLower.includes("sox") ||
      filenameLower.includes("gdpr") || filenameLower.includes("hipaa")) {
    return "COMPLIANCE";
  }
  if (filenameLower.includes("contract") || filenameLower.includes("agreement") ||
      filenameLower.includes("terms") || filenameLower.includes("legal") ||
      filenameLower.includes("nda") || filenameLower.includes("sla")) {
    return "LEGAL";
  }
  if (filenameLower.includes("workflow") || filenameLower.includes("process") ||
      filenameLower.includes("sop") || filenameLower.includes("procedure")) {
    return "PROCESS";
  }

  // Check composition analysis
  const brdScore = (composition.BRD || 0) + (composition.REQUIREMENTS || 0);
  const srsScore = (composition.SRS || 0) + (composition.TECHNICAL || 0) + (composition.API_DOCS || 0);
  const complianceScore = (composition.COMPLIANCE || 0) + (composition.POLICY || 0);
  const legalScore = (composition.LEGAL || 0) + (composition.CONTRACT || 0);

  const scores = [
    { type: "REQUIREMENTS" as DocumentCategory, score: brdScore },
    { type: "TECHNICAL" as DocumentCategory, score: srsScore },
    { type: "COMPLIANCE" as DocumentCategory, score: complianceScore },
    { type: "LEGAL" as DocumentCategory, score: legalScore },
  ];

  const maxScore = Math.max(...scores.map(s => s.score));
  if (maxScore > 20) {
    return scores.find(s => s.score === maxScore)?.type || "GENERAL";
  }

  return "GENERAL";
}

// ============================================================================
// DATA EXTRACTION & PARSING
// ============================================================================

interface ParsedData {
  requirements: any[];
  businessRules: any[];
  technicalSpecs: any[];
  complianceControls: any[];
  legalTerms: any[];
  risks: any[];
  entities: any[];
  workflows: any[];
  testCases: any[];
  apis: any[];
  stakeholders: any[];
  summaries: string[];
  keyMetrics: { label: string; value: string | number }[];
}

function parseAllData(segments: AnalyzedSegment[]): ParsedData {
  const data: ParsedData = {
    requirements: [],
    businessRules: [],
    technicalSpecs: [],
    complianceControls: [],
    legalTerms: [],
    risks: [],
    entities: [],
    workflows: [],
    testCases: [],
    apis: [],
    stakeholders: [],
    summaries: [],
    keyMetrics: [],
  };

  let reqId = 1, ruleId = 1, controlId = 1, riskId = 1;

  segments.forEach((seg) => {
    const structured = seg.analysis_result?.structured_data;
    if (!structured) return;

    Object.entries(structured).forEach(([key, value]: [string, any]) => {
      const lowerKey = key.toLowerCase();
      const items = Array.isArray(value) ? value : [value];

      // Requirements
      if (lowerKey.includes("requirement") || lowerKey.includes("feature") ||
          lowerKey.includes("user_stor") || lowerKey.includes("capability")) {
        items.forEach((item: any) => {
          if (item && (typeof item === "string" || typeof item === "object")) {
            data.requirements.push({
              id: `REQ-${String(reqId++).padStart(3, "0")}`,
              title: typeof item === "string" ? item.slice(0, 100) : (item.title || item.name || "Requirement"),
              description: typeof item === "string" ? item : (item.description || JSON.stringify(item)),
              type: inferType(key, item),
              priority: inferPriority(item),
              source: seg.segment.segment_type,
            });
          }
        });
      }

      // Business Rules
      else if (lowerKey.includes("rule") || lowerKey.includes("policy") ||
               lowerKey.includes("constraint")) {
        items.forEach((item: any) => {
          if (item) {
            data.businessRules.push({
              id: `BR-${String(ruleId++).padStart(3, "0")}`,
              name: typeof item === "string" ? item.slice(0, 80) : (item.name || "Business Rule"),
              condition: typeof item === "object" ? (item.condition || item.if || "") : "",
              action: typeof item === "object" ? (item.action || item.then || "") : "",
              description: typeof item === "string" ? item : (item.description || ""),
              source: seg.segment.segment_type,
            });
          }
        });
      }

      // Compliance Controls
      else if (lowerKey.includes("control") || lowerKey.includes("compliance") ||
               lowerKey.includes("audit") || lowerKey.includes("regulation")) {
        items.forEach((item: any) => {
          if (item) {
            data.complianceControls.push({
              id: `CTRL-${String(controlId++).padStart(3, "0")}`,
              name: typeof item === "string" ? item.slice(0, 80) : (item.name || item.control || "Control"),
              description: typeof item === "string" ? item : (item.description || JSON.stringify(item)),
              category: typeof item === "object" ? (item.category || item.type || "General") : "General",
              status: typeof item === "object" ? (item.status || "To Review") : "To Review",
              evidence: typeof item === "object" ? (item.evidence || item.evidence_required || "") : "",
              source: seg.segment.segment_type,
            });
          }
        });
      }

      // Legal Terms
      else if (lowerKey.includes("term") || lowerKey.includes("obligation") ||
               lowerKey.includes("clause") || lowerKey.includes("agreement") ||
               lowerKey.includes("liability") || lowerKey.includes("warranty")) {
        items.forEach((item: any) => {
          if (item) {
            data.legalTerms.push({
              name: typeof item === "string" ? item.slice(0, 80) : (item.name || item.term || "Term"),
              description: typeof item === "string" ? item : (item.description || JSON.stringify(item)),
              type: lowerKey.includes("obligation") ? "Obligation" :
                    lowerKey.includes("liability") ? "Liability" :
                    lowerKey.includes("warranty") ? "Warranty" : "General",
              source: seg.segment.segment_type,
            });
          }
        });
      }

      // Risks
      else if (lowerKey.includes("risk") || lowerKey.includes("issue") ||
               lowerKey.includes("concern") || lowerKey.includes("threat")) {
        items.forEach((item: any) => {
          if (item) {
            data.risks.push({
              id: `RISK-${String(riskId++).padStart(3, "0")}`,
              title: typeof item === "string" ? item.slice(0, 80) : (item.title || item.name || "Risk"),
              description: typeof item === "string" ? item : (item.description || JSON.stringify(item)),
              severity: inferSeverity(item),
              mitigation: typeof item === "object" ? (item.mitigation || "") : "",
              source: seg.segment.segment_type,
            });
          }
        });
      }

      // Technical Specs / APIs
      else if (lowerKey.includes("api") || lowerKey.includes("endpoint") ||
               lowerKey.includes("interface") || lowerKey.includes("integration")) {
        items.forEach((item: any) => {
          if (item) {
            data.apis.push({
              name: typeof item === "string" ? item : (item.name || item.endpoint || "API"),
              method: typeof item === "object" ? (item.method || "GET") : "",
              description: typeof item === "string" ? item : (item.description || ""),
              source: seg.segment.segment_type,
            });
          }
        });
      }

      // Entities
      else if (lowerKey.includes("entit") || lowerKey.includes("actor") ||
               lowerKey.includes("stakeholder") || lowerKey.includes("definition")) {
        items.forEach((item: any) => {
          if (item) {
            const isStakeholder = lowerKey.includes("stakeholder") || lowerKey.includes("actor");
            const entry = {
              name: typeof item === "string" ? item.split(" ").slice(0, 3).join(" ") :
                    (item.name || item.term || "Entity"),
              definition: typeof item === "string" ? item : (item.definition || item.description || ""),
              type: isStakeholder ? "Stakeholder" : "Entity",
            };
            if (isStakeholder) {
              data.stakeholders.push(entry);
            } else {
              data.entities.push(entry);
            }
          }
        });
      }

      // Workflows / Processes
      else if (lowerKey.includes("workflow") || lowerKey.includes("process") ||
               lowerKey.includes("step") || lowerKey.includes("procedure")) {
        items.forEach((item: any) => {
          if (item) {
            data.workflows.push({
              name: typeof item === "string" ? item.slice(0, 80) : (item.name || "Process Step"),
              description: typeof item === "string" ? item : (item.description || ""),
              order: typeof item === "object" ? (item.order || item.step || 0) : 0,
            });
          }
        });
      }

      // Test Cases
      else if (lowerKey.includes("test") || lowerKey.includes("scenario") ||
               lowerKey.includes("acceptance")) {
        items.forEach((item: any) => {
          if (item) {
            data.testCases.push({
              name: typeof item === "string" ? item.slice(0, 80) : (item.name || item.title || "Test Case"),
              description: typeof item === "string" ? item : (item.description || ""),
              expected: typeof item === "object" ? (item.expected || item.expected_result || "") : "",
            });
          }
        });
      }

      // Summaries
      else if (lowerKey.includes("summary") || lowerKey.includes("overview") ||
               lowerKey.includes("abstract")) {
        if (typeof value === "string" && value.trim()) {
          data.summaries.push(value);
        }
      }
    });
  });

  // Calculate key metrics
  data.keyMetrics = [
    { label: "Requirements", value: data.requirements.length },
    { label: "Business Rules", value: data.businessRules.length },
    { label: "Compliance Controls", value: data.complianceControls.length },
    { label: "Risks Identified", value: data.risks.length },
  ];

  return data;
}

function inferType(key: string, item: any): string {
  const text = (key + (typeof item === "string" ? item : JSON.stringify(item))).toLowerCase();
  if (text.includes("non-functional") || text.includes("performance") || text.includes("security")) return "Non-Functional";
  if (text.includes("functional") || text.includes("shall") || text.includes("must")) return "Functional";
  if (text.includes("business")) return "Business";
  return "General";
}

function inferPriority(item: any): string {
  const text = typeof item === "string" ? item.toLowerCase() : JSON.stringify(item).toLowerCase();
  if (text.includes("critical") || text.includes("must") || text.includes("essential")) return "Critical";
  if (text.includes("high") || text.includes("important") || text.includes("should")) return "High";
  if (text.includes("medium") || text.includes("moderate")) return "Medium";
  if (text.includes("low") || text.includes("nice")) return "Low";
  return "Medium";
}

function inferSeverity(item: any): string {
  const text = typeof item === "string" ? item.toLowerCase() : JSON.stringify(item).toLowerCase();
  if (text.includes("critical") || text.includes("severe") || text.includes("blocker")) return "Critical";
  if (text.includes("high") || text.includes("major")) return "High";
  if (text.includes("medium") || text.includes("moderate")) return "Medium";
  return "Low";
}

// ============================================================================
// ROLE-SPECIFIC INSIGHTS
// ============================================================================

interface RoleInsight {
  type: "info" | "warning" | "success" | "action";
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

function generateRoleInsights(data: ParsedData, role: UserRole, docType: DocumentCategory): RoleInsight[] {
  const insights: RoleInsight[] = [];

  switch (role) {
    case "CXO":
      // Executive-level insights
      if (data.risks.filter(r => r.severity === "Critical" || r.severity === "High").length > 0) {
        insights.push({
          type: "warning",
          title: `${data.risks.filter(r => r.severity === "Critical" || r.severity === "High").length} High-Priority Risks`,
          description: "Review these risks before approving the project scope.",
          icon: AlertTriangle,
        });
      }
      if (data.requirements.filter(r => r.priority === "Critical").length > 0) {
        insights.push({
          type: "info",
          title: `${data.requirements.filter(r => r.priority === "Critical").length} Critical Requirements`,
          description: "These must be delivered for project success.",
          icon: Target,
        });
      }
      insights.push({
        type: "success",
        title: "Analysis Complete",
        description: `${data.requirements.length} requirements and ${data.businessRules.length} business rules identified.`,
        icon: CheckCircle,
      });
      break;

    case "BA":
      // BA-specific insights
      const unclearReqs = data.requirements.filter(r => r.type === "General");
      if (unclearReqs.length > 0) {
        insights.push({
          type: "action",
          title: `${unclearReqs.length} Requirements Need Classification`,
          description: "Review and categorize these as Functional, Non-Functional, or Business requirements.",
          icon: ListChecks,
        });
      }
      if (data.businessRules.length > 0) {
        insights.push({
          type: "info",
          title: `${data.businessRules.length} Business Rules Extracted`,
          description: "Validate these rules with stakeholders for accuracy.",
          icon: Scale,
        });
      }
      if (data.stakeholders.length > 0) {
        insights.push({
          type: "success",
          title: `${data.stakeholders.length} Stakeholders Identified`,
          description: "Ensure all key stakeholders are included in reviews.",
          icon: Users,
        });
      }
      break;

    case "Developer":
      // Developer-specific insights
      if (data.apis.length > 0) {
        insights.push({
          type: "info",
          title: `${data.apis.length} API Endpoints Identified`,
          description: "Review integration points and technical specifications.",
          icon: Code,
        });
      }
      if (data.testCases.length > 0) {
        insights.push({
          type: "success",
          title: `${data.testCases.length} Test Scenarios Found`,
          description: "Use these for test case development.",
          icon: FileCheck,
        });
      }
      const techReqs = data.requirements.filter(r => r.type === "Non-Functional");
      if (techReqs.length > 0) {
        insights.push({
          type: "warning",
          title: `${techReqs.length} Non-Functional Requirements`,
          description: "Consider performance, security, and scalability constraints.",
          icon: Cpu,
        });
      }
      break;

    case "Auditor":
      // Auditor-specific insights
      if (data.complianceControls.length > 0) {
        insights.push({
          type: "info",
          title: `${data.complianceControls.length} Compliance Controls`,
          description: "Review control implementation status and evidence.",
          icon: Shield,
        });
      }
      const controlsToReview = data.complianceControls.filter(c => c.status === "To Review");
      if (controlsToReview.length > 0) {
        insights.push({
          type: "action",
          title: `${controlsToReview.length} Controls Pending Review`,
          description: "These controls require audit verification.",
          icon: ClipboardCheck,
        });
      }
      if (data.risks.length > 0) {
        insights.push({
          type: "warning",
          title: `${data.risks.length} Risks for Assessment`,
          description: "Evaluate risk mitigation strategies and controls.",
          icon: AlertCircle,
        });
      }
      break;

    case "Product Manager":
      // PM-specific insights
      const features = data.requirements.filter(r => r.type === "Functional");
      if (features.length > 0) {
        insights.push({
          type: "info",
          title: `${features.length} Features Identified`,
          description: "Prioritize these for your product roadmap.",
          icon: Sparkles,
        });
      }
      if (data.stakeholders.length > 0) {
        insights.push({
          type: "success",
          title: `${data.stakeholders.length} Stakeholders`,
          description: "Key personas for your product planning.",
          icon: Users,
        });
      }
      break;

    default:
      insights.push({
        type: "success",
        title: "Analysis Complete",
        description: `Successfully extracted ${data.requirements.length} items from this document.`,
        icon: CheckCircle,
      });
  }

  return insights;
}

// ============================================================================
// SECTION COMPONENTS
// ============================================================================

// Executive Summary Section (for CXO, PM)
function ExecutiveSummarySection({ data, role }: { data: ParsedData; role: UserRole }) {
  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {data.keyMetrics.map((metric, i) => (
          <div key={i} className="bg-white rounded-xl border p-4 text-center">
            <p className="text-3xl font-bold text-gray-900">{metric.value}</p>
            <p className="text-sm text-gray-500">{metric.label}</p>
          </div>
        ))}
      </div>

      {/* Summary */}
      {data.summaries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Document Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="prose max-w-none text-gray-600">
              {data.summaries.map((s, i) => <p key={i}>{s}</p>)}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Critical Items */}
      {data.requirements.filter(r => r.priority === "Critical").length > 0 && (
        <Card className="border-red-200 bg-red-50/30">
          <CardHeader>
            <CardTitle className="text-lg text-red-800 flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              Critical Requirements
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {data.requirements.filter(r => r.priority === "Critical").map((req, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-red-700">
                  <span className="font-mono text-xs bg-red-100 px-1.5 rounded">{req.id}</span>
                  <span>{req.title}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// Requirements Section (for BA, PM, CXO)
function RequirementsSection({ data, role }: { data: ParsedData; role: UserRole }) {
  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    return data.requirements.filter(r => {
      if (filter !== "all" && r.priority !== filter) return false;
      if (search && !r.title.toLowerCase().includes(search.toLowerCase()) &&
          !r.description.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [data.requirements, filter, search]);

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            placeholder="Search requirements..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex gap-2">
          {["all", "Critical", "High", "Medium", "Low"].map(f => (
            <Button
              key={f}
              size="sm"
              variant={filter === f ? "default" : "outline"}
              onClick={() => setFilter(f)}
              className="text-xs"
            >
              {f === "all" ? "All" : f}
            </Button>
          ))}
        </div>
      </div>

      {/* Requirements List */}
      <div className="space-y-3">
        {filtered.map((req, i) => (
          <div key={i} className="bg-white border rounded-xl p-4 hover:shadow-md transition-all">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-mono text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                    {req.id}
                  </span>
                  <Badge variant="outline" className="text-xs">{req.type}</Badge>
                  <PriorityBadge priority={req.priority} />
                </div>
                <h4 className="font-medium text-gray-900">{req.title}</h4>
                <p className="text-sm text-gray-600 mt-1 line-clamp-2">{req.description}</p>
              </div>
              <Badge variant="outline" className="text-xs text-gray-500 flex-shrink-0">
                {req.source}
              </Badge>
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="text-center py-8 text-gray-500">No requirements found</div>
        )}
      </div>
    </div>
  );
}

// Compliance Matrix Section (for Auditor, CXO)
function ComplianceMatrixSection({ data, role }: { data: ParsedData; role: UserRole }) {
  const statusColors: Record<string, string> = {
    "Implemented": "bg-green-100 text-green-700",
    "In Progress": "bg-blue-100 text-blue-700",
    "To Review": "bg-amber-100 text-amber-700",
    "Not Started": "bg-gray-100 text-gray-700",
    "Non-Compliant": "bg-red-100 text-red-700",
  };

  return (
    <div className="space-y-4">
      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-green-50 rounded-lg p-4 text-center border border-green-200">
          <p className="text-2xl font-bold text-green-700">
            {data.complianceControls.filter(c => c.status === "Implemented").length}
          </p>
          <p className="text-sm text-green-600">Implemented</p>
        </div>
        <div className="bg-blue-50 rounded-lg p-4 text-center border border-blue-200">
          <p className="text-2xl font-bold text-blue-700">
            {data.complianceControls.filter(c => c.status === "In Progress").length}
          </p>
          <p className="text-sm text-blue-600">In Progress</p>
        </div>
        <div className="bg-amber-50 rounded-lg p-4 text-center border border-amber-200">
          <p className="text-2xl font-bold text-amber-700">
            {data.complianceControls.filter(c => c.status === "To Review").length}
          </p>
          <p className="text-sm text-amber-600">To Review</p>
        </div>
        <div className="bg-red-50 rounded-lg p-4 text-center border border-red-200">
          <p className="text-2xl font-bold text-red-700">
            {data.complianceControls.filter(c => c.status === "Non-Compliant").length}
          </p>
          <p className="text-sm text-red-600">Non-Compliant</p>
        </div>
      </div>

      {/* Controls List */}
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Control ID</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Control Name</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Category</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Status</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600">Evidence Required</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data.complianceControls.map((control, i) => (
              <tr key={i} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <span className="font-mono text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded">
                    {control.id}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <p className="font-medium text-gray-900">{control.name}</p>
                  <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{control.description}</p>
                </td>
                <td className="px-4 py-3">
                  <Badge variant="outline">{control.category}</Badge>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[control.status] || statusColors["To Review"]}`}>
                    {control.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {control.evidence || "Not specified"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.complianceControls.length === 0 && (
          <div className="text-center py-8 text-gray-500">No compliance controls found</div>
        )}
      </div>
    </div>
  );
}

// Technical Specs Section (for Developer)
function TechnicalSpecsSection({ data, role }: { data: ParsedData; role: UserRole }) {
  return (
    <div className="space-y-6">
      {/* APIs */}
      {data.apis.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Code className="w-5 h-5 text-blue-600" />
              API Endpoints ({data.apis.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.apis.map((api, i) => (
                <div key={i} className="bg-gray-50 rounded-lg p-3 font-mono text-sm">
                  {api.method && (
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs mr-2">
                      {api.method}
                    </span>
                  )}
                  <span className="text-gray-900">{api.name}</span>
                  {api.description && (
                    <p className="text-gray-500 text-xs mt-1 font-sans">{api.description}</p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Non-Functional Requirements */}
      {data.requirements.filter(r => r.type === "Non-Functional").length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Cpu className="w-5 h-5 text-purple-600" />
              Non-Functional Requirements
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.requirements.filter(r => r.type === "Non-Functional").map((req, i) => (
                <div key={i} className="flex items-start gap-3 p-3 bg-purple-50 rounded-lg">
                  <span className="font-mono text-xs text-purple-600">{req.id}</span>
                  <p className="text-sm text-purple-900">{req.description}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Test Cases */}
      {data.testCases.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <FileCheck className="w-5 h-5 text-green-600" />
              Test Scenarios ({data.testCases.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.testCases.map((tc, i) => (
                <div key={i} className="border rounded-lg p-3">
                  <p className="font-medium text-gray-900">{tc.name}</p>
                  {tc.description && <p className="text-sm text-gray-600 mt-1">{tc.description}</p>}
                  {tc.expected && (
                    <p className="text-sm text-green-600 mt-1">
                      <span className="font-medium">Expected:</span> {tc.expected}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// Legal Terms Section (for CXO, Auditor)
function LegalTermsSection({ data, role }: { data: ParsedData; role: UserRole }) {
  const termsByType = useMemo(() => {
    const grouped: Record<string, any[]> = {};
    data.legalTerms.forEach(term => {
      if (!grouped[term.type]) grouped[term.type] = [];
      grouped[term.type].push(term);
    });
    return grouped;
  }, [data.legalTerms]);

  return (
    <div className="space-y-4">
      {Object.entries(termsByType).map(([type, terms]) => (
        <Card key={type}>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Gavel className="w-5 h-5 text-amber-600" />
              {type}s ({terms.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {terms.map((term, i) => (
                <div key={i} className="border-l-4 border-amber-400 pl-4 py-2">
                  <p className="font-medium text-gray-900">{term.name}</p>
                  <p className="text-sm text-gray-600 mt-1">{term.description}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
      {data.legalTerms.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          <Gavel className="w-12 h-12 mx-auto mb-4 opacity-20" />
          <p>No legal terms found in this document</p>
        </div>
      )}
    </div>
  );
}

// Risk Assessment Section (for all roles)
function RiskAssessmentSection({ data, role }: { data: ParsedData; role: UserRole }) {
  const severityColors: Record<string, string> = {
    Critical: "border-l-red-500 bg-red-50",
    High: "border-l-orange-500 bg-orange-50",
    Medium: "border-l-yellow-500 bg-yellow-50",
    Low: "border-l-green-500 bg-green-50",
  };

  return (
    <div className="space-y-4">
      {/* Risk Summary */}
      <div className="grid grid-cols-4 gap-4">
        {["Critical", "High", "Medium", "Low"].map(severity => (
          <div key={severity} className={`rounded-lg p-4 text-center border ${severityColors[severity]}`}>
            <p className="text-2xl font-bold">{data.risks.filter(r => r.severity === severity).length}</p>
            <p className="text-sm">{severity}</p>
          </div>
        ))}
      </div>

      {/* Risk Cards */}
      <div className="space-y-3">
        {data.risks.map((risk, i) => (
          <div key={i} className={`border-l-4 rounded-lg p-4 ${severityColors[risk.severity]}`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-mono text-xs text-gray-600">{risk.id}</span>
                  <Badge className={`text-xs ${
                    risk.severity === "Critical" ? "bg-red-100 text-red-700" :
                    risk.severity === "High" ? "bg-orange-100 text-orange-700" :
                    risk.severity === "Medium" ? "bg-yellow-100 text-yellow-700" :
                    "bg-green-100 text-green-700"
                  }`}>
                    {risk.severity}
                  </Badge>
                </div>
                <h4 className="font-medium text-gray-900">{risk.title}</h4>
                <p className="text-sm text-gray-600 mt-1">{risk.description}</p>
                {risk.mitigation && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <p className="text-sm">
                      <span className="font-medium text-green-700">Mitigation:</span>{" "}
                      <span className="text-gray-600">{risk.mitigation}</span>
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
        {data.risks.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <Shield className="w-12 h-12 mx-auto mb-4 opacity-20" />
            <p>No risks explicitly identified</p>
            <p className="text-sm mt-1">Consider a manual risk assessment</p>
          </div>
        )}
      </div>
    </div>
  );
}

// Business Rules Section (for BA, Developer)
function BusinessRulesSection({ data, role }: { data: ParsedData; role: UserRole }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {data.businessRules.map((rule, i) => (
        <div key={i} className="bg-white border rounded-xl overflow-hidden hover:shadow-md transition-all">
          <div className="bg-gradient-to-r from-indigo-50 to-purple-50 px-4 py-3 border-b">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-indigo-600 bg-white px-2 py-0.5 rounded border border-indigo-100">
                {rule.id}
              </span>
              <span className="font-medium text-gray-900">{rule.name}</span>
            </div>
          </div>
          <div className="p-4 space-y-2">
            {rule.condition && (
              <div className="flex items-start gap-2">
                <span className="w-12 text-xs font-bold text-amber-600 bg-amber-50 rounded px-1.5 py-0.5 text-center flex-shrink-0">
                  IF
                </span>
                <p className="text-sm text-gray-700">{rule.condition}</p>
              </div>
            )}
            {rule.action && (
              <div className="flex items-start gap-2">
                <span className="w-12 text-xs font-bold text-green-600 bg-green-50 rounded px-1.5 py-0.5 text-center flex-shrink-0">
                  THEN
                </span>
                <p className="text-sm text-gray-700">{rule.action}</p>
              </div>
            )}
            {!rule.condition && !rule.action && rule.description && (
              <p className="text-sm text-gray-600">{rule.description}</p>
            )}
          </div>
        </div>
      ))}
      {data.businessRules.length === 0 && (
        <div className="col-span-2 text-center py-12 text-gray-500">
          <Scale className="w-12 h-12 mx-auto mb-4 opacity-20" />
          <p>No business rules found</p>
        </div>
      )}
    </div>
  );
}

// Entities/Glossary Section
function EntitiesSection({ data, role }: { data: ParsedData; role: UserRole }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {data.entities.map((entity, i) => (
        <div key={i} className="bg-white border rounded-lg p-4 hover:shadow-md transition-all">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-emerald-50 rounded-lg flex-shrink-0">
              <Box className="w-4 h-4 text-emerald-600" />
            </div>
            <div>
              <h4 className="font-semibold text-gray-900">{entity.name}</h4>
              <Badge variant="outline" className="text-xs mt-1">{entity.type}</Badge>
              <p className="text-sm text-gray-600 mt-2">{entity.definition}</p>
            </div>
          </div>
        </div>
      ))}
      {data.entities.length === 0 && (
        <div className="col-span-3 text-center py-12 text-gray-500">
          <Box className="w-12 h-12 mx-auto mb-4 opacity-20" />
          <p>No entities found</p>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// HELPER COMPONENTS
// ============================================================================

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    Critical: "bg-red-100 text-red-700",
    High: "bg-orange-100 text-orange-700",
    Medium: "bg-yellow-100 text-yellow-700",
    Low: "bg-green-100 text-green-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[priority] || colors.Medium}`}>
      {priority}
    </span>
  );
}

function InsightCard({ insight }: { insight: RoleInsight }) {
  const colors = {
    info: "bg-blue-50 border-blue-200 text-blue-800",
    warning: "bg-amber-50 border-amber-200 text-amber-800",
    success: "bg-green-50 border-green-200 text-green-800",
    action: "bg-purple-50 border-purple-200 text-purple-800",
  };
  const Icon = insight.icon;

  return (
    <div className={`flex items-start gap-3 p-4 rounded-lg border ${colors[insight.type]}`}>
      <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
      <div>
        <h4 className="font-semibold">{insight.title}</h4>
        <p className="text-sm opacity-80 mt-1">{insight.description}</p>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

interface DynamicAnalysisViewProps {
  segments: AnalyzedSegment[];
  document: Document;
}

export default function DynamicAnalysisView({ segments, document }: DynamicAnalysisViewProps) {
  const { user } = useAuth();

  // Detect document category
  const documentCategory = useMemo(() =>
    detectDocumentCategory(document.composition_analysis, document.filename),
    [document]
  );

  // Get user's primary role (first role in array)
  const userRole: UserRole = useMemo(() => {
    const roles = user?.roles || [];
    if (roles.includes("CXO")) return "CXO";
    if (roles.includes("Auditor")) return "Auditor";
    if (roles.includes("Admin")) return "Admin";
    if (roles.includes("BA")) return "BA";
    if (roles.includes("Developer")) return "Developer";
    if (roles.includes("Product Manager")) return "Product Manager";
    return "BA"; // Default fallback
  }, [user]);

  // Parse all data
  const parsedData = useMemo(() => parseAllData(segments), [segments]);

  // Generate role-specific insights
  const insights = useMemo(() =>
    generateRoleInsights(parsedData, userRole, documentCategory),
    [parsedData, userRole, documentCategory]
  );

  // Determine which tabs to show based on document type and role
  const availableTabs = useMemo(() => {
    const tabs: { id: string; label: string; icon: React.ComponentType<{ className?: string }> }[] = [];

    // Executive Summary - for CXO, PM, Admin
    if (["CXO", "Product Manager", "Admin"].includes(userRole)) {
      tabs.push({ id: "summary", label: "Executive Summary", icon: BarChart3 });
    }

    // Requirements - for BA, PM, CXO, Developer (if requirements exist)
    if (parsedData.requirements.length > 0) {
      tabs.push({ id: "requirements", label: "Requirements", icon: ListChecks });
    }

    // Compliance Matrix - for Auditor, CXO (if compliance doc or controls exist)
    if ((documentCategory === "COMPLIANCE" || parsedData.complianceControls.length > 0) &&
        ["Auditor", "CXO", "Admin"].includes(userRole)) {
      tabs.push({ id: "compliance", label: "Compliance Matrix", icon: Shield });
    }

    // Business Rules - for BA, Developer (if rules exist)
    if (parsedData.businessRules.length > 0 && ["BA", "Developer", "CXO"].includes(userRole)) {
      tabs.push({ id: "rules", label: "Business Rules", icon: Scale });
    }

    // Technical Specs - for Developer (if APIs or tech specs exist)
    if ((parsedData.apis.length > 0 || parsedData.testCases.length > 0) &&
        ["Developer", "CXO"].includes(userRole)) {
      tabs.push({ id: "technical", label: "Technical Specs", icon: Code });
    }

    // Legal Terms - for CXO, Auditor (if legal doc or terms exist)
    if ((documentCategory === "LEGAL" || parsedData.legalTerms.length > 0) &&
        ["CXO", "Auditor", "Admin"].includes(userRole)) {
      tabs.push({ id: "legal", label: "Legal Terms", icon: Gavel });
    }

    // Risks - for all roles (if risks exist)
    if (parsedData.risks.length > 0) {
      tabs.push({ id: "risks", label: "Risk Assessment", icon: AlertTriangle });
    }

    // Entities/Glossary - for BA, PM
    if (parsedData.entities.length > 0 && ["BA", "Product Manager", "CXO"].includes(userRole)) {
      tabs.push({ id: "entities", label: "Glossary", icon: BookOpen });
    }

    // If no specific tabs, add a general summary
    if (tabs.length === 0) {
      tabs.push({ id: "summary", label: "Summary", icon: FileText });
    }

    return tabs;
  }, [documentCategory, userRole, parsedData]);

  return (
    <div className="space-y-6">
      {/* Header with Document Type & Role Context */}
      <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl p-6 border border-blue-100">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Badge className="bg-blue-100 text-blue-700">{documentCategory}</Badge>
              <Badge variant="outline">Viewing as: {userRole}</Badge>
            </div>
            <h2 className="text-xl font-bold text-gray-900">
              Analysis Results for {userRole}
            </h2>
            <p className="text-gray-600 mt-1">
              This view is optimized for your role. Showing the most relevant insights.
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-500">Cost</p>
            <p className="text-2xl font-bold text-gray-900">
              {document.ai_cost_inr ? `₹${document.ai_cost_inr.toFixed(2)}` : "N/A"}
            </p>
          </div>
        </div>
      </div>

      {/* Role-Specific Insights */}
      {insights.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {insights.map((insight, i) => (
            <InsightCard key={i} insight={insight} />
          ))}
        </div>
      )}

      {/* Dynamic Tabs */}
      <Tabs defaultValue={availableTabs[0]?.id || "summary"} className="space-y-4">
        <TabsList className="bg-white border shadow-sm p-1 h-auto flex-wrap gap-1">
          {availableTabs.map(tab => {
            const Icon = tab.icon;
            return (
              <TabsTrigger
                key={tab.id}
                value={tab.id}
                className="data-[state=active]:bg-blue-50 data-[state=active]:text-blue-700 h-10 px-4"
              >
                <Icon className="w-4 h-4 mr-2" />
                {tab.label}
              </TabsTrigger>
            );
          })}
        </TabsList>

        <TabsContent value="summary">
          <ExecutiveSummarySection data={parsedData} role={userRole} />
        </TabsContent>

        <TabsContent value="requirements">
          <RequirementsSection data={parsedData} role={userRole} />
        </TabsContent>

        <TabsContent value="compliance">
          <ComplianceMatrixSection data={parsedData} role={userRole} />
        </TabsContent>

        <TabsContent value="rules">
          <BusinessRulesSection data={parsedData} role={userRole} />
        </TabsContent>

        <TabsContent value="technical">
          <TechnicalSpecsSection data={parsedData} role={userRole} />
        </TabsContent>

        <TabsContent value="legal">
          <LegalTermsSection data={parsedData} role={userRole} />
        </TabsContent>

        <TabsContent value="risks">
          <RiskAssessmentSection data={parsedData} role={userRole} />
        </TabsContent>

        <TabsContent value="entities">
          <EntitiesSection data={parsedData} role={userRole} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
