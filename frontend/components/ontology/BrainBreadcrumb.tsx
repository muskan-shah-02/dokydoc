"use client";

import { ChevronRight, BrainCircuit } from "lucide-react";

export interface BreadcrumbSegment {
  label: string;
  level: number; // 1-5
  onClick?: () => void;
}

interface BrainBreadcrumbProps {
  segments: BreadcrumbSegment[];
}

const LEVEL_LABELS: Record<number, string> = {
  5: "Brain",
  4: "Alignment",
  3: "System",
  2: "Domain",
  1: "File",
};

export function BrainBreadcrumb({ segments }: BrainBreadcrumbProps) {
  return (
    <nav className="flex items-center gap-1 text-sm">
      <BrainCircuit className="mr-1 h-4 w-4 text-purple-600" />
      {segments.map((seg, i) => {
        const isLast = i === segments.length - 1;
        return (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-gray-400" />}
            <button
              onClick={seg.onClick}
              disabled={isLast || !seg.onClick}
              className={`rounded px-1.5 py-0.5 ${
                isLast
                  ? "font-medium text-gray-900"
                  : "text-gray-500 hover:bg-gray-100 hover:text-gray-700"
              } ${!seg.onClick && !isLast ? "cursor-default" : ""}`}
            >
              {seg.label}
            </button>
            {!isLast && (
              <span className="text-[10px] text-gray-400">L{seg.level}</span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
