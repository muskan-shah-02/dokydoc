/**
 * Permission Guard Components
 * Sprint 2 Extended - RBAC Support
 *
 * Components and hooks for permission-based access control:
 * - RequirePermission: Hides content if user lacks permission
 * - RequireRole: Hides content if user lacks role
 * - ProtectedRoute: Redirects if user lacks permission
 * - usePermissionGuard: Hook for programmatic permission checks
 */

"use client";

import { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth, Permission } from "@/contexts/AuthContext";
import { Ban } from "lucide-react";

// ============================================================================
// RequirePermission Component
// ============================================================================

interface RequirePermissionProps {
  permission: Permission | string;
  children: ReactNode;
  fallback?: ReactNode;
  mode?: "any" | "all"; // For multiple permissions
  permissions?: (Permission | string)[]; // For multiple permissions
}

/**
 * Component that only renders children if user has the required permission(s)
 *
 * @example
 * // Single permission
 * <RequirePermission permission={Permission.DOCUMENT_WRITE}>
 *   <Button>Create Document</Button>
 * </RequirePermission>
 *
 * @example
 * // Multiple permissions (any)
 * <RequirePermission
 *   permissions={[Permission.DOCUMENT_WRITE, Permission.DOCUMENT_DELETE]}
 *   mode="any"
 * >
 *   <Button>Edit Document</Button>
 * </RequirePermission>
 *
 * @example
 * // With fallback
 * <RequirePermission
 *   permission={Permission.BILLING_VIEW}
 *   fallback={<p>Contact admin for billing access</p>}
 * >
 *   <BillingDashboard />
 * </RequirePermission>
 */
export function RequirePermission({
  permission,
  children,
  fallback = null,
  mode = "any",
  permissions = [],
}: RequirePermissionProps) {
  const { hasPermission, hasAnyPermission, hasAllPermissions } = useAuth();

  // Check multiple permissions
  if (permissions.length > 0) {
    const hasAccess =
      mode === "all"
        ? hasAllPermissions(permissions)
        : hasAnyPermission(permissions);

    return hasAccess ? <>{children}</> : <>{fallback}</>;
  }

  // Check single permission
  const hasAccess = hasPermission(permission);
  return hasAccess ? <>{children}</> : <>{fallback}</>;
}

// ============================================================================
// RequireRole Component
// ============================================================================

interface RequireRoleProps {
  role: string;
  roles?: string[];
  mode?: "any" | "all";
  children: ReactNode;
  fallback?: ReactNode;
}

/**
 * Component that only renders children if user has the required role(s)
 *
 * @example
 * // Single role
 * <RequireRole role="CXO">
 *   <AdminPanel />
 * </RequireRole>
 *
 * @example
 * // Multiple roles (any)
 * <RequireRole roles={["CXO", "PM"]} mode="any">
 *   <TeamManagement />
 * </RequireRole>
 */
export function RequireRole({
  role,
  roles = [],
  mode = "any",
  children,
  fallback = null,
}: RequireRoleProps) {
  const { user } = useAuth();

  if (!user) return <>{fallback}</>;

  // Check multiple roles
  if (roles.length > 0) {
    const hasAccess =
      mode === "all"
        ? roles.every((r) => user.roles.includes(r))
        : roles.some((r) => user.roles.includes(r));

    return hasAccess ? <>{children}</> : <>{fallback}</>;
  }

  // Check single role
  const hasAccess = user.roles.includes(role);
  return hasAccess ? <>{children}</> : <>{fallback}</>;
}

// ============================================================================
// ProtectedRoute Component
// ============================================================================

interface ProtectedRouteProps {
  permission?: Permission | string;
  permissions?: (Permission | string)[];
  mode?: "any" | "all";
  role?: string;
  roles?: string[];
  redirectTo?: string;
  children: ReactNode;
  showForbidden?: boolean;
}

/**
 * Component that protects routes with permission/role checks
 * Redirects to specified page or shows forbidden message if access denied
 *
 * @example
 * // Protect with permission
 * <ProtectedRoute permission={Permission.BILLING_MANAGE}>
 *   <BillingSettings />
 * </ProtectedRoute>
 *
 * @example
 * // Protect with role
 * <ProtectedRoute role="CXO" redirectTo="/dashboard">
 *   <AdminDashboard />
 * </ProtectedRoute>
 */
export function ProtectedRoute({
  permission,
  permissions = [],
  mode = "any",
  role,
  roles = [],
  redirectTo = "/dashboard",
  children,
  showForbidden = true,
}: ProtectedRouteProps) {
  const router = useRouter();
  const { user, hasPermission, hasAnyPermission, hasAllPermissions } = useAuth();

  // Check permissions
  let hasPermissionAccess = true;
  if (permission) {
    hasPermissionAccess = hasPermission(permission);
  } else if (permissions.length > 0) {
    hasPermissionAccess =
      mode === "all"
        ? hasAllPermissions(permissions)
        : hasAnyPermission(permissions);
  }

  // Check roles
  let hasRoleAccess = true;
  if (user) {
    if (role) {
      hasRoleAccess = user.roles.includes(role);
    } else if (roles.length > 0) {
      hasRoleAccess =
        mode === "all"
          ? roles.every((r) => user.roles.includes(r))
          : roles.some((r) => user.roles.includes(r));
    }
  }

  const hasAccess = hasPermissionAccess && hasRoleAccess;

  // Redirect if no access
  if (!hasAccess) {
    if (showForbidden) {
      return <ForbiddenMessage onGoBack={() => router.push(redirectTo)} />;
    } else {
      router.push(redirectTo);
      return null;
    }
  }

  return <>{children}</>;
}

// ============================================================================
// Forbidden Message Component
// ============================================================================

function ForbiddenMessage({ onGoBack }: { onGoBack: () => void }) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-8">
      <div className="text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
          <Ban className="h-8 w-8 text-red-600" />
        </div>
        <h2 className="mt-6 text-2xl font-bold text-gray-900">Access Denied</h2>
        <p className="mt-2 text-gray-600">
          You don't have permission to access this page.
        </p>
        <button
          onClick={onGoBack}
          className="mt-6 rounded-lg bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Go Back
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook for programmatic permission guards
 *
 * @example
 * const { canCreate, canDelete } = usePermissionGuard({
 *   canCreate: Permission.DOCUMENT_WRITE,
 *   canDelete: Permission.DOCUMENT_DELETE,
 * });
 *
 * if (canCreate) {
 *   // Show create button
 * }
 */
export function usePermissionGuard<T extends Record<string, Permission | string>>(
  permissions: T
): Record<keyof T, boolean> {
  const { hasPermission } = useAuth();

  const guards = Object.entries(permissions).reduce((acc, [key, permission]) => {
    acc[key as keyof T] = hasPermission(permission as Permission | string);
    return acc;
  }, {} as Record<keyof T, boolean>);

  return guards;
}

/**
 * Hook for programmatic role guards
 *
 * @example
 * const { isCXO, isPM } = useRoleGuard({
 *   isCXO: 'CXO',
 *   isPM: 'PM',
 * });
 */
export function useRoleGuard<T extends Record<string, string>>(
  roles: T
): Record<keyof T, boolean> {
  const { user } = useAuth();

  const guards = Object.entries(roles).reduce((acc, [key, role]) => {
    acc[key as keyof T] = user?.roles.includes(role as string) || false;
    return acc;
  }, {} as Record<keyof T, boolean>);

  return guards;
}
