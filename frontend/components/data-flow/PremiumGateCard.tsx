"use client";

import { Lock, Zap } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface PremiumGateCardProps {
  featureName?: string;
  currentTier?: string | null;
}

/**
 * P3.8: Shown instead of Data Flow when the tenant is on the free tier.
 * Displays a blurred SVG preview + upgrade CTA.
 */
export function PremiumGateCard({
  featureName = "Request Data Flow Diagrams",
  currentTier = "free",
}: PremiumGateCardProps) {
  return (
    <Card className="relative overflow-hidden border-2 border-dashed border-violet-200 bg-violet-50/30">
      {/* Blurred preview — static SVG placeholder */}
      <div className="absolute inset-0 blur-sm opacity-30 pointer-events-none select-none">
        <svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
          <rect x="10" y="80" width="80" height="40" rx="6" fill="#818cf8" />
          <rect x="160" y="60" width="80" height="40" rx="6" fill="#34d399" />
          <rect x="160" y="110" width="80" height="40" rx="6" fill="#f59e0b" />
          <rect x="310" y="80" width="80" height="40" rx="6" fill="#f87171" />
          <line x1="90" y1="100" x2="160" y2="80" stroke="#6b7280" strokeWidth="2" markerEnd="url(#arr)" />
          <line x1="90" y1="100" x2="160" y2="130" stroke="#6b7280" strokeWidth="2" markerEnd="url(#arr)" />
          <line x1="240" y1="80" x2="310" y2="100" stroke="#6b7280" strokeWidth="2" markerEnd="url(#arr)" />
          <line x1="240" y1="130" x2="310" y2="100" stroke="#6b7280" strokeWidth="2" markerEnd="url(#arr)" />
          <defs>
            <marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#6b7280" />
            </marker>
          </defs>
        </svg>
      </div>

      <CardContent className="relative z-10 flex flex-col items-center justify-center py-16 text-center gap-4">
        <div className="w-14 h-14 rounded-full bg-violet-100 flex items-center justify-center">
          <Lock className="w-7 h-7 text-violet-600" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-violet-900">{featureName}</h3>
          <p className="text-sm text-violet-700 mt-1 max-w-sm">
            Visualise the full request path through your codebase — from API endpoint to database.
            Available on Pro &amp; Enterprise plans.
          </p>
          {currentTier && (
            <p className="text-xs text-violet-500 mt-2">
              Your current plan: <span className="font-medium capitalize">{currentTier}</span>
            </p>
          )}
        </div>
        <Button
          className="bg-violet-600 hover:bg-violet-700 text-white gap-2"
          onClick={() => window.open("/settings/billing", "_self")}
        >
          <Zap className="w-4 h-4" /> Upgrade to Pro
        </Button>
      </CardContent>
    </Card>
  );
}
