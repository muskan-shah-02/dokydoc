/**
 * SmartAnalysisView - Beautiful, User-Friendly Analysis Results
 *
 * Designed for: CEOs, Business Analysts, Project Managers, Auditors
 * Philosophy: Transform raw AI data into actionable, beautiful insights
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
  Bookmark,
  Tag,
  Users,
  Target,
  Zap,
  Shield,
  Clock,
  TrendingUp,
  Box,
  Layers,
  BookOpen,
  HelpCircle,
  ArrowUpRight,
  Sparkles,
  CircleDot,
  ListChecks,
  Scale,
  FileCheck,
  Building2,
  Lightbulb,
  AlertCircle,
  CheckCircle,
  XCircle,
  MinusCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

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

interface Requirement {
  id: string;
  title: string;
  description: string;
  type: "functional" | "non-functional" | "business" | "technical" | "unknown";
  priority: "critical" | "high" | "medium" | "low" | "unknown";
  status: "identified" | "validated" | "pending" | "unclear";
  source: string;
  acceptanceCriteria?: string[];
  stakeholders?: string[];
  dependencies?: string[];
}

interface BusinessRule {
  id: string;
  name: string;
  condition: string;
  action: string;
  exception?: string;
  category: string;
  source: string;
}

interface Entity {
  name: string;
  definition: string;
  context: string;
  category: string;
  aliases?: string[];
}

interface Risk {
  id: string;
  title: string;
  description: string;
  severity: "critical" | "high" | "medium" | "low";
  category: string;
  mitigation?: string;
}

interface Insight {
  type: "recommendation" | "warning" | "info" | "success";
  title: string;
  description: string;
  actionable?: boolean;
}

// ============================================================================
// SMART PARSER - Transforms raw AI data into structured format
// ============================================================================

function parseStructuredData(segments: AnalyzedSegment[]): {
  requirements: Requirement[];
  businessRules: BusinessRule[];
  entities: Entity[];
  risks: Risk[];
  insights: Insight[];
  summaries: string[];
  rawData: any[];
} {
  const requirements: Requirement[] = [];
  const businessRules: BusinessRule[] = [];
  const entities: Entity[] = [];
  const risks: Risk[] = [];
  const insights: Insight[] = [];
  const summaries: string[] = [];
  const rawData: any[] = [];

  let reqCounter = 1;
  let ruleCounter = 1;
  let riskCounter = 1;

  segments.forEach((seg, segIndex) => {
    const data = seg.analysis_result?.structured_data;
    if (!data) return;

    // Store raw data for technical view
    rawData.push({ segmentType: seg.segment.segment_type, data });

    // Smart parsing based on key patterns
    Object.entries(data).forEach(([key, value]: [string, any]) => {
      const lowerKey = key.toLowerCase();

      // === REQUIREMENTS ===
      if (lowerKey.includes("requirement") || lowerKey.includes("feature") ||
          lowerKey.includes("user_stor") || lowerKey.includes("use_case") ||
          lowerKey.includes("functional") || lowerKey.includes("capability")) {
        const items = Array.isArray(value) ? value : [value];
        items.forEach((item: any) => {
          if (typeof item === "string" && item.trim()) {
            requirements.push({
              id: `REQ-${String(reqCounter++).padStart(3, "0")}`,
              title: extractTitle(item),
              description: item,
              type: inferRequirementType(key, item),
              priority: inferPriority(item),
              status: "identified",
              source: seg.segment.segment_type,
            });
          } else if (typeof item === "object" && item !== null) {
            requirements.push({
              id: item.id || `REQ-${String(reqCounter++).padStart(3, "0")}`,
              title: item.title || item.name || extractTitle(JSON.stringify(item)),
              description: item.description || item.details || JSON.stringify(item),
              type: item.type || inferRequirementType(key, JSON.stringify(item)),
              priority: item.priority || inferPriority(JSON.stringify(item)),
              status: item.status || "identified",
              source: seg.segment.segment_type,
              acceptanceCriteria: item.acceptance_criteria || item.acceptanceCriteria,
              stakeholders: item.stakeholders,
              dependencies: item.dependencies,
            });
          }
        });
      }

      // === BUSINESS RULES ===
      else if (lowerKey.includes("rule") || lowerKey.includes("policy") ||
               lowerKey.includes("constraint") || lowerKey.includes("validation")) {
        const items = Array.isArray(value) ? value : [value];
        items.forEach((item: any) => {
          if (typeof item === "string" && item.trim()) {
            const parsed = parseRuleString(item);
            businessRules.push({
              id: `BR-${String(ruleCounter++).padStart(3, "0")}`,
              name: parsed.name,
              condition: parsed.condition,
              action: parsed.action,
              exception: parsed.exception,
              category: inferRuleCategory(item),
              source: seg.segment.segment_type,
            });
          } else if (typeof item === "object" && item !== null) {
            businessRules.push({
              id: item.id || `BR-${String(ruleCounter++).padStart(3, "0")}`,
              name: item.name || item.title || "Business Rule",
              condition: item.condition || item.if || item.when || "",
              action: item.action || item.then || item.result || "",
              exception: item.exception || item.else || item.otherwise,
              category: item.category || inferRuleCategory(JSON.stringify(item)),
              source: seg.segment.segment_type,
            });
          }
        });
      }

      // === ENTITIES / DEFINITIONS ===
      else if (lowerKey.includes("entit") || lowerKey.includes("definition") ||
               lowerKey.includes("glossary") || lowerKey.includes("term") ||
               lowerKey.includes("concept") || lowerKey.includes("actor")) {
        const items = Array.isArray(value) ? value : [value];
        items.forEach((item: any) => {
          if (typeof item === "string" && item.trim()) {
            entities.push({
              name: extractEntityName(item),
              definition: item,
              context: seg.segment.segment_type,
              category: lowerKey.includes("actor") ? "Actor" : "Concept",
            });
          } else if (typeof item === "object" && item !== null) {
            entities.push({
              name: item.name || item.term || Object.keys(item)[0] || "Entity",
              definition: item.definition || item.description || item.meaning || JSON.stringify(item),
              context: seg.segment.segment_type,
              category: item.category || item.type || "Concept",
              aliases: item.aliases || item.synonyms,
            });
          }
        });
      }

      // === RISKS ===
      else if (lowerKey.includes("risk") || lowerKey.includes("security") ||
               lowerKey.includes("compliance") || lowerKey.includes("issue") ||
               lowerKey.includes("concern") || lowerKey.includes("threat")) {
        const items = Array.isArray(value) ? value : [value];
        items.forEach((item: any) => {
          if (typeof item === "string" && item.trim()) {
            risks.push({
              id: `RISK-${String(riskCounter++).padStart(3, "0")}`,
              title: extractTitle(item),
              description: item,
              severity: inferSeverity(item),
              category: lowerKey.includes("security") ? "Security" :
                       lowerKey.includes("compliance") ? "Compliance" : "General",
            });
          } else if (typeof item === "object" && item !== null) {
            risks.push({
              id: item.id || `RISK-${String(riskCounter++).padStart(3, "0")}`,
              title: item.title || item.name || "Risk",
              description: item.description || item.details || JSON.stringify(item),
              severity: item.severity || item.level || inferSeverity(JSON.stringify(item)),
              category: item.category || "General",
              mitigation: item.mitigation || item.resolution,
            });
          }
        });
      }

      // === SUMMARIES ===
      else if (lowerKey.includes("summary") || lowerKey.includes("overview") ||
               lowerKey.includes("abstract") || lowerKey.includes("description") && !lowerKey.includes("rule")) {
        if (typeof value === "string" && value.trim()) {
          summaries.push(value);
        }
      }
    });
  });

  // Generate AI insights based on analysis
  insights.push(...generateInsights(requirements, businessRules, entities, risks));

  return { requirements, businessRules, entities, risks, insights, summaries, rawData };
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function extractTitle(text: string): string {
  // Get first sentence or first 80 chars
  const firstSentence = text.split(/[.!?]/)[0];
  return firstSentence.length > 80 ? firstSentence.substring(0, 77) + "..." : firstSentence;
}

function extractEntityName(text: string): string {
  // Try to get the first noun phrase or key term
  const words = text.split(" ").slice(0, 3);
  return words.join(" ");
}

function inferRequirementType(key: string, text: string): Requirement["type"] {
  const lower = (key + text).toLowerCase();
  if (lower.includes("non-functional") || lower.includes("nonfunctional") ||
      lower.includes("performance") || lower.includes("scalability") ||
      lower.includes("security") || lower.includes("availability")) return "non-functional";
  if (lower.includes("business") || lower.includes("stakeholder")) return "business";
  if (lower.includes("technical") || lower.includes("system") || lower.includes("api")) return "technical";
  if (lower.includes("functional") || lower.includes("feature") || lower.includes("shall")) return "functional";
  return "unknown";
}

function inferPriority(text: string): Requirement["priority"] {
  const lower = text.toLowerCase();
  if (lower.includes("critical") || lower.includes("must have") || lower.includes("essential")) return "critical";
  if (lower.includes("high") || lower.includes("important") || lower.includes("should")) return "high";
  if (lower.includes("medium") || lower.includes("moderate")) return "medium";
  if (lower.includes("low") || lower.includes("nice to have") || lower.includes("could")) return "low";
  return "medium"; // Default to medium
}

function inferSeverity(text: string): Risk["severity"] {
  const lower = text.toLowerCase();
  if (lower.includes("critical") || lower.includes("severe") || lower.includes("blocker")) return "critical";
  if (lower.includes("high") || lower.includes("major")) return "high";
  if (lower.includes("medium") || lower.includes("moderate")) return "medium";
  return "low";
}

function inferRuleCategory(text: string): string {
  const lower = text.toLowerCase();
  if (lower.includes("valid") || lower.includes("check")) return "Validation";
  if (lower.includes("auth") || lower.includes("access") || lower.includes("permission")) return "Authorization";
  if (lower.includes("calc") || lower.includes("compute") || lower.includes("formula")) return "Calculation";
  if (lower.includes("workflow") || lower.includes("process") || lower.includes("flow")) return "Workflow";
  return "Business Logic";
}

function parseRuleString(text: string): { name: string; condition: string; action: string; exception?: string } {
  // Try to parse IF-THEN-ELSE patterns
  const ifMatch = text.match(/if\s+(.+?)\s+then\s+(.+?)(?:\s+else\s+(.+))?$/i);
  if (ifMatch) {
    return {
      name: extractTitle(text),
      condition: ifMatch[1],
      action: ifMatch[2],
      exception: ifMatch[3],
    };
  }

  const whenMatch = text.match(/when\s+(.+?)[,;]\s*(.+)/i);
  if (whenMatch) {
    return {
      name: extractTitle(text),
      condition: whenMatch[1],
      action: whenMatch[2],
    };
  }

  return {
    name: extractTitle(text),
    condition: text,
    action: "",
  };
}

function generateInsights(
  requirements: Requirement[],
  rules: BusinessRule[],
  entities: Entity[],
  risks: Risk[]
): Insight[] {
  const insights: Insight[] = [];

  // Requirements insights
  const criticalReqs = requirements.filter(r => r.priority === "critical");
  if (criticalReqs.length > 0) {
    insights.push({
      type: "warning",
      title: `${criticalReqs.length} Critical Requirements Identified`,
      description: "These requirements are marked as critical and should be prioritized in your project planning.",
      actionable: true,
    });
  }

  const unclearReqs = requirements.filter(r => r.status === "unclear" || r.type === "unknown");
  if (unclearReqs.length > 0) {
    insights.push({
      type: "info",
      title: `${unclearReqs.length} Requirements Need Clarification`,
      description: "Some requirements may need further discussion with stakeholders for clarity.",
      actionable: true,
    });
  }

  // Risk insights
  const criticalRisks = risks.filter(r => r.severity === "critical" || r.severity === "high");
  if (criticalRisks.length > 0) {
    insights.push({
      type: "warning",
      title: `${criticalRisks.length} High-Priority Risks Detected`,
      description: "Review these risks and ensure mitigation strategies are in place.",
      actionable: true,
    });
  }

  // Entity insights
  if (entities.length > 10) {
    insights.push({
      type: "info",
      title: "Rich Domain Model Detected",
      description: `${entities.length} business entities identified. Consider creating a data dictionary for your team.`,
      actionable: true,
    });
  }

  // Success insights
  if (requirements.length > 0 && rules.length > 0) {
    insights.push({
      type: "success",
      title: "Comprehensive Document Analysis",
      description: `Successfully extracted ${requirements.length} requirements and ${rules.length} business rules.`,
    });
  }

  return insights;
}

// ============================================================================
// UI COMPONENTS
// ============================================================================

// Priority Badge
function PriorityBadge({ priority }: { priority: string }) {
  const config: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
    critical: { bg: "bg-red-100", text: "text-red-700", icon: <AlertCircle className="w-3 h-3" /> },
    high: { bg: "bg-orange-100", text: "text-orange-700", icon: <ArrowUpRight className="w-3 h-3" /> },
    medium: { bg: "bg-yellow-100", text: "text-yellow-700", icon: <MinusCircle className="w-3 h-3" /> },
    low: { bg: "bg-green-100", text: "text-green-700", icon: <CheckCircle className="w-3 h-3" /> },
    unknown: { bg: "bg-gray-100", text: "text-gray-600", icon: <HelpCircle className="w-3 h-3" /> },
  };
  const { bg, text, icon } = config[priority] || config.unknown;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${bg} ${text}`}>
      {icon}
      {priority.charAt(0).toUpperCase() + priority.slice(1)}
    </span>
  );
}

// Type Badge
function TypeBadge({ type }: { type: string }) {
  const config: Record<string, { bg: string; text: string }> = {
    functional: { bg: "bg-blue-100", text: "text-blue-700" },
    "non-functional": { bg: "bg-purple-100", text: "text-purple-700" },
    business: { bg: "bg-emerald-100", text: "text-emerald-700" },
    technical: { bg: "bg-slate-100", text: "text-slate-700" },
    unknown: { bg: "bg-gray-100", text: "text-gray-600" },
  };
  const { bg, text } = config[type] || config.unknown;

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${bg} ${text}`}>
      {type.charAt(0).toUpperCase() + type.slice(1).replace("-", " ")}
    </span>
  );
}

// Severity Badge
function SeverityBadge({ severity }: { severity: string }) {
  const config: Record<string, { bg: string; text: string; border: string }> = {
    critical: { bg: "bg-red-50", text: "text-red-700", border: "border-red-200" },
    high: { bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-200" },
    medium: { bg: "bg-yellow-50", text: "text-yellow-700", border: "border-yellow-200" },
    low: { bg: "bg-green-50", text: "text-green-700", border: "border-green-200" },
  };
  const { bg, text, border } = config[severity] || config.medium;

  return (
    <span className={`px-2 py-0.5 rounded border text-xs font-medium ${bg} ${text} ${border}`}>
      {severity.toUpperCase()}
    </span>
  );
}

// Requirement Card
function RequirementCard({ req, index }: { req: Requirement; index: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 hover:shadow-md transition-all duration-200 hover:border-blue-200">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-mono text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
              {req.id}
            </span>
            <TypeBadge type={req.type} />
            <PriorityBadge priority={req.priority} />
          </div>
          <h4 className="font-semibold text-gray-900 mb-1">{req.title}</h4>
          <p className={`text-sm text-gray-600 ${expanded ? "" : "line-clamp-2"}`}>
            {req.description}
          </p>

          {expanded && req.acceptanceCriteria && req.acceptanceCriteria.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <h5 className="text-xs font-semibold text-gray-500 uppercase mb-2">Acceptance Criteria</h5>
              <ul className="space-y-1">
                {req.acceptanceCriteria.map((ac, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                    <CheckCircle2 className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                    {ac}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {expanded && req.stakeholders && req.stakeholders.length > 0 && (
            <div className="mt-3 flex items-center gap-2">
              <Users className="w-4 h-4 text-gray-400" />
              <span className="text-xs text-gray-500">Stakeholders:</span>
              {req.stakeholders.map((s, i) => (
                <Badge key={i} variant="outline" className="text-xs">{s}</Badge>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-col items-end gap-2">
          <Badge variant="outline" className="text-xs text-gray-500">
            {req.source}
          </Badge>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-gray-500 h-6"
          >
            {expanded ? "Show less" : "Show more"}
            <ChevronDown className={`w-3 h-3 ml-1 transition-transform ${expanded ? "rotate-180" : ""}`} />
          </Button>
        </div>
      </div>
    </div>
  );
}

// Business Rule Card
function BusinessRuleCard({ rule }: { rule: BusinessRule }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden hover:shadow-md transition-all duration-200">
      <div className="bg-gradient-to-r from-indigo-50 to-purple-50 px-4 py-3 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-indigo-600 bg-white px-2 py-0.5 rounded border border-indigo-100">
              {rule.id}
            </span>
            <h4 className="font-semibold text-gray-900">{rule.name}</h4>
          </div>
          <Badge className="bg-indigo-100 text-indigo-700 hover:bg-indigo-100">{rule.category}</Badge>
        </div>
      </div>

      <div className="p-4 space-y-3">
        {rule.condition && (
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-12 text-xs font-bold text-amber-600 bg-amber-50 rounded px-1.5 py-0.5 text-center">
              IF
            </div>
            <p className="text-sm text-gray-700">{rule.condition}</p>
          </div>
        )}

        {rule.action && (
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-12 text-xs font-bold text-green-600 bg-green-50 rounded px-1.5 py-0.5 text-center">
              THEN
            </div>
            <p className="text-sm text-gray-700">{rule.action}</p>
          </div>
        )}

        {rule.exception && (
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-12 text-xs font-bold text-red-600 bg-red-50 rounded px-1.5 py-0.5 text-center">
              ELSE
            </div>
            <p className="text-sm text-gray-600">{rule.exception}</p>
          </div>
        )}
      </div>

      <div className="bg-gray-50 px-4 py-2 flex items-center justify-between border-t border-gray-100">
        <span className="text-xs text-gray-500">Source: {rule.source}</span>
        <Button variant="ghost" size="sm" className="h-6 text-xs">
          <Copy className="w-3 h-3 mr-1" /> Copy
        </Button>
      </div>
    </div>
  );
}

// Entity Card
function EntityCard({ entity }: { entity: Entity }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 hover:border-emerald-200 transition-all duration-200">
      <div className="flex items-start gap-3">
        <div className="p-2 bg-emerald-50 rounded-lg">
          <Box className="w-4 h-4 text-emerald-600" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-semibold text-gray-900">{entity.name}</h4>
            <Badge variant="outline" className="text-xs">{entity.category}</Badge>
          </div>
          <p className="text-sm text-gray-600">{entity.definition}</p>
          {entity.aliases && entity.aliases.length > 0 && (
            <div className="mt-2 flex items-center gap-1">
              <span className="text-xs text-gray-400">Also known as:</span>
              {entity.aliases.map((a, i) => (
                <span key={i} className="text-xs text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                  {a}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Risk Card
function RiskCard({ risk }: { risk: Risk }) {
  const severityColors = {
    critical: "border-l-red-500 bg-red-50/50",
    high: "border-l-orange-500 bg-orange-50/50",
    medium: "border-l-yellow-500 bg-yellow-50/50",
    low: "border-l-green-500 bg-green-50/50",
  };

  return (
    <div className={`border border-gray-200 border-l-4 rounded-lg p-4 ${severityColors[risk.severity]}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-mono text-gray-500">{risk.id}</span>
            <SeverityBadge severity={risk.severity} />
            <Badge variant="outline" className="text-xs">{risk.category}</Badge>
          </div>
          <h4 className="font-semibold text-gray-900 mb-1">{risk.title}</h4>
          <p className="text-sm text-gray-600">{risk.description}</p>

          {risk.mitigation && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <div className="flex items-start gap-2">
                <Shield className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                <div>
                  <span className="text-xs font-semibold text-gray-500 uppercase">Mitigation</span>
                  <p className="text-sm text-gray-600">{risk.mitigation}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Insight Card
function InsightCard({ insight }: { insight: Insight }) {
  const config = {
    recommendation: { icon: Lightbulb, bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-700" },
    warning: { icon: AlertTriangle, bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-700" },
    info: { icon: Info, bg: "bg-slate-50", border: "border-slate-200", text: "text-slate-700" },
    success: { icon: CheckCircle2, bg: "bg-green-50", border: "border-green-200", text: "text-green-700" },
  };
  const { icon: Icon, bg, border, text } = config[insight.type];

  return (
    <div className={`${bg} border ${border} rounded-lg p-4 flex items-start gap-3`}>
      <Icon className={`w-5 h-5 ${text} flex-shrink-0 mt-0.5`} />
      <div className="flex-1">
        <h4 className={`font-semibold ${text}`}>{insight.title}</h4>
        <p className="text-sm text-gray-600 mt-1">{insight.description}</p>
      </div>
      {insight.actionable && (
        <Button variant="outline" size="sm" className="flex-shrink-0">
          Take Action <ChevronRight className="w-3 h-3 ml-1" />
        </Button>
      )}
    </div>
  );
}

// Quality Score Ring
function QualityScoreRing({ score }: { score: number }) {
  const circumference = 2 * Math.PI * 40;
  const progress = (score / 100) * circumference;
  const color = score >= 80 ? "text-green-500" : score >= 60 ? "text-yellow-500" : "text-red-500";

  return (
    <div className="relative w-24 h-24">
      <svg className="w-24 h-24 transform -rotate-90">
        <circle
          cx="48"
          cy="48"
          r="40"
          stroke="currentColor"
          strokeWidth="8"
          fill="none"
          className="text-gray-200"
        />
        <circle
          cx="48"
          cy="48"
          r="40"
          stroke="currentColor"
          strokeWidth="8"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          className={color}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-2xl font-bold text-gray-900">{score}</span>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

interface SmartAnalysisViewProps {
  segments: AnalyzedSegment[];
  document: Document;
}

export default function SmartAnalysisView({ segments, document }: SmartAnalysisViewProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilters, setActiveFilters] = useState<string[]>([]);

  // Parse all structured data
  const parsed = useMemo(() => parseStructuredData(segments), [segments]);

  // Calculate quality score based on analysis completeness
  const qualityScore = useMemo(() => {
    let score = 50; // Base score
    if (parsed.requirements.length > 0) score += 15;
    if (parsed.businessRules.length > 0) score += 15;
    if (parsed.entities.length > 0) score += 10;
    if (parsed.risks.length > 0) score += 5;
    if (parsed.summaries.length > 0) score += 5;
    return Math.min(score, 100);
  }, [parsed]);

  // Filter requirements based on search
  const filteredRequirements = useMemo(() => {
    if (!searchQuery) return parsed.requirements;
    const lower = searchQuery.toLowerCase();
    return parsed.requirements.filter(
      r => r.title.toLowerCase().includes(lower) ||
           r.description.toLowerCase().includes(lower) ||
           r.id.toLowerCase().includes(lower)
    );
  }, [parsed.requirements, searchQuery]);

  return (
    <div className="space-y-6">
      {/* Hero Stats Section */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {/* Quality Score */}
        <Card className="md:col-span-1 flex flex-col items-center justify-center p-6 bg-gradient-to-br from-white to-gray-50">
          <QualityScoreRing score={qualityScore} />
          <p className="text-sm font-medium text-gray-600 mt-2">Analysis Quality</p>
        </Card>

        {/* Quick Stats */}
        <Card className="md:col-span-4 p-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-100 rounded-xl">
                <ListChecks className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{parsed.requirements.length}</p>
                <p className="text-sm text-gray-500">Requirements</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="p-3 bg-purple-100 rounded-xl">
                <Scale className="w-6 h-6 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{parsed.businessRules.length}</p>
                <p className="text-sm text-gray-500">Business Rules</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="p-3 bg-emerald-100 rounded-xl">
                <Box className="w-6 h-6 text-emerald-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{parsed.entities.length}</p>
                <p className="text-sm text-gray-500">Entities</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="p-3 bg-red-100 rounded-xl">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{parsed.risks.length}</p>
                <p className="text-sm text-gray-500">Risks Identified</p>
              </div>
            </div>
          </div>

          {/* Cost & Tokens */}
          {(document.ai_cost_inr || document.token_count_input) && (
            <div className="mt-4 pt-4 border-t border-gray-100 flex items-center gap-6 text-sm text-gray-500">
              {document.ai_cost_inr && (
                <div className="flex items-center gap-2">
                  <span className="font-medium">Analysis Cost:</span>
                  <span className="text-green-600 font-semibold">₹{document.ai_cost_inr.toFixed(2)}</span>
                </div>
              )}
              {document.token_count_input && document.token_count_output && (
                <div className="flex items-center gap-2">
                  <span className="font-medium">Tokens:</span>
                  <span>{(document.token_count_input + document.token_count_output).toLocaleString()}</span>
                  <span className="text-gray-400">
                    ({document.token_count_input.toLocaleString()} in / {document.token_count_output.toLocaleString()} out)
                  </span>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* AI Insights */}
      {parsed.insights.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-amber-500" />
              AI Insights & Recommendations
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {parsed.insights.map((insight, i) => (
              <InsightCard key={i} insight={insight} />
            ))}
          </CardContent>
        </Card>
      )}

      {/* Main Tabs */}
      <Tabs defaultValue="requirements" className="space-y-4">
        <TabsList className="bg-white border shadow-sm p-1 h-12 w-full justify-start">
          <TabsTrigger value="requirements" className="data-[state=active]:bg-blue-50 data-[state=active]:text-blue-700 h-10 px-4">
            <ListChecks className="w-4 h-4 mr-2" />
            Requirements ({parsed.requirements.length})
          </TabsTrigger>
          <TabsTrigger value="rules" className="data-[state=active]:bg-purple-50 data-[state=active]:text-purple-700 h-10 px-4">
            <Scale className="w-4 h-4 mr-2" />
            Business Rules ({parsed.businessRules.length})
          </TabsTrigger>
          <TabsTrigger value="entities" className="data-[state=active]:bg-emerald-50 data-[state=active]:text-emerald-700 h-10 px-4">
            <Box className="w-4 h-4 mr-2" />
            Entities ({parsed.entities.length})
          </TabsTrigger>
          <TabsTrigger value="risks" className="data-[state=active]:bg-red-50 data-[state=active]:text-red-700 h-10 px-4">
            <Shield className="w-4 h-4 mr-2" />
            Risks ({parsed.risks.length})
          </TabsTrigger>
          <TabsTrigger value="summary" className="data-[state=active]:bg-gray-100 h-10 px-4">
            <FileText className="w-4 h-4 mr-2" />
            Executive Summary
          </TabsTrigger>
        </TabsList>

        {/* Requirements Tab */}
        <TabsContent value="requirements">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Extracted Requirements</CardTitle>
                  <CardDescription>
                    All functional, non-functional, and business requirements identified in the document
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      placeholder="Search requirements..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-9 w-64"
                    />
                  </div>
                  <Button variant="outline" size="sm">
                    <Filter className="w-4 h-4 mr-2" /> Filter
                  </Button>
                  <Button variant="outline" size="sm">
                    <Download className="w-4 h-4 mr-2" /> Export
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {filteredRequirements.length > 0 ? (
                <div className="space-y-3">
                  {filteredRequirements.map((req, i) => (
                    <RequirementCard key={req.id} req={req} index={i} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 text-gray-400">
                  <ListChecks className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p>No requirements found in this document.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Business Rules Tab */}
        <TabsContent value="rules">
          <Card>
            <CardHeader>
              <CardTitle>Business Rules & Policies</CardTitle>
              <CardDescription>
                Validation rules, constraints, and business logic extracted from the document
              </CardDescription>
            </CardHeader>
            <CardContent>
              {parsed.businessRules.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {parsed.businessRules.map((rule) => (
                    <BusinessRuleCard key={rule.id} rule={rule} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 text-gray-400">
                  <Scale className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p>No business rules found in this document.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Entities Tab */}
        <TabsContent value="entities">
          <Card>
            <CardHeader>
              <CardTitle>Entities & Definitions</CardTitle>
              <CardDescription>
                Business terms, actors, and concepts identified in the document - your project glossary
              </CardDescription>
            </CardHeader>
            <CardContent>
              {parsed.entities.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {parsed.entities.map((entity, i) => (
                    <EntityCard key={i} entity={entity} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 text-gray-400">
                  <Box className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p>No entities found in this document.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Risks Tab */}
        <TabsContent value="risks">
          <Card>
            <CardHeader>
              <CardTitle>Risks & Compliance</CardTitle>
              <CardDescription>
                Security concerns, compliance requirements, and potential risks identified
              </CardDescription>
            </CardHeader>
            <CardContent>
              {parsed.risks.length > 0 ? (
                <div className="space-y-4">
                  {parsed.risks.map((risk) => (
                    <RiskCard key={risk.id} risk={risk} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 text-gray-400">
                  <Shield className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p className="mb-2">No explicit risks identified in this document.</p>
                  <p className="text-sm">This doesn&apos;t mean there are no risks - consider a manual review.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Executive Summary Tab */}
        <TabsContent value="summary">
          <Card>
            <CardHeader>
              <CardTitle>Executive Summary</CardTitle>
              <CardDescription>
                High-level overview for stakeholders and decision makers
              </CardDescription>
            </CardHeader>
            <CardContent className="prose max-w-none">
              {parsed.summaries.length > 0 ? (
                <div className="space-y-4">
                  {parsed.summaries.map((summary, i) => (
                    <p key={i} className="text-gray-700 leading-relaxed">{summary}</p>
                  ))}
                </div>
              ) : (
                <div className="bg-gray-50 rounded-xl p-6">
                  <h3 className="font-semibold text-gray-900 mb-4">Document Analysis Overview</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-white rounded-lg p-4 text-center border">
                      <p className="text-3xl font-bold text-blue-600">{parsed.requirements.length}</p>
                      <p className="text-sm text-gray-500">Requirements</p>
                    </div>
                    <div className="bg-white rounded-lg p-4 text-center border">
                      <p className="text-3xl font-bold text-purple-600">{parsed.businessRules.length}</p>
                      <p className="text-sm text-gray-500">Business Rules</p>
                    </div>
                    <div className="bg-white rounded-lg p-4 text-center border">
                      <p className="text-3xl font-bold text-emerald-600">{parsed.entities.length}</p>
                      <p className="text-sm text-gray-500">Entities</p>
                    </div>
                    <div className="bg-white rounded-lg p-4 text-center border">
                      <p className="text-3xl font-bold text-red-600">{parsed.risks.length}</p>
                      <p className="text-sm text-gray-500">Risks</p>
                    </div>
                  </div>

                  {parsed.requirements.filter(r => r.priority === "critical").length > 0 && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                      <h4 className="font-semibold text-red-800 mb-2">Critical Requirements</h4>
                      <ul className="space-y-1">
                        {parsed.requirements.filter(r => r.priority === "critical").map(r => (
                          <li key={r.id} className="text-sm text-red-700 flex items-center gap-2">
                            <span className="font-mono">{r.id}</span> - {r.title}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {parsed.risks.filter(r => r.severity === "critical" || r.severity === "high").length > 0 && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                      <h4 className="font-semibold text-amber-800 mb-2">High-Priority Risks</h4>
                      <ul className="space-y-1">
                        {parsed.risks.filter(r => r.severity === "critical" || r.severity === "high").map(r => (
                          <li key={r.id} className="text-sm text-amber-700 flex items-center gap-2">
                            <SeverityBadge severity={r.severity} /> {r.title}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
