// This is the updated content for your file at:
// frontend/components/analysis/RepositoryAnalysisView.tsx

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
  Layers,
  Lightbulb,
  Code,
  GitMerge,
  ShieldCheck,
  AlertTriangle,
  CheckCircle,
  Star,
  TrendingUp,
  Package,
} from "lucide-react";

interface RepositoryAnalysisViewProps {
  analysis: any; // The structured_analysis object from our API
  isLoading?: boolean;
}

// Helper component for displaying a list of items with an icon
const InfoList = ({
  title,
  items,
  icon: Icon,
  emptyMessage = "Not available",
  maxItems = 10,
}: {
  title: string;
  items?: string[];
  icon: React.ElementType;
  emptyMessage?: string;
  maxItems?: number;
}) => {
  const displayItems = items?.slice(0, maxItems) || [];
  const hasMore = items && items.length > maxItems;
  return (
    <div className="space-y-2">
      <h4 className="font-semibold text-sm flex items-center">
        <Icon className="w-4 h-4 mr-2 text-muted-foreground" />
        {title}
      </h4>
      <div className="flex flex-wrap gap-2">
        {displayItems.length > 0 ? (
          <>
            {displayItems.map((item, index) => (
              <Badge key={index} variant="secondary" className="text-xs">
                {item}
              </Badge>
            ))}
            {hasMore && (
              <Badge variant="outline" className="text-xs">
                +{items!.length - maxItems} more
              </Badge>
            )}
          </>
        ) : (
          <p className="text-sm text-muted-foreground italic">{emptyMessage}</p>
        )}
      </div>
    </div>
  );
};

// Helper component for displaying key-value pairs with better formatting
const InfoItem = ({
  label,
  value,
  icon: Icon,
  variant = "default",
}: {
  label: string;
  value?: string;
  icon?: React.ElementType;
  variant?: "default" | "success" | "warning" | "error";
}) => {
  const getVariantStyles = () => {
    switch (variant) {
      case "success":
        return "text-green-600 bg-green-50 dark:bg-green-900/20 dark:text-green-400";
      case "warning":
        return "text-yellow-600 bg-yellow-50 dark:bg-yellow-900/20 dark:text-yellow-400";
      case "error":
        return "text-red-600 bg-red-50 dark:bg-red-900/20 dark:text-red-400";
      default:
        return "text-blue-600 bg-blue-50 dark:bg-blue-900/20 dark:text-blue-400";
    }
  };
  return (
    <div className="flex justify-between items-start gap-2 p-2 rounded-md bg-muted/30">
      <span className="font-medium text-sm flex items-center">
        {Icon && <Icon className="w-4 h-4 mr-2 text-muted-foreground" />}
        {label}
      </span>
      <span
        className={`text-sm font-semibold px-2 py-1 rounded-md ${getVariantStyles()}`}
      >
        {value || "N/A"}
      </span>
    </div>
  );
};

