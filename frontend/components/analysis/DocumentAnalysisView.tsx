"use client";

/**
 * SPRINT 3: DocumentAnalysisView (UI-DOC-01/02/03)
 *
 * Rich renderer for document analysis results. Replaces raw JSON display
 * with structured, type-specific renderers for BRD, Tech Spec, and generic segments.
 * Integrates with the 3-pass DAE pipeline output.
 */

import { useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  FileText,
  ChevronDown,
  ChevronRight,
  CheckCircle,
  AlertTriangle,
  Layers,
  List,
  BookOpen,
  Shield,
  Target,
  Lightbulb,
  Copy,
  Download,
  Zap,
  Network,
  Code,
  Info,
  Star,
  Database,
} from "lucide-react";

// --- Types ---
interface AnalyzedSegment {
  segment: {
    id: number;
    segment_type: string;
    start_char_index: number;
    end_char_index: number;
  };
  analysis_result: {
    id: number;
    structured_data: any;
  } | null;
  status: "analyzed" | "pending" | "failed";
}

interface DocumentAnalysisViewProps {
  segments: AnalyzedSegment[];
  documentType?: string;
  filename?: string;
}

// --- Segment type detection ---
const getSegmentCategory = (segmentType: string): "brd" | "api" | "generic" => {
  const lower = segmentType.toLowerCase();
  if (
    lower.includes("requirement") ||
    lower.includes("brd") ||
    lower.includes("business_rule") ||
    lower.includes("functional") ||
    lower.includes("user_story") ||
    lower.includes("acceptance")
  ) {
    return "brd";
  }
  if (
    lower.includes("api") ||
    lower.includes("endpoint") ||
    lower.includes("technical") ||
    lower.includes("architecture") ||
    lower.includes("data_model") ||
    lower.includes("interface")
  ) {
    return "api";
  }
  return "generic";
};

// --- Segment type badge color ---
const getSegmentColor = (segmentType: string) => {
  const category = getSegmentCategory(segmentType);
  switch (category) {
    case "brd":
      return "bg-blue-100 text-blue-800 border-blue-200";
    case "api":
      return "bg-purple-100 text-purple-800 border-purple-200";
    default:
      return "bg-gray-100 text-gray-800 border-gray-200";
  }
};

const getSegmentIcon = (segmentType: string) => {
  const category = getSegmentCategory(segmentType);
  switch (category) {
    case "brd":
      return BookOpen;
    case "api":
      return Code;
    default:
      return FileText;
  }
};

