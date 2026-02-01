/**
 * Sidebar Component
 * Sprint 2 Refinement - FR-03: Unified Sidebar Navigation
 *
 * Features:
 * - Nested menus with hover/click expansion
 * - Context-sensitive menu based on current view
 * - Role-based visibility:
 *   - "Work" section: CXO, Developer, BA (not Admin)
 *   - "Management" section: CXO, Admin
 * - Active route highlighting
 * - Mobile-responsive with toggle
 */

"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth, Permission, Role } from "@/contexts/AuthContext";
import {
  LayoutDashboard,
  FileText,
  Code,
  CheckSquare,
  ListTodo,
  Users,
  CreditCard,
  Settings,
  BarChart3,
  FolderOpen,
  X,
  ChevronDown,
  ChevronRight,
  User,
  Building2,
  Shield,
  Crown,
  Briefcase,
} from "lucide-react";
import { ReactNode } from "react";

interface MenuItem {
  label: string;
  href: string;
  icon: ReactNode;
  permission?: Permission | string;
  roles?: Role[];
  badge?: string | number;
}

interface MenuSection {
  title?: string;
  items: MenuItem[];
  collapsible?: boolean;
  defaultOpen?: boolean;
}

interface NestedMenuItem {
  label: string;
  icon: ReactNode;
  permission?: Permission | string;
  roles?: Role[];
  children: MenuItem[];
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { user, hasPermission, isCXO, isAdmin, hasRole } = useAuth();
  const [expandedMenus, setExpandedMenus] = useState<string[]>(["settings"]);

  // Check if user can access Work modules (Documents, Code, Tasks, Validation)
  const canAccessWork = isCXO() || hasRole(Role.DEVELOPER) || hasRole(Role.BA) || hasRole(Role.PRODUCT_MANAGER);

  // Check if user can access Management modules (Users, Billing, Org)
  const canAccessManagement = isCXO() || isAdmin();

  // Determine current dashboard context for highlighting
  const getCurrentDashboardType = (): string => {
    if (pathname.startsWith("/dashboard/cxo")) return "cxo";
    if (pathname.startsWith("/dashboard/admin")) return "admin";
    if (pathname.startsWith("/dashboard/developer")) return "developer";
    if (pathname.startsWith("/dashboard/ba")) return "ba";
    return "general";
  };

  const dashboardType = getCurrentDashboardType();

  // Define menu structure with RBAC
  const menuSections: MenuSection[] = [
    {
      title: "Main",
      items: [
        {
          label: "Dashboard",
          href: "/dashboard",
          icon: <LayoutDashboard className="h-5 w-5" />,
        },
      ],
    },
  ];

  // Work section - visible to CXO, Developer, BA, PM (NOT Admin)
  if (canAccessWork) {
    menuSections.push({
      title: "Work",
      items: [
        {
          label: "Documents",
          href: "/documents",
          icon: <FileText className="h-5 w-5" />,
          permission: Permission.DOCUMENT_READ,
        },
        {
          label: "Code Components",
          href: "/code",
          icon: <Code className="h-5 w-5" />,
          permission: Permission.CODE_READ,
        },
        {
          label: "Tasks",
          href: "/tasks",
          icon: <ListTodo className="h-5 w-5" />,
          permission: Permission.TASK_READ,
        },
        {
          label: "Validation",
          href: "/validation",
          icon: <CheckSquare className="h-5 w-5" />,
          permission: Permission.VALIDATION_VIEW,
        },
      ],
    });
  }

  // Analytics section
  menuSections.push({
    title: "Analytics",
    items: [
      {
        label: "Analysis",
        href: "/analysis",
        icon: <BarChart3 className="h-5 w-5" />,
        permission: Permission.ANALYSIS_VIEW,
      },
      {
        label: "Reports",
        href: "/reports",
        icon: <FolderOpen className="h-5 w-5" />,
      },
    ],
  });

  // Management section - visible to CXO and Admin only
  if (canAccessManagement) {
    menuSections.push({
      title: "Management",
      items: [
        {
          label: "Users",
          href: "/users",
          icon: <Users className="h-5 w-5" />,
          permission: Permission.USER_VIEW,
        },
        {
          label: "Billing",
          href: "/settings",
          icon: <CreditCard className="h-5 w-5" />,
          permission: Permission.BILLING_VIEW,
        },
      ],
    });
  }

  // Settings submenu items
  const settingsSubItems: MenuItem[] = [
    {
      label: "Profile",
      href: "/settings",
      icon: <User className="h-4 w-4" />,
    },
  ];

  if (canAccessManagement) {
    settingsSubItems.push(
      {
        label: "User Management",
        href: "/settings/user_management",
        icon: <Users className="h-4 w-4" />,
        permission: Permission.USER_MANAGE,
      },
      {
        label: "Organization",
        href: "/settings/organization",
        icon: <Building2 className="h-4 w-4" />,
        permission: Permission.TENANT_VIEW,
      },
      {
        label: "Billing",
        href: "/settings/billing",
        icon: <CreditCard className="h-4 w-4" />,
        permission: Permission.BILLING_VIEW,
      }
    );
  }

  /**
   * Check if user can see a menu item
   */
  const canSeeMenuItem = (item: MenuItem): boolean => {
    // Check role requirement
    if (item.roles && item.roles.length > 0) {
      const hasRequiredRole = item.roles.some((role) => hasRole(role));
      if (!hasRequiredRole) return false;
    }

    // Check permission requirement
    if (item.permission) {
      return hasPermission(item.permission);
    }

    return true;
  };

