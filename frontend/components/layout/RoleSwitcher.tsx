/**
 * Role Switcher Component
 * Sprint 2 Refinement - FR-02
 *
 * Allows users with multiple roles to switch between different dashboard views.
 * Displays in the navbar for users with 2+ roles.
 */

"use client";

import { useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth, Role, ROLE_DASHBOARD_MAP } from "@/contexts/AuthContext";
import {
  ChevronDown,
  Crown,
  Shield,
  Code,
  FileText,
  Briefcase,
  Check,
} from "lucide-react";

// Role icons mapping
const ROLE_ICONS: Record<Role, React.ReactNode> = {
  [Role.CXO]: <Crown className="h-4 w-4" />,
  [Role.ADMIN]: <Shield className="h-4 w-4" />,
  [Role.DEVELOPER]: <Code className="h-4 w-4" />,
  [Role.BA]: <FileText className="h-4 w-4" />,
  [Role.PRODUCT_MANAGER]: <Briefcase className="h-4 w-4" />,
};

// Role display names
const ROLE_LABELS: Record<Role, string> = {
  [Role.CXO]: "Executive",
  [Role.ADMIN]: "Admin",
  [Role.DEVELOPER]: "Developer",
  [Role.BA]: "Analyst",
  [Role.PRODUCT_MANAGER]: "Product Manager",
};

// Role colors
const ROLE_COLORS: Record<Role, { bg: string; text: string }> = {
  [Role.CXO]: { bg: "bg-purple-100", text: "text-purple-700" },
  [Role.ADMIN]: { bg: "bg-blue-100", text: "text-blue-700" },
  [Role.DEVELOPER]: { bg: "bg-green-100", text: "text-green-700" },
  [Role.BA]: { bg: "bg-orange-100", text: "text-orange-700" },
  [Role.PRODUCT_MANAGER]: { bg: "bg-gray-100", text: "text-gray-700" },
};

export function RoleSwitcher() {
  const router = useRouter();
  const pathname = usePathname();
  const { getAvailableDashboards, getPrimaryRole } = useAuth();
  const [isOpen, setIsOpen] = useState(false);

  const availableDashboards = getAvailableDashboards();
  const primaryRole = getPrimaryRole();

  // Don't show switcher if user has only one role
  if (availableDashboards.length <= 1) {
    return null;
  }

  // Determine current active view based on URL
  const getCurrentRole = (): Role | null => {
    if (pathname.startsWith("/dashboard/cxo")) return Role.CXO;
    if (pathname.startsWith("/dashboard/admin")) return Role.ADMIN;
    if (pathname.startsWith("/dashboard/developer")) return Role.DEVELOPER;
    if (pathname.startsWith("/dashboard/ba")) return Role.BA;
    return primaryRole;
  };

  const currentRole = getCurrentRole();
  const currentRoleConfig = currentRole ? ROLE_COLORS[currentRole] : { bg: "bg-gray-100", text: "text-gray-700" };

  const handleSwitchRole = (role: Role) => {
    const dashboardUrl = ROLE_DASHBOARD_MAP[role];
    setIsOpen(false);
    router.push(dashboardUrl);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center space-x-2 rounded-lg px-3 py-1.5 transition-colors hover:bg-gray-100 ${currentRoleConfig.bg}`}
      >
        {currentRole && ROLE_ICONS[currentRole]}
        <span className={`text-sm font-medium ${currentRoleConfig.text}`}>
          {currentRole ? ROLE_LABELS[currentRole] : "Switch View"}
        </span>
        <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? "rotate-180" : ""} ${currentRoleConfig.text}`} />
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />

          {/* Dropdown */}
          <div className="absolute right-0 z-20 mt-2 w-56 rounded-lg border bg-white shadow-lg">
            <div className="p-2">
              <p className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                Switch View
              </p>
              {availableDashboards.map(({ role, url, label }) => {
                const isActive = currentRole === role;
                const colors = ROLE_COLORS[role];

                return (
                  <button
                    key={role}
                    onClick={() => handleSwitchRole(role)}
                    className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-sm transition-colors ${
                      isActive ? `${colors.bg} ${colors.text}` : "hover:bg-gray-100"
                    }`}
                  >
                    <div className="flex items-center space-x-3">
                      <span className={isActive ? colors.text : "text-gray-500"}>
                        {ROLE_ICONS[role]}
                      </span>
                      <span className={isActive ? "font-medium" : "text-gray-700"}>
                        {label}
                      </span>
                    </div>
                    {isActive && <Check className="h-4 w-4" />}
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
