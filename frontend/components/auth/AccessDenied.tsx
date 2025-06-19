// components/auth/AccessDenied.tsx
"use client";

import { Button } from "@/components/ui/button";
import { XCircle } from "lucide-react";

// This component now accepts an `onBack` function as a prop
export function AccessDenied({ onBack }: { onBack: () => void }) {
  return (
    <div className="w-full max-w-sm space-y-6 p-4 text-center">
      <h1 className="text-3xl font-bold">Access denied</h1>
      <div className="flex flex-col items-center space-y-4">
        <XCircle className="h-16 w-16 text-red-500" />

        <div className="space-y-2">
          <p className="text-muted-foreground">
            Oops! You don't have access
            <br />
            to this role.
          </p>
          <p className="text-sm text-muted-foreground">
            Contact your admin if you need access.
          </p>
        </div>

        <Button onClick={onBack} variant="outline" className="w-full">
          Back to role selection
        </Button>
      </div>
    </div>
  );
}
