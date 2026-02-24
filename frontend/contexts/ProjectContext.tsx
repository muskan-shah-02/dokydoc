"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

interface Initiative {
  id: number;
  name: string;
  description: string | null;
  status: string;
  owner_id: number;
  created_at: string;
  updated_at: string | null;
}

interface ProjectContextType {
  selectedProject: Initiative | null; // null = "All Projects"
  setSelectedProject: (p: Initiative | null) => void;
  projects: Initiative[];
  refreshProjects: () => void;
  isLoadingProjects: boolean;
}

const ProjectContext = createContext<ProjectContextType>({
  selectedProject: null,
  setSelectedProject: () => {},
  projects: [],
  refreshProjects: () => {},
  isLoadingProjects: false,
});

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [selectedProject, setSelectedProjectState] = useState<Initiative | null>(null);
  const [projects, setProjects] = useState<Initiative[]>([]);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);

  // Restore selection from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem("dokydoc_selected_project");
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (parsed && parsed.id) {
          setSelectedProjectState(parsed);
        }
      } catch {
        // Invalid stored value, ignore
      }
    }
  }, []);

  const setSelectedProject = useCallback((p: Initiative | null) => {
    setSelectedProjectState(p);
    if (p) {
      localStorage.setItem("dokydoc_selected_project", JSON.stringify(p));
    } else {
      localStorage.removeItem("dokydoc_selected_project");
    }
  }, []);

  const refreshProjects = useCallback(async () => {
    setIsLoadingProjects(true);
    try {
      const data = await api.get<Initiative[]>("/initiatives/");
      setProjects(data);
      // If the currently selected project was deleted, reset to "All"
      if (selectedProject && !data.find((p) => p.id === selectedProject.id)) {
        setSelectedProject(null);
      }
    } catch (error) {
      console.error("Failed to fetch projects:", error);
      setProjects([]);
    } finally {
      setIsLoadingProjects(false);
    }
  }, [selectedProject, setSelectedProject]);

  // Initial fetch
  useEffect(() => {
    const token = localStorage.getItem("accessToken");
    if (token) {
      refreshProjects();
    }
  }, [refreshProjects]);

  return (
    <ProjectContext.Provider
      value={{
        selectedProject,
        setSelectedProject,
        projects,
        refreshProjects,
        isLoadingProjects,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  return useContext(ProjectContext);
}

export type { Initiative };
