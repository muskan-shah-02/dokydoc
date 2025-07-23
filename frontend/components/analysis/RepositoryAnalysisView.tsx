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
  Users,
  Code,
  GitMerge,
  ShieldCheck,
  AlertTriangle,
  CheckCircle,
  Clock,
  Star,
  TrendingUp,
  Package,
  Zap,
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

// Helper to get stage icon and color
const getStageInfo = (stage: string) => {
  const lower = stage?.toLowerCase();
  if (lower?.includes("production") || lower?.includes("stable")) {
    return { icon: CheckCircle, color: "text-green-600" };
  }
  if (lower?.includes("beta") || lower?.includes("testing")) {
    return { icon: AlertTriangle, color: "text-yellow-600" };
  }
  if (lower?.includes("alpha") || lower?.includes("development")) {
    return { icon: Clock, color: "text-blue-600" };
  }
  return { icon: Code, color: "text-muted-foreground" };
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

  const {
    architecture = {},
    project_insights = {},
    technology_assessment = {},
    primary_language,
    confidence_score,
    analysis_timestamp,
  } = analysis;

  const stageInfo = getStageInfo(project_insights.development_stage || "");

  return (
    <div className="space-y-6">
      {(confidence_score || analysis_timestamp) && (
        <Alert>
          <Star className="h-4 w-4" />
          <AlertDescription>
            Analysis completed
            {analysis_timestamp && (
              <span>
                {" "}
                on {new Date(analysis_timestamp).toLocaleDateString()}
              </span>
            )}
            {confidence_score && (
              <span>
                {" "}
                with {Math.round(confidence_score * 100)}% confidence
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
                label="Architecture Pattern"
                value={architecture.type || "Not identified"}
                icon={Layers}
                variant={architecture.type ? "success" : "default"}
              />
              <InfoList
                title="System Components"
                items={architecture.components}
                icon={GitMerge}
                emptyMessage="No specific components identified"
                maxItems={8}
              />
              <InfoList
                title="Technology Stack"
                items={architecture.tech_stack}
                icon={Code}
                emptyMessage="Technology stack not analyzed"
                maxItems={6}
              />
              {primary_language && (
                <InfoItem
                  label="Primary Language"
                  value={primary_language}
                  icon={Code}
                  variant="success"
                />
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <ShieldCheck className="w-5 h-5 mr-3 text-green-600" />
                Technology Assessment
              </CardTitle>
              <CardDescription>
                Analysis of technology choices, dependencies, and scalability
                considerations
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {technology_assessment.language_choice_rationale && (
                <div className="p-4 bg-muted/30 rounded-lg">
                  <h4 className="font-semibold mb-2 flex items-center">
                    <Lightbulb className="w-4 h-4 mr-2 text-yellow-500" />
                    Language Choice Rationale
                  </h4>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {technology_assessment.language_choice_rationale}
                  </p>
                </div>
              )}
              <InfoList
                title="Notable Dependencies"
                items={technology_assessment.notable_dependencies}
                icon={Package}
                emptyMessage="No notable dependencies identified"
                maxItems={8}
              />
              {technology_assessment.scalability_considerations && (
                <div className="p-4 bg-muted/30 rounded-lg">
                  <h4 className="font-semibold mb-2 flex items-center">
                    <TrendingUp className="w-4 h-4 mr-2 text-blue-500" />
                    Scalability Considerations
                  </h4>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {technology_assessment.scalability_considerations}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Lightbulb className="w-5 h-5 mr-3 text-yellow-500" />
                Project Insights
              </CardTitle>
              <CardDescription>
                High-level project characteristics and development status
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <InfoItem
                label="Complexity Level"
                value={project_insights.complexity}
                icon={Zap}
                variant={
                  project_insights.complexity?.toLowerCase().includes("high")
                    ? "warning"
                    : project_insights.complexity?.toLowerCase().includes("low")
                    ? "success"
                    : "default"
                }
              />
              <InfoItem
                label="Development Stage"
                value={project_insights.development_stage}
                icon={stageInfo.icon}
              />
              {project_insights.target_users && (
                <div className="p-3 bg-muted/30 rounded-lg">
                  <h4 className="font-semibold mb-2 flex items-center text-sm">
                    <Users className="w-4 h-4 mr-2 text-muted-foreground" />
                    Target Users
                  </h4>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {project_insights.target_users}
                  </p>
                </div>
              )}
              {project_insights.maintenance_notes && (
                <div className="p-3 bg-muted/30 rounded-lg">
                  <h4 className="font-semibold mb-2 flex items-center text-sm">
                    <AlertTriangle className="w-4 h-4 mr-2 text-yellow-500" />
                    Maintenance Notes
                  </h4>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {project_insights.maintenance_notes}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
          {(architecture.components?.length ||
            technology_assessment.notable_dependencies?.length) && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Quick Stats</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {architecture.components?.length && (
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium">Components</span>
                    <Badge variant="outline">
                      {architecture.components.length}
                    </Badge>
                  </div>
                )}
                {technology_assessment.notable_dependencies?.length && (
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium">Dependencies</span>
                    <Badge variant="outline">
                      {technology_assessment.notable_dependencies.length}
                    </Badge>
                  </div>
                )}
                {architecture.tech_stack?.length && (
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium">Technologies</span>
                    <Badge variant="outline">
                      {architecture.tech_stack.length}
                    </Badge>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
