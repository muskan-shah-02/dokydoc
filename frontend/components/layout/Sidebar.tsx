/**
 * Sidebar Component
 * Sprint 2 Extended - Multi-Tenancy & RBAC Support
 *
 * Features:
 * - Role-based navigation menu
 * - Active route highlighting
 * - Permission-based visibility
 * - Mobile-responsive with toggle
 */

"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth, Permission } from "@/contexts/AuthContext";
import {
  LayoutDashboard,
  FileText,
  Code,
  CheckSquare,
  ListTodo,
  Users,
  CreditCard,
  Settings,
  Shield,
  BarChart3,
  FolderOpen,
  X,
} from "lucide-react";
import { ReactNode } from "react";

interface MenuItem {
  label: string;
  href: string;
  icon: ReactNode;
  permission?: Permission | string;
  roles?: string[];
  badge?: string | number;
}

interface MenuSection {
  title?: string;
  items: MenuItem[];
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { user, hasPermission, hasAnyPermission, isCXO } = useAuth();

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
    {
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
    },
    {
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
    },
    {
      title: "Management",
      items: [
        {
          label: "Users",
          href: "/users",
          icon: <Users className="h-5 w-5" />,
          permission: Permission.USER_VIEW,
          roles: ["CXO"],
        },
        {
          label: "Billing",
          href: "/billing",
          icon: <CreditCard className="h-5 w-5" />,
          permission: Permission.BILLING_VIEW,
          roles: ["CXO"],
        },
        {
          label: "Organization",
          href: "/settings/organization",
          icon: <Settings className="h-5 w-5" />,
          roles: ["CXO"],
        },
        {
          label: "Permissions",
          href: "/permissions",
          icon: <Shield className="h-5 w-5" />,
        },
        {
          label: "My Profile",
          href: "/settings",
          icon: <Settings className="h-5 w-5" />,
        },
      ],
    },
  ];

  /**
   * Check if user can see a menu item
   */
  const canSeeMenuItem = (item: MenuItem): boolean => {
    // Check role requirement
    if (item.roles && item.roles.length > 0) {
      const hasRole = item.roles.some((role) =>
        user?.roles.includes(role)
      );
      if (!hasRole) return false;
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
                    const isActive = pathname === item.href;

                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => {
                          // Close mobile menu when clicking a link
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

                        {/* Badge */}
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
