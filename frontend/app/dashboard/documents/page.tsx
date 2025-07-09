/*
  This is the complete and corrected content for your file at:
  frontend/app/dashboard/documents/page.tsx
*/
"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
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
import {
  FileText,
  PlusCircle,
  AlertCircle,
  Link as LinkIcon,
  Unlink,
} from "lucide-react";

// --- Interface Definitions ---
interface Document {
  id: number;
  filename: string;
  document_type: string;
  version: string;
  created_at: string;
  status: string;
  progress: number;
  link_count?: number;
}

interface CodeComponent {
  id: number;
  name: string;
  component_type: string;
  version: string;
}

// --- Upload Dialog Component ---
const UploadDialog = ({ onUploadSuccess }: { onUploadSuccess: () => void }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [version, setVersion] = useState("");
  const [documentType, setDocumentType] = useState("BRD");
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !version || !documentType) {
      setError("All fields are required.");
      return;
    }
    setIsUploading(true);
    setError(null);
    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("version", version);
    formData.append("document_type", documentType);
    const token = localStorage.getItem("accessToken");
    try {
      const response = await fetch(
        "http://localhost:8000/api/v1/documents/upload",
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        }
      );
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Upload failed");
      }
      onUploadSuccess();
      setIsOpen(false);
      setSelectedFile(null);
      setVersion("");
      setDocumentType("BRD");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <PlusCircle className="mr-2 h-4 w-4" /> Upload Document
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Upload New Document</DialogTitle>
          <DialogDescription>
            Select a file and provide its metadata. Click upload when you're
            done.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="file">Document File</Label>
            <Input id="file" type="file" onChange={handleFileChange} />
          </div>
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="version">Version</Label>
            <Input
              id="version"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="e.g., v1.0"
            />
          </div>
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="documentType">Document Type</Label>
            <select
              id="documentType"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="BRD">BRD</option>
              <option value="SRS">SRS</option>
              <option value="Tech Spec">Tech Spec</option>
              <option value="Other">Other</option>
            </select>
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
        <DialogFooter>
          <Button onClick={handleUpload} disabled={isUploading}>
            {isUploading ? "Uploading..." : "Upload"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// --- Manage Links Dialog Component ---
const ManageLinksDialog = ({
  document,
  onLinksChanged,
}: {
  document: Document;
  onLinksChanged: () => void;
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [allCodeComponents, setAllCodeComponents] = useState<CodeComponent[]>(
    []
  );
  const [linkedComponentIds, setLinkedComponentIds] = useState<Set<number>>(
    new Set()
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = localStorage.getItem("accessToken");

  const fetchAllData = useCallback(async () => {
    if (!isOpen || !token) return;
    setIsLoading(true);
    setError(null);
    try {
      const componentsRes = await fetch(
        "http://localhost:8000/api/v1/code-components/",
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!componentsRes.ok)
        throw new Error("Failed to fetch code components.");
      const allComps: CodeComponent[] = await componentsRes.json();
      setAllCodeComponents(allComps);

      const linkedRes = await fetch(
        `http://localhost:8000/api/v1/links/document/${document.id}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!linkedRes.ok) throw new Error("Failed to fetch existing links.");
      const linkedComps: CodeComponent[] = await linkedRes.json();
      setLinkedComponentIds(new Set(linkedComps.map((c) => c.id)));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [isOpen, document.id, token]);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  const handleLinkToggle = async (component: CodeComponent) => {
    const isCurrentlyLinked = linkedComponentIds.has(component.id);
    const endpoint = "http://localhost:8000/api/v1/links/";
    const method = isCurrentlyLinked ? "DELETE" : "POST";
    try {
      const response = await fetch(endpoint, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          document_id: document.id,
          code_component_id: component.id,
        }),
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(
          errData.detail || `Failed to ${isCurrentlyLinked ? "unlink" : "link"}`
        );
      }
      await fetchAllData();
      onLinksChanged();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <LinkIcon className="mr-2 h-4 w-4" /> Manage Links (
          {document.link_count || 0})
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Link Code to: {document.filename}</DialogTitle>
          <DialogDescription>
            Select code components to associate with this document.
          </DialogDescription>
        </DialogHeader>
        {isLoading && <p>Loading...</p>}
        {error && <p className="text-sm text-red-500">{error}</p>}
        {!isLoading && !error && (
          <div className="max-h-80 overflow-y-auto p-1">
            <ul className="space-y-2">
              {allCodeComponents.map((comp) => (
                <li
                  key={comp.id}
                  className="flex items-center justify-between p-2 rounded-md hover:bg-gray-100"
                >
                  <div>
                    <p className="font-semibold">{comp.name}</p>
                    <p className="text-sm text-gray-500">
                      {comp.component_type} - v{comp.version}
                    </p>
                  </div>
                  <Button
                    variant={
                      linkedComponentIds.has(comp.id)
                        ? "destructive"
                        : "default"
                    }
                    size="sm"
                    onClick={() => handleLinkToggle(comp)}
                  >
                    {linkedComponentIds.has(comp.id) ? (
                      <Unlink className="h-4 w-4" />
                    ) : (
                      <LinkIcon className="h-4 w-4" />
                    )}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

// --- Document Status Cell Component ---
const DocumentStatusCell = ({
  doc,
  onUpdate,
}: {
  doc: Document;
  onUpdate: (updatedDoc: Document) => void;
}) => {
  const [status, setStatus] = useState(doc.status);
  const [progress, setProgress] = useState(doc.progress);

  useEffect(() => {
    if (status === "processing") {
      const intervalId = setInterval(async () => {
        const token = localStorage.getItem("accessToken");
        try {
          const response = await fetch(
            `http://localhost:8000/api/v1/documents/${doc.id}/status`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          if (!response.ok) {
            clearInterval(intervalId);
            setStatus("failed");
            return;
          }
          const data = await response.json();
          setProgress(data.progress);
          setStatus(data.status);
          if (data.status === "completed" || data.status === "failed") {
            clearInterval(intervalId);
            onUpdate({ ...doc, status: data.status, progress: data.progress });
          }
        } catch (error) {
          console.error("Polling error:", error);
          clearInterval(intervalId);
          setStatus("failed");
        }
      }, 2000);
      return () => clearInterval(intervalId);
    }
  }, [status, doc.id, onUpdate, doc]);

  if (status === "completed") {
    return <span className="text-green-600 font-medium">Completed</span>;
  }
  if (status === "failed") {
    return <span className="text-red-600 font-medium">Failed</span>;
  }
  return (
    <div className="flex items-center gap-2">
      <Progress value={progress} className="w-24" />
      <span className="text-sm text-gray-500">{progress}%</span>
    </div>
  );
};

