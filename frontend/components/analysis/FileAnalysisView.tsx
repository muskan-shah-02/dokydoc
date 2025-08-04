// Updated FileAnalysisView.tsx - Compatible with Universal Backend Schema - Zero Errors

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
  Globe,
  Database,
  Layers,
  Activity,
  Target,
  Hash,
  Cpu,
  FileCode,
  Braces,
  FunctionSquare as FunctionIcon,
  Component as ComponentIcon,
  Variable,
  Route,
  Plug,
  Type,
} from "lucide-react";
import { useState } from "react";

interface FileAnalysisViewProps {
  analysis: any; // The response object from our universal API
  isLoading?: boolean;
  fileName?: string;
}

interface ComponentInfo {
  name: string;
  type: string;
  purpose: string;
  details: string;
  line_info?: string;
}

interface LanguageInfo {
  primary_language?: string;
  framework?: string;
  file_type?: string;
}

interface PatternsAndArchitecture {
  design_patterns?: string[];
  architectural_style?: string;
  key_concepts?: string[];
}

// Get appropriate icon for component type
const getComponentIcon = (type: string) => {
  const lowerType = type.toLowerCase();
  switch (lowerType) {
    case "function":
    case "asyncfunction":
    case "method":
      return FunctionIcon;
    case "class":
    case "interface":
      return Boxes;
    case "component":
      return ComponentIcon;
    case "constant":
    case "variable":
      return Variable;
    case "hook":
      return Activity;
    case "service":
      return Settings;
    case "route":
      return Route;
    case "model":
      return Database;
    case "type":
    case "enum":
      return Type;
    case "module":
      return Package;
    default:
      return Code;
  }
};

