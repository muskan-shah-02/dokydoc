/**
 * Sidebar Component
 * Restored to match main branch structure with RBAC enhancements
 *
 * Features:
 * - All menu items visible: Dashboard, Documents, Code, Validation, etc.
 * - Collapsible sidebar
 * - Settings submenu with role-based items
 * - User profile section at bottom
 * - SPRINT 3: Business Ontology dashboard link
 */

"use client";

import React, { useState, useEffect, createContext, useContext } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth, Permission, Role } from "@/contexts/AuthContext";
import { useProject } from "@/contexts/ProjectContext";
import {
  LayoutDashboard,
  FileText,
  Code,
  GitBranch,
  CheckSquare,
  History,
  Download,
  ShieldCheck,
  Network,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  User,
  Users,
  Building2,
  CreditCard,
  Shield,
  X,
  FolderKanban,
  Plus,
  Check,
  BrainCircuit,
  Search,
  Sparkles,
} from "lucide-react";

// Context for sidebar collapsed state
const SidebarContext = createContext({ isCollapsed: false });

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { user, tenant, isCXO, isAdmin, hasPermission, logout } = useAuth();
  const { selectedProject, setSelectedProject, projects, refreshProjects } = useProject();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [settingsExpanded, setSettingsExpanded] = useState(pathname.startsWith("/settings"));
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false);

  // Check if user can access management features
  const canAccessManagement = isCXO() || isAdmin();

  // Main menu items - visible to all authenticated users
  const mainMenuItems = [
    {
      icon: LayoutDashboard,
      text: "Dashboard",
      href: "/dashboard",
    },
    {
      icon: Sparkles,
      text: "AskyDoc",
      href: "/dashboard/chat",
      badge: "AI",
    },
    {
      icon: FileText,
      text: "Documents",
      href: "/dashboard/documents",
    },
    {
      icon: Code,
      text: "Code",
      href: "/dashboard/code",
    },
    {
      icon: GitBranch,
      text: "Visual Architecture",
      href: "/dashboard/visual-architecture",
      badge: "New",
    },
    {
      icon: CheckSquare,
      text: "Validation Panel",
      href: "/dashboard/validation-panel",
    },
    {
      icon: FolderKanban,
      text: "Projects",
      href: "/dashboard/projects",
      badge: "New",
    },
    {
      icon: Network,
      text: "Business Ontology",
      href: "/dashboard/ontology",
    },
    {
      icon: BrainCircuit,
      text: "Brain",
      href: "/dashboard/brain",
      badge: "New",
    },
    {
      icon: Search,
      text: "Search",
      href: "/dashboard/search",
      badge: "New",
    },
    {
      icon: History,
      text: "Sync Timeline",
      href: "/dashboard/sync-timeline",
    },
    {
      icon: Download,
      text: "Export",
      href: "/dashboard/export",
    },
    {
      icon: ShieldCheck,
      text: "Audit Trail",
      href: "/dashboard/audit-trail",
    },
    {
      icon: CheckSquare,
      text: "Approvals",
      href: "/dashboard/approvals",
      badge: "New",
    },
  ];

  // Settings submenu items - role-based
  const settingsSubItems = [
    {
      icon: User,
      text: "Profile",
      href: "/settings",
      visible: true,
    },
    {
      icon: Shield,
      text: "Permissions",
      href: "/settings/permissions",
      visible: true,
    },
    {
      icon: Users,
      text: "User Management",
      href: "/settings/user_management",
      visible: canAccessManagement,
    },
    {
      icon: Building2,
      text: "Organization",
      href: "/settings/organization",
      visible: canAccessManagement,
    },
    {
      icon: CreditCard,
      text: "Billing",
      href: "/settings/billing",
      visible: canAccessManagement,
    },
  ];

  const visibleSettingsItems = settingsSubItems.filter((item) => item.visible);
  const isSettingsActive = pathname.startsWith("/settings");

  const handleLogout = () => {
    logout();
  };

  return (
    <SidebarContext.Provider value={{ isCollapsed }}>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 bg-white border-r border-gray-200 shadow-sm transition-all duration-300 lg:static ${
          isCollapsed ? "w-20" : "w-64"
        } ${isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}
      >
        <nav className="h-full flex flex-col">
          {/* Logo Header */}
          <div
            className={`flex items-center h-16 border-b border-gray-200 ${
              isCollapsed ? "justify-center px-2" : "px-4"
            }`}
          >
            <Link href="/dashboard" className="flex items-center">
              <svg
                className={`transition-all duration-300 ${
                  isCollapsed ? "h-8 w-8" : "h-9 w-9"
                }`}
                viewBox="0 0 100 80"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M78.6,0.1c-12.2,0-22.1,9.9-22.1,22.1c0,2.4,0.4,4.8,1.2,7c-3.5-2.1-7.6-3.3-12-3.3c-14.9,0-27,12.1-27,27s12.1,27,27,27c6.1,0,11.7-2,16.3-5.5c3.2,3.3,7.7,5.5,12.7,5.5c10.5,0,19-8.5,19-19S89.1,0.1,78.6,0.1z M78.6,57.1c-3.9,0-7-3.1-7-7s3.1-7,7-7s7,3.1,7,7S82.5,57.1,78.6,57.1z"
                  fill="#4A90E2"
                />
                <path
                  d="M20.7,48.2c-0.8-2.3-1.2-4.6-1.2-7c0-12.2,9.9-22.1,22.1-22.1c4.4,0,8.5,1.3,12,3.3c-2.3,13.4-12.1,23.8-25.2,25.6C25.9,56.8,22.9,53,20.7,48.2z"
                  fill="#90B8DE"
                />
              </svg>
              {!isCollapsed && (
                <span className="ml-2 text-xl font-bold text-gray-800">
                  DokyDoc
                  <span className="ml-1.5 text-[10px] font-medium text-purple-500 bg-purple-50 px-1.5 py-0.5 rounded-full align-middle">+ AskyDoc</span>
                </span>
              )}
            </Link>

            {/* Mobile close button */}
            <button
              onClick={onClose}
              className="lg:hidden ml-auto p-2 hover:bg-gray-100 rounded-md"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Tenant Info */}
          {!isCollapsed && tenant && (
            <div className="px-4 py-2 border-b border-gray-100">
              <p className="text-xs text-gray-500">Organization</p>
              <p className="text-sm font-medium text-gray-800 truncate">
                {tenant.name}
              </p>
            </div>
          )}

          {/* Project Selector */}
          {!isCollapsed && (
            <div className="px-3 py-2 border-b border-gray-100">
              <p className="px-1 mb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Project
              </p>
              <div className="relative">
                <button
                  onClick={() => setProjectDropdownOpen(!projectDropdownOpen)}
                  className="w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <FolderKanban className="h-4 w-4 text-blue-500 flex-shrink-0" />
                    <span className="truncate font-medium text-gray-700">
                      {selectedProject ? selectedProject.name : "All Projects"}
                    </span>
                  </div>
                  <ChevronDown className={`h-3.5 w-3.5 text-gray-400 transition-transform ${projectDropdownOpen ? "rotate-180" : ""}`} />
                </button>

                {projectDropdownOpen && (
                  <div className="absolute left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto">
                    {/* All Projects option */}
                    <button
                      onClick={() => {
                        setSelectedProject(null);
                        setProjectDropdownOpen(false);
                      }}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50 transition-colors ${
                        !selectedProject ? "bg-blue-50 text-blue-700 font-medium" : "text-gray-700"
                      }`}
                    >
                      {!selectedProject && <Check className="h-3.5 w-3.5" />}
                      <span className={!selectedProject ? "" : "ml-5"}>All Projects</span>
                    </button>

                    {projects.length > 0 && (
                      <div className="border-t border-gray-100">
                        {projects.map((project) => (
                          <button
                            key={project.id}
                            onClick={() => {
                              setSelectedProject(project);
                              setProjectDropdownOpen(false);
                            }}
                            className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50 transition-colors ${
                              selectedProject?.id === project.id
                                ? "bg-blue-50 text-blue-700 font-medium"
                                : "text-gray-700"
                            }`}
                          >
                            {selectedProject?.id === project.id && <Check className="h-3.5 w-3.5" />}
                            <span className={selectedProject?.id === project.id ? "" : "ml-5"}>
                              {project.name}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Create new project link */}
                    <div className="border-t border-gray-100">
                      <Link
                        href="/dashboard/projects"
                        onClick={() => {
                          setProjectDropdownOpen(false);
                          isOpen && onClose();
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-blue-600 hover:bg-blue-50 transition-colors"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        <span>Manage Projects</span>
                      </Link>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Main Menu */}
          <div className="flex-1 overflow-y-auto py-4 px-3">
            <ul className="space-y-1">
              {mainMenuItems.map((item) => {
                const Icon = item.icon;
                const isActive =
                  pathname === item.href ||
                  (item.href !== "/dashboard" && pathname.startsWith(item.href));

                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={() => isOpen && onClose()}
                      className={`relative flex items-center py-2.5 px-3 rounded-lg font-medium transition-colors ${
                        isActive
                          ? "bg-blue-50 text-blue-700"
                          : "text-gray-600 hover:bg-gray-100"
                      }`}
                    >
                      <Icon className="h-5 w-5 flex-shrink-0" />
                      {!isCollapsed && (
                        <>
                          <span className="ml-3">{item.text}</span>
                          {item.badge && (
                            <span className="ml-auto text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                              {item.badge}
                            </span>
                          )}
                        </>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>

            {/* Settings Section with Submenu */}
            <div className="mt-6 pt-4 border-t border-gray-200">
              {!isCollapsed && (
                <p className="px-3 mb-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  System
                </p>
              )}

              {/* Settings Parent */}
              <button
                onClick={() => setSettingsExpanded(!settingsExpanded)}
                className={`w-full flex items-center justify-between py-2.5 px-3 rounded-lg font-medium transition-colors ${
                  isSettingsActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <div className="flex items-center">
                  <Settings className="h-5 w-5 flex-shrink-0" />
                  {!isCollapsed && <span className="ml-3">Settings</span>}
                </div>
                {!isCollapsed && (
                  <span>
                    {settingsExpanded ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </span>
                )}
              </button>

              {/* Settings Submenu */}
              {settingsExpanded && !isCollapsed && (
                <ul className="mt-1 ml-4 pl-4 border-l border-gray-200 space-y-1">
                  {visibleSettingsItems.map((item) => {
                    const Icon = item.icon;
                    const isSubActive = pathname === item.href;

                    return (
                      <li key={item.href}>
                        <Link
                          href={item.href}
                          onClick={() => isOpen && onClose()}
                          className={`flex items-center py-2 px-3 rounded-lg text-sm transition-colors ${
                            isSubActive
                              ? "bg-blue-50 text-blue-700 font-medium"
                              : "text-gray-600 hover:bg-gray-100"
                          }`}
                        >
                          <Icon className="h-4 w-4 flex-shrink-0" />
                          <span className="ml-3">{item.text}</span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>

          {/* User Profile Section */}
          <div className="border-t border-gray-200 p-4">
            <div className="flex items-center">
              <div className="flex-shrink-0 h-10 w-10 rounded-full bg-blue-600 flex items-center justify-center text-white font-semibold">
                {user?.email?.charAt(0).toUpperCase() || "U"}
              </div>
              {!isCollapsed && (
                <div className="ml-3 flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {user?.email}
                  </p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {user?.roles?.slice(0, 2).map((role) => (
                      <span
                        key={role}
                        className={`text-xs px-1.5 py-0.5 rounded ${
                          role === "CXO"
                            ? "bg-purple-100 text-purple-700"
                            : role === "Admin"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {role}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {!isCollapsed && (
                <button
                  onClick={handleLogout}
                  className="ml-2 p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                  title="Logout"
                >
                  <LogOut className="h-5 w-5" />
                </button>
              )}
            </div>
          </div>

          {/* Collapse Toggle Button */}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="hidden lg:flex absolute -right-3 top-20 p-1.5 rounded-full bg-white border border-gray-200 text-gray-600 hover:bg-gray-100 shadow-sm"
          >
            {isCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </button>
        </nav>
      </aside>
    </SidebarContext.Provider>
  );
}
