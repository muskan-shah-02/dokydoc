/*
  This is the content for your NEW file at:
  frontend/app/dashboard/validation-panel/page.tsx
*/
"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AlertCircle, FileWarning, ScanLine, CheckCircle } from "lucide-react";

// Define the shape of a Mismatch object for TypeScript
interface Mismatch {
  id: number;
  mismatch_type: string;
  description: string;
  status: string;
  detected_at: string;
  document_id: number;
  code_component_id: number;
}

// --- Main Validation Panel Page Component ---
export default function ValidationPanelPage() {
  const [mismatches, setMismatches] = useState<Mismatch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = localStorage.getItem("accessToken");

  const fetchMismatches = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    if (!token) {
      setError("Authentication token not found.");
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch(
        "http://localhost:8000/api/v1/validation/mismatches",
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to fetch mismatches.");
      }
      const data: Mismatch[] = await response.json();
      setMismatches(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchMismatches();
  }, [fetchMismatches]);

  const handleRunScan = async () => {
    setIsScanning(true);
    setError(null);
    if (!token) {
      setError("Authentication token not found.");
      setIsScanning(false);
      return;
    }

    try {
      const response = await fetch(
        "http://localhost:8000/api/v1/validation/run-scan",
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (response.status !== 202) {
        // 202 Accepted
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to start validation scan.");
      }

      // After triggering the scan, wait a few seconds for the background task
      // to complete, then refresh the list of mismatches.
      setTimeout(() => {
        fetchMismatches();
        setIsScanning(false);
      }, 5000); // 5-second delay to allow backend processing
    } catch (err) {
      setError((err as Error).message);
      setIsScanning(false);
    }
  };

  return (
    <div className="p-2 sm:p-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
          Validation Panel
        </h1>
        <Button onClick={handleRunScan} disabled={isScanning}>
          <ScanLine
            className={`mr-2 h-4 w-4 ${isScanning ? "animate-pulse" : ""}`}
          />
          {isScanning ? "Scanning..." : "Run Validation Scan"}
        </Button>
      </div>

      {isLoading && <p className="text-center p-10">Loading results...</p>}
      {error && (
        <div className="text-red-500 bg-red-100 p-4 rounded-lg flex items-center">
          <AlertCircle className="mr-2" /> Error: {error}
        </div>
      )}

      {!isLoading && !error && (
        <div className="rounded-lg border shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Description</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Detected At</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mismatches.length > 0 ? (
                mismatches.map((mismatch) => (
                  <TableRow key={mismatch.id}>
                    <TableCell className="font-medium">
                      {mismatch.description}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{mismatch.mismatch_type}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          mismatch.status === "new"
                            ? "destructive"
                            : "secondary"
                        }
                      >
                        {mismatch.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {new Date(mismatch.detected_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="text-center h-48">
                    <div className="flex flex-col items-center justify-center gap-2 text-gray-500">
                      <CheckCircle className="h-12 w-12 text-green-500" />
                      <span className="font-semibold">No Mismatches Found</span>
                      <p className="text-sm">
                        Run a new scan to check for discrepancies.
                      </p>
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
