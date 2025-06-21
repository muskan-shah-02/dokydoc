// frontend/app/access-denied/page.tsx

"use client"; // Required for router usage if needed, good practice here

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { XCircle } from "lucide-react";

export default function AccessDeniedPage() {
  return (
    <main className="flex h-screen w-full items-center justify-center">
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

                {/* Use Next.js Link for navigation */}
                <Link href="/select-role" passHref>
                    <Button variant="outline" className="w-full">
                        Back to role selection
                    </Button>
                </Link>
            </div>
        </div>
    </main>
  );
}