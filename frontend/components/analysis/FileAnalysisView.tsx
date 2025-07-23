// This is the updated content for your file at:
// frontend/components/analysis/FileAnalysisView.tsx

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  FileText,
  Code,
  AlertTriangle,
  Lightbulb,
  Book,
  Boxes,
  Network,
  ShieldCheck,
  ChevronDown,
  ChevronRight,
  Star,
  CheckCircle,
  XCircle,
  Info,
  Package,
  Zap,
  Eye,
  Settings,
  ArrowRight,
  Home,
} from "lucide-react";
import { useState } from "react";

// Define a more specific type for the Function icon, if needed. For now, we'll use a generic name.
const FunctionIcon = Code;

interface FileAnalysisViewProps {
  analysis: any; // The structured_analysis object from our API
  isLoading?: boolean;
  fileName?: string;
}

interface FunctionInfo {
  name: string;
  purpose: string;
  parameters?: string[];
  return_type?: string;
  complexity?: string;
  visibility?: string;
}

interface ClassInfo {
  name: string;
  purpose: string;
  methods?: string[];
  inheritance?: string;
  properties?: string[];
}

interface ImportInfo {
  standard_library?: string[];
  third_party?: string[];
  local?: string[];
}

interface CodeQualityInfo {
  architecture_notes?: string;
  patterns?: string[];
  potential_issues?: string[];
  maintainability_score?: number;
  complexity_score?: number;
}

