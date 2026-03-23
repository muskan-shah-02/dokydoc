/**
 * Auth Components and Hooks
 * Sprint 2 Extended - RBAC Support
 *
 * Export all authentication and permission-related components and hooks
 */

export {
  RequirePermission,
  RequireRole,
  ProtectedRoute,
  usePermissionGuard,
  useRoleGuard,
} from "./PermissionGuard";