export function RepositoryAnalysisView({
  analysis,
  isLoading = false,
}: RepositoryAnalysisViewProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {[1, 2].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader>
                <div className="h-6 bg-muted rounded w-1/3"></div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="h-4 bg-muted rounded w-1/2"></div>
                  <div className="h-4 bg-muted rounded w-2/3"></div>
                  <div className="h-4 bg-muted rounded w-1/4"></div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="space-y-6">
          <Card className="animate-pulse">
            <CardHeader>
              <div className="h-6 bg-muted rounded w-1/2"></div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="h-4 bg-muted rounded"></div>
                <div className="h-4 bg-muted rounded w-3/4"></div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (!analysis || analysis.error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          The AI analysis for this repository could not be completed.
          {analysis?.error && (
            <span className="block mt-1 text-sm">
              Error details: {analysis.error}
            </span>
          )}
        </AlertDescription>
      </Alert>
    );
  }

  // Map from the actual Gemini CODE_ANALYSIS response format
  // Gemini returns: language_info, components, dependencies, patterns_and_architecture, quality_assessment
  const {
    language_info = {} as Record<string, any>,
    components = [] as any[],
    dependencies = [] as string[],
    exports = [] as string[],
    patterns_and_architecture = {} as Record<string, any>,
    quality_assessment,
    analysis_timestamp,
  } = analysis;

  const primary_language = language_info.primary_language;
  const framework = language_info.framework;
  const architectural_style = patterns_and_architecture.architectural_style;
  const design_patterns = patterns_and_architecture.design_patterns || [];
  const key_concepts = patterns_and_architecture.key_concepts || [];

  // Group components by type for stats
  const componentsByType: Record<string, number> = {};
  components.forEach((c: any) => {
    const type = c.type || "Unknown";
    componentsByType[type] = (componentsByType[type] || 0) + 1;
  });
  const componentTypeNames = Object.keys(componentsByType).sort(
    (a, b) => componentsByType[b] - componentsByType[a]
  );

  return (
    <div className="space-y-6">
      {analysis_timestamp && (
        <Alert>
          <Star className="h-4 w-4" />
          <AlertDescription>
            Analysis completed on{" "}
            {new Date(analysis_timestamp).toLocaleDateString()}
          </AlertDescription>
        </Alert>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Layers className="w-5 h-5 mr-3 text-blue-600" />
                Architectural Overview
              </CardTitle>
              <CardDescription>
                System design patterns and structural components identified in
                the codebase
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <InfoItem
                label="Architecture Style"
                value={architectural_style || "Not identified"}
                icon={Layers}
                variant={architectural_style ? "success" : "default"}
              />
              {primary_language && (
                <InfoItem
                  label="Primary Language"
                  value={primary_language}
                  icon={Code}
                  variant="success"
                />
              )}
              {framework && (
                <InfoItem
                  label="Framework"
                  value={framework}
                  icon={Code}
                  variant="default"
                />
              )}
              <InfoList
                title="Key Concepts"
                items={key_concepts}
                icon={GitMerge}
                emptyMessage="No key concepts identified"
                maxItems={10}
              />
              <InfoList
                title="Design Patterns"
                items={design_patterns}
                icon={CheckCircle}
                emptyMessage="No design patterns identified"
                maxItems={8}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <ShieldCheck className="w-5 h-5 mr-3 text-green-600" />
                Dependencies & Technology Stack
              </CardTitle>
              <CardDescription>
                External libraries and technology dependencies found in the
                repository
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <InfoList
                title="Dependencies"
                items={Array.isArray(dependencies) ? dependencies : []}
                icon={Package}
                emptyMessage="No dependencies identified"
                maxItems={12}
              />
              {exports.length > 0 && (
                <InfoList
                  title="Exports"
                  items={exports}
                  icon={TrendingUp}
                  emptyMessage="No exports identified"
                  maxItems={8}
                />
              )}
            </CardContent>
          </Card>
          {/* Code Components Found */}
          {components.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Code className="w-5 h-5 mr-3 text-purple-600" />
                  Code Components ({components.length})
                </CardTitle>
                <CardDescription>
                  Functions, classes, services, and other code elements found
                  across the repository
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                  {components.slice(0, 30).map((comp: any, idx: number) => (
                    <div
                      key={idx}
                      className="flex items-start justify-between p-3 bg-muted/30 rounded-lg"
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">
                            {comp.name}
                          </span>
                          <Badge variant="secondary" className="text-xs">
                            {comp.type}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {comp.purpose}
                        </p>
                      </div>
                    </div>
                  ))}
                  {components.length > 30 && (
                    <p className="text-sm text-muted-foreground text-center py-2">
                      +{components.length - 30} more components
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
        <div className="space-y-6">
          {/* Quality Assessment */}
          {quality_assessment && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Lightbulb className="w-5 h-5 mr-3 text-yellow-500" />
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
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Quick Stats</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Total Components</span>
                <Badge variant="outline">{components.length}</Badge>
              </div>
              {componentTypeNames.slice(0, 5).map((type) => (
                <div key={type} className="flex justify-between items-center">
                  <span className="text-sm font-medium">{type}s</span>
                  <Badge variant="outline">{componentsByType[type]}</Badge>
                </div>
              ))}
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Dependencies</span>
                <Badge variant="outline">
                  {Array.isArray(dependencies) ? dependencies.length : 0}
                </Badge>
              </div>
              {design_patterns.length > 0 && (
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Design Patterns</span>
                  <Badge variant="outline">{design_patterns.length}</Badge>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