const Section = ({
  title,
  icon: Icon,
  children,
  collapsible = false,
  defaultOpen = true,
  count,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
  count?: number;
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  if (collapsible) {
    return (
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger className="flex items-center justify-between w-full p-3 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors">
          <div className="flex items-center">
            <Icon className="w-5 h-5 mr-3 text-muted-foreground" />
            <h3 className="font-semibold text-lg">{title}</h3>
            {count !== undefined && (
              <Badge variant="outline" className="ml-2">
                {count}
              </Badge>
            )}
          </div>
          {isOpen ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-4 pl-8 space-y-4">
          {children}
        </CollapsibleContent>
      </Collapsible>
    );
  }
  return (
    <div>
      <h3 className="font-semibold mb-3 flex items-center text-lg">
        <Icon className="w-5 h-5 mr-3 text-muted-foreground" />
        {title}
        {count !== undefined && (
          <Badge variant="outline" className="ml-2">
            {count}
          </Badge>
        )}
      </h3>
      <div className="pl-8 space-y-4">{children}</div>
    </div>
  );
};

const DetailItem = ({
  title,
  content,
  icon: Icon,
}: {
  title: string;
  content: string | string[] | undefined;
  icon?: React.ElementType;
}) => (
  <div className="space-y-1">
    <h4 className="font-medium text-sm flex items-center">
      {Icon && <Icon className="w-3 h-3 mr-1 text-muted-foreground" />}
      {title}
    </h4>
    {Array.isArray(content) ? (
      <div className="flex flex-wrap gap-1">
        {content.length > 0 ? (
          content.map((item, i) => (
            <Badge key={i} variant="secondary" className="text-xs">
              {item}
            </Badge>
          ))
        ) : (
          <span className="text-xs text-muted-foreground italic">
            None specified
          </span>
        )}
      </div>
    ) : (
      <p className="text-sm text-muted-foreground leading-relaxed">
        {content || "Not specified"}
      </p>
    )}
  </div>
);

const QualityIndicator = ({
  score,
  label,
}: {
  score?: number;
  label: string;
}) => {
  if (score === undefined) return null;
  const getColor = (score: number) => {
    if (score >= 8) return "text-green-600 bg-green-100";
    if (score >= 6) return "text-yellow-600 bg-yellow-100";
    return "text-red-600 bg-red-100";
  };
  const getIcon = (score: number) => {
    if (score >= 8) return CheckCircle;
    if (score >= 6) return Info;
    return XCircle;
  };
  const IconComponent = getIcon(score);
  return (
    <div className="flex items-center justify-between p-2 rounded-md bg-muted/30">
      <span className="text-sm font-medium flex items-center">
        <IconComponent className="w-4 h-4 mr-2" />
        {label}
      </span>
      <div className="flex items-center gap-2">
        <div className="w-20 bg-muted rounded-full h-2">
          <div
            className={`h-2 rounded-full ${getColor(score)}`}
            style={{ width: `${(score / 10) * 100}%` }}
          />
        </div>
        <span className={`text-sm px-2 py-1 rounded-md ${getColor(score)}`}>
          {score}/10
        </span>
      </div>
    </div>
  );
};

const ImportTypeIcon = ({ type }: { type: string }) => {
  switch (type) {
    case "standard_library":
      return <Book className="w-4 h-4 text-blue-500" />;
    case "third_party":
      return <Package className="w-4 h-4 text-green-500" />;
    case "local":
      return <Home className="w-4 h-4 text-orange-500" />;
    default:
      return <Network className="w-4 h-4 text-muted-foreground" />;
  }
};

export function FileAnalysisView({
  analysis,
  isLoading = false,
  fileName,
}: FileAnalysisViewProps) {
  if (isLoading) {
    return (
      <div className="space-y-6">
        <Card className="animate-pulse">
          <CardHeader>
            <div className="h-6 bg-muted rounded w-1/2"></div>
            <div className="h-4 bg-muted rounded w-3/4"></div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="space-y-2">
                  <div className="h-4 bg-muted rounded w-1/3"></div>
                  <div className="h-8 bg-muted rounded"></div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!analysis || analysis.error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          The AI analysis for this file could not be completed.
          {analysis?.error && (
            <span className="block mt-1 text-sm">
              Error details: {analysis.error}
            </span>
          )}
        </AlertDescription>
      </Alert>
    );
  }

  const {
    functions = [],
    classes = [],
    imports = {} as ImportInfo,
    code_quality = {} as CodeQualityInfo,
    file_stats,
    analysis_timestamp,
  } = analysis;

  const totalImports =
    (imports.standard_library?.length || 0) +
    (imports.third_party?.length || 0) +
    (imports.local?.length || 0);

  return (
    <div className="space-y-6">
      {(fileName || analysis_timestamp) && (
        <Alert>
          <FileText className="h-4 w-4" />
          <AlertDescription>
            Analysis of {fileName || "file"}
            {analysis_timestamp && (
              <span>
                {" "}
                completed on {new Date(analysis_timestamp).toLocaleDateString()}
              </span>
            )}
          </AlertDescription>
        </Alert>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Code className="w-5 h-5 mr-3 text-blue-600" />
                Code Structure Analysis
              </CardTitle>
              <CardDescription>
                Functions, classes, and structural components identified in the
                file
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <Section
                title="Functions"
                icon={FunctionIcon}
                collapsible={functions.length > 3}
                count={functions.length}
              >
                {functions.length > 0 ? (
                  functions.map((func: FunctionInfo, index: number) => (
                    <div
                      key={index}
                      className="p-4 bg-gradient-to-r from-blue-50 to-blue-50/50 border border-blue-100 rounded-lg"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-semibold text-blue-700 flex items-center">
                          <FunctionIcon className="w-4 h-4 mr-2" />
                          {func.name}
                        </h4>
                        {func.visibility && (
                          <Badge
                            variant={
                              func.visibility === "public"
                                ? "default"
                                : "secondary"
                            }
                          >
                            {func.visibility}
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mb-3 leading-relaxed">
                        {func.purpose}
                      </p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                        <DetailItem
                          title="Parameters"
                          content={func.parameters}
                          icon={ArrowRight}
                        />
                        <DetailItem
                          title="Returns"
                          content={func.return_type}
                          icon={Eye}
                        />
                      </div>
                      {func.complexity && (
                        <div className="mt-2 pt-2 border-t border-blue-200">
                          <Badge variant="outline" className="text-xs">
                            Complexity: {func.complexity}
                          </Badge>
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground italic">
                    No functions identified in this file.
                  </p>
                )}
              </Section>
              <Section
                title="Classes"
                icon={Boxes}
                collapsible={classes.length > 3}
                count={classes.length}
              >
                {classes.length > 0 ? (
                  classes.map((cls: ClassInfo, index: number) => (
                    <div
                      key={index}
                      className="p-4 bg-gradient-to-r from-green-50 to-green-50/50 border border-green-100 rounded-lg"
                    >
                      <h4 className="font-semibold text-green-700 flex items-center mb-2">
                        <Boxes className="w-4 h-4 mr-2" />
                        {cls.name}
                      </h4>
                      <p className="text-sm text-muted-foreground mb-3 leading-relaxed">
                        {cls.purpose}
                      </p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                        <DetailItem
                          title="Methods"
                          content={cls.methods}
                          icon={FunctionIcon}
                        />
                        <DetailItem
                          title="Inheritance"
                          content={cls.inheritance || "None"}
                          icon={ArrowRight}
                        />
                      </div>
                      {cls.properties && cls.properties.length > 0 && (
                        <div className="mt-3 pt-2 border-t border-green-200">
                          <DetailItem
                            title="Properties"
                            content={cls.properties}
                            icon={Settings}
                          />
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground italic">
                    No classes identified in this file.
                  </p>
                )}
              </Section>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Network className="w-5 h-5 mr-3 text-purple-600" />
                Dependencies & Imports
              </CardTitle>
              <CardDescription>
                External libraries and internal modules used by this file
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {Object.entries(imports).map(([type, items]) => {
                // Fix: Ensure items is an array before accessing length
                const itemsArray = Array.isArray(items) ? items : [];
                return (
                  <div key={type} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="font-medium text-sm flex items-center">
                        <ImportTypeIcon type={type} />
                        <span className="ml-2 capitalize">
                          {type.replace("_", " ")}
                        </span>
                      </h4>
                      <Badge variant="outline">{itemsArray.length}</Badge>
                    </div>
                    <div className="flex flex-wrap gap-1 pl-6">
                      {itemsArray.length > 0 ? (
                        itemsArray.map((item: string, i: number) => (
                          <Badge
                            key={i}
                            variant="secondary"
                            className="text-xs"
                          >
                            {item}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-xs text-muted-foreground italic">
                          None
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </div>
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <ShieldCheck className="w-5 h-5 mr-3 text-green-600" />
                Quality Assessment
              </CardTitle>
              <CardDescription>
                Code quality metrics and architectural analysis
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <QualityIndicator
                score={code_quality.maintainability_score}
                label="Maintainability"
              />
              <QualityIndicator
                score={code_quality.complexity_score}
                label="Complexity"
              />
              {code_quality.architecture_notes && (
                <div className="p-3 bg-muted/30 rounded-lg">
                  <h4 className="font-semibold mb-2 flex items-center text-sm">
                    <Lightbulb className="w-4 h-4 mr-2 text-yellow-500" />
                    Architecture Notes
                  </h4>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {code_quality.architecture_notes}
                  </p>
                </div>
              )}
              {code_quality.patterns && code_quality.patterns.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-2 flex items-center text-sm">
                    <Star className="w-4 h-4 mr-2 text-blue-500" />
                    Design Patterns
                  </h4>
                  <div className="flex flex-wrap gap-1">
                    {code_quality.patterns.map((pattern: string, i: number) => (
                      <Badge key={i} variant="default" className="text-xs">
                        {pattern}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {code_quality.potential_issues &&
                Array.isArray(code_quality.potential_issues) &&
                code_quality.potential_issues.length > 0 && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                    <h4 className="font-semibold mb-2 flex items-center text-sm text-red-700">
                      <AlertTriangle className="w-4 h-4 mr-2" />
                      Potential Issues
                    </h4>
                    <div className="space-y-1">
                      {code_quality.potential_issues.map(
                        (issue: string, i: number) => (
                          <div
                            key={i}
                            className="text-sm text-red-600 flex items-start"
                          >
                            <span className="text-red-400 mr-2">•</span>
                            <span>{issue}</span>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                )}
            </CardContent>
          </Card>
          {(functions.length > 0 || classes.length > 0 || totalImports > 0) && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Zap className="w-5 h-5 mr-3 text-orange-500" />
                  Quick Stats
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Functions</span>
                  <Badge variant="outline">{functions.length}</Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Classes</span>
                  <Badge variant="outline">{classes.length}</Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Imports</span>
                  <Badge variant="outline">{totalImports}</Badge>
                </div>
                {file_stats && (
                  <>
                    {file_stats.lines_of_code && (
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">
                          Lines of Code
                        </span>
                        <Badge variant="outline">
                          {file_stats.lines_of_code}
                        </Badge>
                      </div>
                    )}
                    {file_stats.file_size && (
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">File Size</span>
                        <Badge variant="outline">{file_stats.file_size}</Badge>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
