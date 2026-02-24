"use client";

import { useCallback, useEffect, useState } from "react";
import {
  FolderKanban,
  PlusCircle,
  RefreshCw,
  Loader2,
  AlertCircle,
  FileText,
  GitBranch,
  Network,
  ChevronRight,
  Trash2,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { useProject, Initiative } from "@/contexts/ProjectContext";
import { useRouter } from "next/navigation";

interface InitiativeAsset {
  id: number;
  initiative_id: number;
  asset_type: string;
  asset_id: number;
  is_active: boolean;
  created_at: string;
}

interface InitiativeWithAssets extends Initiative {
  assets?: InitiativeAsset[];
}

export default function ProjectsPage() {
  const router = useRouter();
  const { projects, refreshProjects, setSelectedProject, isLoadingProjects } = useProject();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [projectStats, setProjectStats] = useState<Record<number, { docs: number; repos: number; concepts: number }>>({});

  // Fetch project stats
  const fetchStats = useCallback(async () => {
    const stats: Record<number, { docs: number; repos: number; concepts: number }> = {};
    for (const project of projects) {
      try {
        const [assets, ontologyStats] = await Promise.all([
          api.get<InitiativeAsset[]>(`/initiatives/${project.id}/assets`),
          api.get<{ total_concepts: number }>("/ontology/stats", { initiative_id: project.id }),
        ]);
        stats[project.id] = {
          docs: assets.filter((a) => a.asset_type === "DOCUMENT" && a.is_active).length,
          repos: assets.filter((a) => a.asset_type === "REPOSITORY" && a.is_active).length,
          concepts: ontologyStats.total_concepts,
        };
      } catch {
        stats[project.id] = { docs: 0, repos: 0, concepts: 0 };
      }
    }
    setProjectStats(stats);
  }, [projects]);

  useEffect(() => {
    setLoading(true);
    refreshProjects();
    setLoading(false);
  }, []);

  useEffect(() => {
    if (projects.length > 0) {
      fetchStats();
    }
  }, [projects, fetchStats]);

  const handleCreate = async () => {
    if (!createName.trim()) return;
    setCreating(true);
    try {
      await api.post("/initiatives/", {
        name: createName.trim(),
        description: createDescription.trim() || null,
        status: "ACTIVE",
      });
      setShowCreateDialog(false);
      setCreateName("");
      setCreateDescription("");
      refreshProjects();
    } catch (err: any) {
      setError(err.detail || "Failed to create project");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/initiatives/${id}`);
      refreshProjects();
    } catch (err: any) {
      setError(err.detail || "Failed to delete project");
    }
  };

  const handleSelectAndNavigate = (project: Initiative) => {
    setSelectedProject(project);
    router.push(`/dashboard/projects/${project.id}`);
  };

  if (loading || isLoadingProjects) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        <p className="ml-2 text-sm text-gray-500">Loading projects...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50/50 p-4 lg:p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Manage projects (initiatives) — group documents, repositories, and ontology concepts
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { refreshProjects(); fetchStats(); }}
            className="flex items-center gap-1.5 rounded-md border bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
          <button
            onClick={() => setShowCreateDialog(true)}
            className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <PlusCircle className="h-4 w-4" /> New Project
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
          <button onClick={() => setError("")} className="ml-auto"><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Project Cards Grid */}
      {projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 bg-white py-16">
          <FolderKanban className="h-12 w-12 text-gray-300" />
          <p className="mt-3 text-sm font-medium text-gray-500">No projects yet</p>
          <p className="mt-1 text-xs text-gray-400">Create a project to group documents, repos, and ontology concepts</p>
          <button
            onClick={() => setShowCreateDialog(true)}
            className="mt-4 flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <PlusCircle className="h-4 w-4" /> Create First Project
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => {
            const stats = projectStats[project.id] || { docs: 0, repos: 0, concepts: 0 };
            return (
              <div
                key={project.id}
                className="group cursor-pointer rounded-lg border bg-white p-5 shadow-sm transition-all hover:border-blue-300 hover:shadow-md"
                onClick={() => handleSelectAndNavigate(project)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-blue-50 p-2.5">
                      <FolderKanban className="h-5 w-5 text-blue-600" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-gray-900">{project.name}</h3>
                      <span className={`mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        project.status === "ACTIVE"
                          ? "bg-green-50 text-green-700"
                          : "bg-gray-100 text-gray-500"
                      }`}>
                        {project.status}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(project.id); }}
                      className="hidden rounded-md p-1 text-gray-400 hover:bg-red-50 hover:text-red-500 group-hover:block"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                    <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-blue-500" />
                  </div>
                </div>

                {project.description && (
                  <p className="mt-2 line-clamp-2 text-xs text-gray-500">{project.description}</p>
                )}

                {/* Stats row */}
                <div className="mt-4 flex items-center gap-4 border-t pt-3">
                  <div className="flex items-center gap-1.5 text-xs text-gray-500">
                    <FileText className="h-3.5 w-3.5" />
                    <span className="font-medium text-gray-700">{stats.docs}</span> docs
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-gray-500">
                    <GitBranch className="h-3.5 w-3.5" />
                    <span className="font-medium text-gray-700">{stats.repos}</span> repos
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-gray-500">
                    <Network className="h-3.5 w-3.5" />
                    <span className="font-medium text-gray-700">{stats.concepts}</span> concepts
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Dialog */}
      {showCreateDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">New Project</h2>
              <button onClick={() => setShowCreateDialog(false)} className="rounded-md p-1 hover:bg-gray-100">
                <X className="h-5 w-5 text-gray-400" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Project Name *</label>
                <input
                  type="text"
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  placeholder="e.g., Payment Service, User Auth Module"
                  className="w-full rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  autoFocus
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Description</label>
                <textarea
                  value={createDescription}
                  onChange={(e) => setCreateDescription(e.target.value)}
                  placeholder="Brief description of this project..."
                  rows={3}
                  className="w-full rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setShowCreateDialog(false)}
                className="rounded-md border px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !createName.trim()}
                className="flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {creating && <Loader2 className="h-4 w-4 animate-spin" />}
                Create Project
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
