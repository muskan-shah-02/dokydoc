/*
  This is the content for your NEW file at:
  frontend/app/dashboard/code/page.tsx
*/
"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { GitBranch, PlusCircle, AlertCircle } from "lucide-react";

// Define the shape of a CodeComponent object for TypeScript
interface CodeComponent {
  id: number;
  name: string;
  component_type: string;
  location: string;
  version: string;
  created_at: string;
}

// --- Register Component Dialog Component ---
const RegisterComponentDialog = ({
  onRegisterSuccess,
}: {
  onRegisterSuccess: () => void;
}) => {
  const [name, setName] = useState("");
  const [componentType, setComponentType] = useState("Repository");
  const [location, setLocation] = useState("");
  const [version, setVersion] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const handleSubmit = async () => {
    if (!name || !componentType || !location || !version) {
      setError("All fields are required.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    const componentIn = {
      name,
      component_type: componentType,
      location,
      version,
    };
    const token = localStorage.getItem("accessToken");

    try {
      const response = await fetch(
        "http://localhost:8000/api/v1/code-components/",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(componentIn),
        }
      );

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to register component");
      }

      onRegisterSuccess();
      setIsOpen(false);
      // Reset form
      setName("");
      setComponentType("Repository");
      setLocation("");
      setVersion("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <PlusCircle className="mr-2 h-4 w-4" /> Register Component
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Register New Code Component</DialogTitle>
          <DialogDescription>
            Provide details for the code component you want to track.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid w-full items-center gap-1.5">
            <Label htmlFor="name">Component Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., User Authentication Service"
            />
          </div>
          <div className="grid w-full items-center gap-1.5">
            <Label htmlFor="location">Location (URL or Path)</Label>
            <Input
              id="location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g., https://github.com/org/repo"
            />
          </div>
          <div className="grid w-full items-center gap-1.5">
            <Label htmlFor="version">Version / Git Hash</Label>
            <Input
              id="version"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="e.g., v1.2.0 or a0b1c2d"
            />
          </div>
          <div className="grid w-full items-center gap-1.5">
            <Label htmlFor="componentType">Component Type</Label>
            <select
              id="componentType"
              value={componentType}
              onChange={(e) => setComponentType(e.target.value)}
              className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="Repository">Repository</option>
              <option value="File">File</option>
              <option value="Class">Class</option>
              <option value="Function">Function</option>
            </select>
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
        <DialogFooter>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Registering..." : "Register"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// --- Main Code Components Page Component ---
export default function CodeComponentsPage() {
  const [components, setComponents] = useState<CodeComponent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchComponents = async () => {
    setIsLoading(true);
    setError(null);
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setError("Authentication token not found.");
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch(
        "http://localhost:8000/api/v1/code-components/",
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to fetch code components.");
      }
      const data: CodeComponent[] = await response.json();
      setComponents(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchComponents();
  }, []);

  return (
    <div className="p-2 sm:p-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
          Code Component Library
        </h1>
        <RegisterComponentDialog onRegisterSuccess={fetchComponents} />
      </div>

      {isLoading && <p>Loading components...</p>}
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
                <TableHead>Component Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Version</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {components.length > 0 ? (
                components.map((comp) => (
                  <TableRow key={comp.id}>
                    <TableCell className="font-medium flex items-center">
                      <GitBranch className="h-4 w-4 mr-2 text-gray-500" />
                      {comp.name}
                    </TableCell>
                    <TableCell>{comp.component_type}</TableCell>
                    <TableCell className="text-blue-600 hover:underline cursor-pointer">
                      {comp.location}
                    </TableCell>
                    <TableCell>{comp.version}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="text-center h-24">
                    No code components found. Register your first component to
                    get started.
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