// Get appropriate color for component type
const getComponentColor = (type: string) => {
  const lowerType = type.toLowerCase();
  switch (lowerType) {
    case "function":
    case "asyncfunction":
    case "method":
      return "from-blue-50 to-blue-50/50 border-blue-100 text-blue-700";
    case "class":
    case "interface":
      return "from-green-50 to-green-50/50 border-green-100 text-green-700";
    case "component":
      return "from-purple-50 to-purple-50/50 border-purple-100 text-purple-700";
    case "constant":
    case "variable":
      return "from-orange-50 to-orange-50/50 border-orange-100 text-orange-700";
    case "hook":
      return "from-pink-50 to-pink-50/50 border-pink-100 text-pink-700";
    case "service":
      return "from-indigo-50 to-indigo-50/50 border-indigo-100 text-indigo-700";
    case "route":
      return "from-yellow-50 to-yellow-50/50 border-yellow-100 text-yellow-700";
    case "model":
      return "from-teal-50 to-teal-50/50 border-teal-100 text-teal-700";
    case "type":
    case "enum":
      return "from-slate-50 to-slate-50/50 border-slate-100 text-slate-700";
    default:
      return "from-gray-50 to-gray-50/50 border-gray-100 text-gray-700";
  }
};

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
        <CollapsibleContent className="pt-4 space-y-4">
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
      <div className="space-y-4">{children}</div>
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

  // Extract data from the backend schema - handle both direct props and structured_analysis
  const structuredData = analysis.structured_analysis || analysis;
  const {
    language_info = {} as LanguageInfo,
    components = [] as ComponentInfo[],
    dependencies = [],
    exports = [],
    patterns_and_architecture = {} as PatternsAndArchitecture,
    quality_assessment,
    analysis_timestamp,
  } = structuredData;

  // Group components by type for better organization with proper TypeScript handling
  interface ComponentsByType {
    [type: string]: ComponentInfo[];
  }

  const componentsByType: ComponentsByType = components.reduce(
    (acc: ComponentsByType, component: ComponentInfo) => {
      const type: string = component.type || "Unknown";
      if (!acc[type]) {
        acc[type] = [];
      }
      acc[type].push(component);
      return acc;
    },
    {} as ComponentsByType
  );

  // Get component type counts
  const componentCounts = Object.keys(componentsByType)
    .map((type: string) => ({
      type,
      count: componentsByType[type].length,
      components: componentsByType[type],
    }))
    .sort((a, b) => b.count - a.count);

  return (
    <div className="space-y-6">
      {/* Header with language and file info */}
      <Alert>
        <FileText className="h-4 w-4" />
        <AlertDescription>
          <div className="flex flex-wrap items-center gap-2">
            <span>Analysis of {fileName || "file"}</span>
            {language_info.primary_language && (
              <Badge variant="default" className="text-xs">
                {language_info.primary_language}
              </Badge>
            )}
            {language_info.framework && (
              <Badge variant="secondary" className="text-xs">
                {language_info.framework}
              </Badge>
            )}
            {language_info.file_type && (
              <Badge variant="outline" className="text-xs">
                {language_info.file_type}
              </Badge>
            )}
            {analysis_timestamp && (
              <span className="text-xs text-muted-foreground">
                • {new Date(analysis_timestamp).toLocaleDateString()}
              </span>
            )}
          </div>
        </AlertDescription>
      </Alert>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Code Components Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Code className="w-5 h-5 mr-3 text-blue-600" />
                Code Components Analysis
              </CardTitle>
              <CardDescription>
                All code elements identified in this{" "}
                {language_info.primary_language || "code"} file
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {componentCounts.length > 0 ? (
                componentCounts.map(
                  ({ type, count, components: typeComponents }) => (
                    <Section
                      key={type}
                      title={`${type}s`}
                      icon={getComponentIcon(type)}
                      collapsible={count > 3}
                      count={count}
                    >
                      {typeComponents.map(
                        (component: ComponentInfo, index: number) => {
                          const IconComponent = getComponentIcon(
                            component.type
                          );
                          const colorClasses = getComponentColor(
                            component.type
                          );

                          return (
                            <div
                              key={index}
                              className={`p-4 bg-gradient-to-r ${colorClasses} border rounded-lg`}
                            >
                              <div className="flex items-start justify-between mb-2">
                                <h4
                                  className={`font-semibold flex items-center ${colorClasses
                                    .split(" ")
                                    .pop()}`}
                                >
                                  <IconComponent className="w-4 h-4 mr-2" />
                                  {component.name}
                                </h4>
                                <Badge variant="outline" className="text-xs">
                                  {component.type}
                                </Badge>
                              </div>
                              <p className="text-sm text-muted-foreground mb-3 leading-relaxed">
                                {component.purpose}
                              </p>
                              {component.details && (
                                <div className="text-xs">
                                  <DetailItem
                                    title="Details"
                                    content={component.details}
                                    icon={Info}
                                  />
                                </div>
                              )}
                              {component.line_info && (
                                <div className="mt-2 pt-2 border-t border-current/20">
                                  <Badge variant="outline" className="text-xs">
                                    {component.line_info}
                                  </Badge>
                                </div>
                              )}
                            </div>
                          );
                        }
                      )}
                    </Section>
                  )
                )
              ) : (
                <div className="text-center py-8">
                  <Code className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-sm text-muted-foreground italic">
                    No code components identified in this file.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Dependencies & Exports Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Network className="w-5 h-5 mr-3 text-purple-600" />
                Dependencies & Exports
              </CardTitle>
              <CardDescription>
                External libraries and exports from this file
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Dependencies */}
              <div className="space-y-2">
                <h4 className="font-medium text-sm flex items-center">
                  <Package className="w-4 h-4 mr-2 text-muted-foreground" />
                  Dependencies
                  <Badge variant="outline" className="ml-2">
                    {Array.isArray(dependencies) ? dependencies.length : 0}
                  </Badge>
                </h4>
                <div className="flex flex-wrap gap-1 pl-6">
                  {Array.isArray(dependencies) && dependencies.length > 0 ? (
                    dependencies.map((dep: string, i: number) => (
                      <Badge key={i} variant="secondary" className="text-xs">
                        {dep}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-xs text-muted-foreground italic">
                      No dependencies identified
                    </span>
                  )}
                </div>
              </div>

              {/* Exports */}
              <div className="space-y-2">
                <h4 className="font-medium text-sm flex items-center">
                  <ArrowRight className="w-4 h-4 mr-2 text-muted-foreground" />
                  Exports
                  <Badge variant="outline" className="ml-2">
                    {Array.isArray(exports) ? exports.length : 0}
                  </Badge>
                </h4>
                <div className="flex flex-wrap gap-1 pl-6">
                  {Array.isArray(exports) && exports.length > 0 ? (
                    exports.map((exp: string, i: number) => (
                      <Badge key={i} variant="default" className="text-xs">
                        {exp}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-xs text-muted-foreground italic">
                      No exports identified
                    </span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right sidebar */}
        <div className="space-y-6">
          {/* Language & Architecture Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Layers className="w-5 h-5 mr-3 text-blue-600" />
                Architecture & Patterns
              </CardTitle>
              <CardDescription>
                Technical patterns and architectural insights
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {patterns_and_architecture.architectural_style && (
                <div className="p-3 bg-muted/30 rounded-lg">
                  <h4 className="font-semibold mb-2 flex items-center text-sm">
                    <Layers className="w-4 h-4 mr-2 text-blue-500" />
                    Architectural Style
                  </h4>
                  <p className="text-sm text-muted-foreground">
                    {patterns_and_architecture.architectural_style}
                  </p>
                </div>
              )}

              {patterns_and_architecture.design_patterns &&
                Array.isArray(patterns_and_architecture.design_patterns) &&
                patterns_and_architecture.design_patterns.length > 0 && (
                  <div>
                    <h4 className="font-semibold mb-2 flex items-center text-sm">
                      <Star className="w-4 h-4 mr-2 text-yellow-500" />
                      Design Patterns
                    </h4>
                    <div className="flex flex-wrap gap-1">
                      {patterns_and_architecture.design_patterns.map(
                        (pattern: string, i: number) => (
                          <Badge key={i} variant="default" className="text-xs">
                            {pattern}
                          </Badge>
                        )
                      )}
                    </div>
                  </div>
                )}

              {patterns_and_architecture.key_concepts &&
                Array.isArray(patterns_and_architecture.key_concepts) &&
                patterns_and_architecture.key_concepts.length > 0 && (
                  <div>
                    <h4 className="font-semibold mb-2 flex items-center text-sm">
                      <Lightbulb className="w-4 h-4 mr-2 text-orange-500" />
                      Key Concepts
                    </h4>
                    <div className="flex flex-wrap gap-1">
                      {patterns_and_architecture.key_concepts.map(
                        (concept: string, i: number) => (
                          <Badge
                            key={i}
                            variant="secondary"
                            className="text-xs"
                          >
                            {concept}
                          </Badge>
                        )
                      )}
                    </div>
                  </div>
                )}
            </CardContent>
          </Card>

          {/* Quality Assessment */}
          {quality_assessment && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <ShieldCheck className="w-5 h-5 mr-3 text-green-600" />
                  Quality Assessment
                </CardTitle>
                <CardDescription>
                  AI-generated code quality analysis
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {quality_assessment}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Quick Stats */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Zap className="w-5 h-5 mr-3 text-orange-500" />
                Quick Stats
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Total Components</span>
                <Badge variant="outline">{components.length}</Badge>
              </div>
              {componentCounts.slice(0, 3).map(({ type, count }) => (
                <div key={type} className="flex justify-between items-center">
                  <span className="text-sm font-medium">{type}s</span>
                  <Badge variant="outline">{count}</Badge>
                </div>
              ))}
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Dependencies</span>
                <Badge variant="outline">
                  {Array.isArray(dependencies) ? dependencies.length : 0}
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Exports</span>
                <Badge variant="outline">
                  {Array.isArray(exports) ? exports.length : 0}
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