// --- Main Documents Page Component ---
export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setError("Authentication token not found.");
      setIsLoading(false);
      return;
    }
    try {
      const response = await fetch("http://localhost:8000/api/v1/documents/", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to fetch documents.");
      }
      const data: Document[] = await response.json();
      const documentsWithLinkCounts = await Promise.all(
        data.map(async (doc) => {
          try {
            const linksResponse = await fetch(
              `http://localhost:8000/api/v1/links/document/${doc.id}`,
              { headers: { Authorization: `Bearer ${token}` } }
            );
            if (!linksResponse.ok) return { ...doc, link_count: 0 };
            const linkedComponents: CodeComponent[] =
              await linksResponse.json();
            return { ...doc, link_count: linkedComponents.length };
          } catch {
            return { ...doc, link_count: 0 };
          }
        })
      );
      setDocuments(documentsWithLinkCounts);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleDocumentUpdate = (updatedDoc: Document) => {
    setDocuments((currentDocs) =>
      currentDocs.map((d) => (d.id === updatedDoc.id ? updatedDoc : d))
    );
  };

  return (
    <div className="p-2 sm:p-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
          Document Library
        </h1>
        <UploadDialog onUploadSuccess={fetchDocuments} />
      </div>

      {isLoading && <p className="text-center p-10">Loading documents...</p>}
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
                <TableHead>Filename</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.length > 0 ? (
                documents.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="font-medium">
                      <a
                        href={`/dashboard/documents/${doc.id}`}
                        className="flex items-center text-blue-600 hover:underline"
                      >
                        <FileText className="h-4 w-4 mr-2 text-gray-500" />
                        {doc.filename}
                      </a>
                    </TableCell>
                    <TableCell>{doc.document_type}</TableCell>
                    <TableCell>{doc.version}</TableCell>
                    <TableCell>
                      <DocumentStatusCell
                        doc={doc}
                        onUpdate={handleDocumentUpdate}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <ManageLinksDialog
                        document={doc}
                        onLinksChanged={fetchDocuments}
                      />
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={5} className="text-center h-24">
                    No documents found. Upload your first document to get
                    started.
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