// ============================================================
// BRD RENDERER — Requirements tables
// ============================================================
const BRDRenderer = ({ data }: { data: any }) => {
  // Extract requirements from various possible structures
  const requirements =
    data.requirements ||
    data.functional_requirements ||
    data.user_stories ||
    data.business_rules ||
    [];
  const nonFunctional = data.non_functional_requirements || [];
  const stakeholders = data.stakeholders || data.actors || [];

  return (
    <div className="space-y-4">
      {/* Requirements Table */}
      {Array.isArray(requirements) && requirements.length > 0 && (
        <div>
          <h4 className="font-semibold text-sm flex items-center mb-2">
            <Target className="w-4 h-4 mr-2 text-blue-500" />
            Requirements ({requirements.length})
          </h4>
          <div className="border rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/50">
                  <TableHead className="w-[80px]">ID</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead className="w-[100px]">Priority</TableHead>
                  <TableHead className="w-[100px]">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {requirements.map((req: any, i: number) => (
                  <TableRow key={i}>
                    <TableCell className="font-mono text-xs">
                      {req.id || req.requirement_id || `REQ-${i + 1}`}
                    </TableCell>
                    <TableCell className="text-sm">
                      {typeof req === "string"
                        ? req
                        : req.description || req.text || req.name || JSON.stringify(req)}
                    </TableCell>
                    <TableCell>
                      <PriorityBadge
                        priority={req.priority || req.importance || "Medium"}
                      />
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">
                        {req.status || "Identified"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Non-functional Requirements */}
      {Array.isArray(nonFunctional) && nonFunctional.length > 0 && (
        <div>
          <h4 className="font-semibold text-sm flex items-center mb-2">
            <Shield className="w-4 h-4 mr-2 text-green-500" />
            Non-Functional Requirements ({nonFunctional.length})
          </h4>
          <div className="grid gap-2">
            {nonFunctional.map((nfr: any, i: number) => (
              <div
                key={i}
                className="p-3 bg-green-50 border border-green-100 rounded-lg text-sm"
              >
                {typeof nfr === "string" ? nfr : nfr.description || JSON.stringify(nfr)}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stakeholders */}
      {Array.isArray(stakeholders) && stakeholders.length > 0 && (
        <div>
          <h4 className="font-semibold text-sm flex items-center mb-2">
            <Star className="w-4 h-4 mr-2 text-yellow-500" />
            Stakeholders/Actors
          </h4>
          <div className="flex flex-wrap gap-2">
            {stakeholders.map((s: any, i: number) => (
              <Badge key={i} variant="secondary">
                {typeof s === "string" ? s : s.name || s.role || JSON.stringify(s)}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Fallback for unstructured data */}
      <GenericKeyValueRenderer data={data} exclude={[
        "requirements", "functional_requirements", "user_stories",
        "business_rules", "non_functional_requirements", "stakeholders", "actors"
      ]} />
    </div>
  );
};

// ============================================================
// API / TECH SPEC RENDERER — Endpoints, data models
// ============================================================
const APIRenderer = ({ data }: { data: any }) => {
  const endpoints =
    data.endpoints || data.api_endpoints || data.routes || [];
  const dataModels =
    data.data_models || data.schemas || data.entities || [];
  const architecture = data.architecture || data.system_design || null;

  return (
    <div className="space-y-4">
      {/* Endpoints */}
      {Array.isArray(endpoints) && endpoints.length > 0 && (
        <div>
          <h4 className="font-semibold text-sm flex items-center mb-2">
            <Network className="w-4 h-4 mr-2 text-purple-500" />
            API Endpoints ({endpoints.length})
          </h4>
          <div className="space-y-2">
            {endpoints.map((ep: any, i: number) => (
              <div
                key={i}
                className="p-3 border rounded-lg bg-purple-50/50 border-purple-100"
              >
                <div className="flex items-center gap-2 mb-1">
                  <MethodBadge method={ep.method || "GET"} />
                  <span className="font-mono text-sm font-semibold">
                    {ep.path || ep.url || ep.endpoint || "N/A"}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground">
                  {ep.description || ep.purpose || ep.summary || ""}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data Models */}
      {Array.isArray(dataModels) && dataModels.length > 0 && (
        <div>
          <h4 className="font-semibold text-sm flex items-center mb-2">
            <Database className="w-4 h-4 mr-2 text-teal-500" />
            Data Models ({dataModels.length})
          </h4>
          <div className="grid gap-2">
            {dataModels.map((model: any, i: number) => (
              <div
                key={i}
                className="p-3 border rounded-lg bg-teal-50/50 border-teal-100"
              >
                <span className="font-semibold text-sm">
                  {typeof model === "string"
                    ? model
                    : model.name || model.entity || `Model ${i + 1}`}
                </span>
                {model.fields && Array.isArray(model.fields) && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {model.fields.map((f: any, j: number) => (
                      <Badge key={j} variant="outline" className="text-xs font-mono">
                        {typeof f === "string" ? f : f.name || JSON.stringify(f)}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Architecture notes */}
      {architecture && (
        <div>
          <h4 className="font-semibold text-sm flex items-center mb-2">
            <Layers className="w-4 h-4 mr-2 text-indigo-500" />
            Architecture
          </h4>
          <div className="p-3 bg-indigo-50/50 border border-indigo-100 rounded-lg text-sm">
            {typeof architecture === "string"
              ? architecture
              : JSON.stringify(architecture, null, 2)}
          </div>
        </div>
      )}

      <GenericKeyValueRenderer data={data} exclude={[
        "endpoints", "api_endpoints", "routes", "data_models",
        "schemas", "entities", "architecture", "system_design"
      ]} />
    </div>
  );
};

// ============================================================
// GENERIC KEY-VALUE RENDERER — Fallback for any segment type
// ============================================================
const GenericKeyValueRenderer = ({
  data,
  exclude = [],
}: {
  data: any;
  exclude?: string[];
}) => {
  if (!data || typeof data !== "object") return null;

  const entries = Object.entries(data).filter(
    ([key]) => !exclude.includes(key)
  );

  if (entries.length === 0) return null;

  return (
    <div className="space-y-2">
      {entries.map(([key, value]) => (
        <div key={key} className="text-sm">
          <span className="font-medium text-muted-foreground capitalize">
            {key.replace(/_/g, " ")}:
          </span>{" "}
          {renderValue(value)}
        </div>
      ))}
    </div>
  );
};

// ============================================================
// UTILITY COMPONENTS
// ============================================================

const PriorityBadge = ({ priority }: { priority: string }) => {
  const p = String(priority).toLowerCase();
  if (p.includes("high") || p.includes("critical")) {
    return (
      <Badge variant="destructive" className="text-xs">
        {priority}
      </Badge>
    );
  }
  if (p.includes("medium") || p.includes("moderate")) {
    return (
      <Badge variant="default" className="text-xs">
        {priority}
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="text-xs">
      {priority}
    </Badge>
  );
};

const MethodBadge = ({ method }: { method: string }) => {
  const m = method.toUpperCase();
  const colors: Record<string, string> = {
    GET: "bg-green-100 text-green-800",
    POST: "bg-blue-100 text-blue-800",
    PUT: "bg-yellow-100 text-yellow-800",
    PATCH: "bg-orange-100 text-orange-800",
    DELETE: "bg-red-100 text-red-800",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${
        colors[m] || "bg-gray-100 text-gray-800"
      }`}
    >
      {m}
    </span>
  );
};

const renderValue = (value: any): React.ReactNode => {
  if (value === null || value === undefined) return <span className="text-muted-foreground italic">N/A</span>;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-muted-foreground italic">Empty</span>;
    if (typeof value[0] === "string") {
      return (
        <span className="inline-flex flex-wrap gap-1">
          {value.map((v, i) => (
            <Badge key={i} variant="outline" className="text-xs">
              {v}
            </Badge>
          ))}
        </span>
      );
    }
    return (
      <span className="text-muted-foreground">
        [{value.length} items]
      </span>
    );
  }
  if (typeof value === "object") {
    return (
      <span className="text-muted-foreground">
        {JSON.stringify(value).substring(0, 100)}...
      </span>
    );
  }
  return String(value);
};

// ============================================================
// MAIN COMPONENT
// ============================================================
export function DocumentAnalysisView({
  segments,
  documentType,
  filename,
}: DocumentAnalysisViewProps) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  if (!segments || segments.length === 0) {
    return (
      <Alert>
        <FileText className="h-4 w-4" />
        <AlertDescription>
          No analysis segments available for this document.
        </AlertDescription>
      </Alert>
    );
  }

  const analyzedCount = segments.filter((s) => s.status === "analyzed").length;
  const failedCount = segments.filter((s) => s.status === "failed").length;

  const handleCopyJSON = (data: any, index: number) => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div className="space-y-4">
      {/* Summary Bar */}
      <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
        <div className="flex items-center gap-4 text-sm">
          <span className="flex items-center gap-1">
            <Layers className="w-4 h-4 text-muted-foreground" />
            {segments.length} segments
          </span>
          <span className="flex items-center gap-1 text-green-600">
            <CheckCircle className="w-4 h-4" />
            {analyzedCount} analyzed
          </span>
          {failedCount > 0 && (
            <span className="flex items-center gap-1 text-red-600">
              <AlertTriangle className="w-4 h-4" />
              {failedCount} failed
            </span>
          )}
        </div>
        {documentType && (
          <Badge variant="outline">{documentType}</Badge>
        )}
      </div>

      {/* Segment Cards */}
      {segments.map((seg, index) => {
        const Icon = getSegmentIcon(seg.segment.segment_type);
        const category = getSegmentCategory(seg.segment.segment_type);
        const structuredData = seg.analysis_result?.structured_data;

        return (
          <Collapsible key={seg.segment.id} defaultOpen={index < 3}>
            <Card>
              <CollapsibleTrigger asChild>
                <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors">
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center text-base">
                      <Icon className="w-5 h-5 mr-2 text-muted-foreground" />
                      <span className="capitalize">
                        {seg.segment.segment_type.replace(/_/g, " ")}
                      </span>
                      <Badge
                        variant="outline"
                        className={`ml-2 text-xs ${getSegmentColor(
                          seg.segment.segment_type
                        )}`}
                      >
                        {category.toUpperCase()}
                      </Badge>
                    </CardTitle>
                    <div className="flex items-center gap-2">
                      {seg.status === "analyzed" && (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      )}
                      {seg.status === "failed" && (
                        <AlertTriangle className="w-4 h-4 text-red-500" />
                      )}
                      {seg.status === "pending" && (
                        <Info className="w-4 h-4 text-yellow-500" />
                      )}
                      <ChevronDown className="w-4 h-4" />
                    </div>
                  </div>
                </CardHeader>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <CardContent>
                  {seg.status === "failed" && (
                    <Alert variant="destructive" className="mb-4">
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription>
                        Analysis failed for this segment.
                      </AlertDescription>
                    </Alert>
                  )}

                  {seg.status === "pending" && (
                    <div className="text-center py-6 text-muted-foreground">
                      Analysis pending...
                    </div>
                  )}

                  {structuredData && (
                    <div>
                      {/* Type-specific renderer */}
                      {category === "brd" && (
                        <BRDRenderer data={structuredData} />
                      )}
                      {category === "api" && (
                        <APIRenderer data={structuredData} />
                      )}
                      {category === "generic" && (
                        <GenericKeyValueRenderer data={structuredData} />
                      )}

                      {/* Actions */}
                      <div className="flex gap-2 mt-4 pt-3 border-t">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            handleCopyJSON(structuredData, index)
                          }
                        >
                          {copiedIndex === index ? (
                            <>
                              <CheckCircle className="w-3 h-3 mr-1" />
                              Copied
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3 mr-1" />
                              Copy JSON
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </CollapsibleContent>
            </Card>
          </Collapsible>
        );
      })}
    </div>
  );
}