  /**
   * Filter sections to only show items user can see
   */
  const visibleSections = menuSections
    .map((section) => ({
      ...section,
      items: section.items.filter(canSeeMenuItem),
    }))
    .filter((section) => section.items.length > 0);

  /**
   * Toggle nested menu expansion
   */
  const toggleMenu = (menuId: string) => {
    setExpandedMenus((prev) =>
      prev.includes(menuId)
        ? prev.filter((id) => id !== menuId)
        : [...prev, menuId]
    );
  };

  /**
   * Check if a nested menu is expanded
   */
  const isMenuExpanded = (menuId: string) => expandedMenus.includes(menuId);

  /**
   * Check if any child of settings is active
   */
  const isSettingsActive = pathname.startsWith("/settings");

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 transform border-r bg-white transition-transform duration-200 ease-in-out lg:static lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-full flex-col">
          {/* Mobile Close Button */}
          <div className="flex h-16 items-center justify-between border-b px-4 lg:hidden">
            <span className="text-lg font-semibold">Menu</span>
            <button
              onClick={onClose}
              className="rounded-md p-2 hover:bg-gray-100"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Current View Indicator */}
          <div className="hidden border-b px-4 py-3 lg:block">
            <div className="flex items-center space-x-2">
              {dashboardType === "cxo" && (
                <>
                  <Crown className="h-4 w-4 text-purple-600" />
                  <span className="text-sm font-medium text-purple-600">Executive View</span>
                </>
              )}
              {dashboardType === "admin" && (
                <>
                  <Shield className="h-4 w-4 text-blue-600" />
                  <span className="text-sm font-medium text-blue-600">Admin View</span>
                </>
              )}
              {dashboardType === "developer" && (
                <>
                  <Code className="h-4 w-4 text-green-600" />
                  <span className="text-sm font-medium text-green-600">Developer View</span>
                </>
              )}
              {dashboardType === "ba" && (
                <>
                  <FileText className="h-4 w-4 text-orange-600" />
                  <span className="text-sm font-medium text-orange-600">Analyst View</span>
                </>
              )}
              {dashboardType === "general" && (
                <>
                  <LayoutDashboard className="h-4 w-4 text-gray-600" />
                  <span className="text-sm font-medium text-gray-600">General View</span>
                </>
              )}
            </div>
          </div>

          {/* Menu Items */}
          <nav className="flex-1 space-y-1 overflow-y-auto p-4">
            {visibleSections.map((section, idx) => (
              <div key={idx} className="mb-6">
                {/* Section Title */}
                {section.title && (
                  <h3 className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
                    {section.title}
                  </h3>
                )}

                {/* Section Items */}
                <div className="space-y-1">
                  {section.items.map((item) => {
                    const isActive =
                      pathname === item.href ||
                      (item.href !== "/dashboard" &&
                        pathname.startsWith(item.href + "/"));

                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => {
                          if (isOpen) onClose();
                        }}
                        className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                          isActive
                            ? "bg-blue-50 text-blue-600"
                            : "text-gray-700 hover:bg-gray-100"
                        }`}
                      >
                        <div className="flex items-center space-x-3">
                          <span
                            className={
                              isActive ? "text-blue-600" : "text-gray-500"
                            }
                          >
                            {item.icon}
                          </span>
                          <span>{item.label}</span>
                        </div>

                        {item.badge && (
                          <span className="rounded-full bg-blue-600 px-2 py-0.5 text-xs font-semibold text-white">
                            {item.badge}
                          </span>
                        )}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}

            {/* Settings with Nested Menu */}
            <div className="mb-6">
              <h3 className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
                System
              </h3>

              {/* Settings Parent */}
              <button
                onClick={() => toggleMenu("settings")}
                onMouseEnter={() => {
                  if (!isMenuExpanded("settings")) {
                    toggleMenu("settings");
                  }
                }}
                className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isSettingsActive
                    ? "bg-blue-50 text-blue-600"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <div className="flex items-center space-x-3">
                  <span className={isSettingsActive ? "text-blue-600" : "text-gray-500"}>
                    <Settings className="h-5 w-5" />
                  </span>
                  <span>Settings</span>
                </div>
                <span className={isSettingsActive ? "text-blue-600" : "text-gray-500"}>
                  {isMenuExpanded("settings") ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </span>
              </button>

              {/* Settings Submenu */}
              {isMenuExpanded("settings") && (
                <div className="ml-4 mt-1 space-y-1 border-l pl-4">
                  {settingsSubItems.filter(canSeeMenuItem).map((item) => {
                    const isSubActive = pathname === item.href;

                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => {
                          if (isOpen) onClose();
                        }}
                        className={`flex items-center space-x-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                          isSubActive
                            ? "bg-blue-50 text-blue-600 font-medium"
                            : "text-gray-600 hover:bg-gray-100"
                        }`}
                      >
                        <span className={isSubActive ? "text-blue-600" : "text-gray-400"}>
                          {item.icon}
                        </span>
                        <span>{item.label}</span>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </nav>

          {/* User Info Footer */}
          <div className="border-t p-4">
            <div className="rounded-lg bg-gray-50 p-3">
              <div className="flex items-center space-x-3">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-semibold text-white">
                  {user?.email.charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-900">
                    {user?.email}
                  </p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {user?.roles.slice(0, 2).map((role) => (
                      <span
                        key={role}
                        className={`rounded px-1.5 py-0.5 text-xs font-medium ${
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
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
