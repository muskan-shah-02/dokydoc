/**
 * Authentication Context
 * Sprint 2 Extended - Multi-Tenancy & RBAC Support
 *
 * Manages:
 * - User authentication state
 * - Tenant information
 * - User permissions
 * - Login/logout functions
 * - Permission checking
 */

'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { api, User, Tenant, ApiError } from '@/lib/api';

// Role enum matching backend
export enum Role {
  CXO = 'CXO',
  ADMIN = 'Admin',
  BA = 'BA',
  DEVELOPER = 'Developer',
  PRODUCT_MANAGER = 'Product Manager',
}

// Permission enum matching backend
export enum Permission {
  DOCUMENT_READ = 'document:read',
  DOCUMENT_WRITE = 'document:write',
  DOCUMENT_DELETE = 'document:delete',
  DOCUMENT_ANALYZE = 'document:analyze',
  CODE_READ = 'code:read',
  CODE_WRITE = 'code:write',
  CODE_DELETE = 'code:delete',
  ANALYSIS_VIEW = 'analysis:view',
  ANALYSIS_RUN = 'analysis:run',
  VALIDATION_VIEW = 'validation:view',
  VALIDATION_RUN = 'validation:run',
  TASK_READ = 'task:read',
  TASK_CREATE = 'task:create',
  TASK_UPDATE = 'task:update',
  TASK_DELETE = 'task:delete',
  TASK_ASSIGN = 'task:assign',
  TASK_COMMENT = 'task:comment',
  BILLING_VIEW = 'billing:view',
  BILLING_MANAGE = 'billing:manage',
  USER_VIEW = 'user:view',
  USER_INVITE = 'user:invite',
  USER_MANAGE = 'user:manage',
  USER_DELETE = 'user:delete',
  TENANT_VIEW = 'tenant:view',
  TENANT_MANAGE = 'tenant:manage',
  // Dashboard Permissions
  DASHBOARD_DEVELOPER = 'dashboard:developer',
  DASHBOARD_BA = 'dashboard:ba',
  DASHBOARD_CXO = 'dashboard:cxo',
  DASHBOARD_ADMIN = 'dashboard:admin',
  DASHBOARD_PM = 'dashboard:pm',
}

// Role priority for determining primary dashboard
const ROLE_PRIORITY: Role[] = [Role.CXO, Role.ADMIN, Role.DEVELOPER, Role.BA, Role.PRODUCT_MANAGER];

// Role to dashboard URL mapping
export const ROLE_DASHBOARD_MAP: Record<Role, string> = {
  [Role.CXO]: '/dashboard/cxo',
  [Role.ADMIN]: '/dashboard/admin',
  [Role.DEVELOPER]: '/dashboard/developer',
  [Role.BA]: '/dashboard/ba',
  [Role.PRODUCT_MANAGER]: '/dashboard/developer', // PM uses developer dashboard
};

interface AuthContextType {
  // State
  user: User | null;
  tenant: Tenant | null;
  permissions: string[];
  isLoading: boolean;
  isAuthenticated: boolean;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;

  // Permission checking
  hasPermission: (permission: Permission | string) => boolean;
  hasAnyPermission: (permissions: (Permission | string)[]) => boolean;
  hasAllPermissions: (permissions: (Permission | string)[]) => boolean;

  // Role checking
  isCXO: () => boolean;
  isAdmin: () => boolean;
  isDeveloper: () => boolean;
  isBA: () => boolean;
  hasRole: (role: Role | string) => boolean;
  getPrimaryRole: () => Role | null;
  getPrimaryDashboardUrl: () => string;
  getAvailableDashboards: () => { role: Role; url: string; label: string }[];
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const isAuthenticated = !!user;

  /**
   * Load permissions from backend
   */
  const loadPermissions = async () => {
    if (!user) {
      setPermissions([]);
      return;
    }

    try {
      const response = await api.get<{ permissions: string[] }>('/users/me/permissions');
      setPermissions(response.permissions || []);
    } catch (error) {
      console.error('Failed to load permissions:', error);
      setPermissions([]);
    }
  };

  /**
   * Load user and tenant from localStorage on mount
   */
  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    const storedUser = localStorage.getItem('user');
    const storedTenant = localStorage.getItem('tenant');

    if (token && storedUser && storedTenant) {
      try {
        setUser(JSON.parse(storedUser));
        setTenant(JSON.parse(storedTenant));
      } catch (error) {
        console.error('Failed to parse stored auth data:', error);
        localStorage.removeItem('accessToken');
        localStorage.removeItem('user');
        localStorage.removeItem('tenant');
      }
    }

    setIsLoading(false);
  }, []);

  /**
   * Load permissions when user changes
   */
  useEffect(() => {
    if (user) {
      loadPermissions();
    } else {
      setPermissions([]);
    }
  }, [user]);

  /**
   * Login function
   */
  const login = async (email: string, password: string) => {
    setIsLoading(true);

    try {
      const response = await api.login(email, password);

      // Store token
      localStorage.setItem('accessToken', response.access_token);

      // Store user and tenant
      localStorage.setItem('user', JSON.stringify(response.user));
      localStorage.setItem('tenant', JSON.stringify(response.tenant));

      // Update state
      setUser(response.user);
      setTenant(response.tenant);

      // Permissions will be loaded by useEffect
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Logout function
   */
  const logout = () => {
    // Clear localStorage
    localStorage.removeItem('accessToken');
    localStorage.removeItem('user');
    localStorage.removeItem('tenant');

    // Clear state
    setUser(null);
    setTenant(null);
    setPermissions([]);

    // Redirect to login
    router.push('/');
  };

  /**
   * Check if user has a specific permission
   */
  const hasPermission = (permission: Permission | string): boolean => {
    if (!permissions || !Array.isArray(permissions)) return false;
    return permissions.includes(permission);
  };

  /**
   * Check if user has ANY of the specified permissions
   */
  const hasAnyPermission = (perms: (Permission | string)[]): boolean => {
    if (!permissions || !Array.isArray(permissions)) return false;
    return perms.some((p) => permissions.includes(p));
  };

  /**
   * Check if user has ALL of the specified permissions
   */
  const hasAllPermissions = (perms: (Permission | string)[]): boolean => {
    if (!permissions || !Array.isArray(permissions)) return false;
    return perms.every((p) => permissions.includes(p));
  };

  /**
   * Check if user has a specific role
   */
  const hasRole = (role: Role | string): boolean => {
    if (!user?.roles) return false;
    return user.roles.includes(role);
  };

  /**
   * Check if user is a CXO (tenant owner - "God Mode")
   */
  const isCXO = (): boolean => hasRole(Role.CXO);

  /**
   * Check if user is an Admin (operations manager)
   */
  const isAdmin = (): boolean => hasRole(Role.ADMIN);

  /**
   * Check if user is a Developer
   */
  const isDeveloper = (): boolean => hasRole(Role.DEVELOPER);

  /**
   * Check if user is a Business Analyst
   */
  const isBA = (): boolean => hasRole(Role.BA);

  /**
   * Get user's primary role (highest priority)
   * Used to determine default dashboard
   */
  const getPrimaryRole = (): Role | null => {
    if (!user?.roles) return null;
    for (const role of ROLE_PRIORITY) {
      if (user.roles.includes(role)) {
        return role;
      }
    }
    return null;
  };

  /**
   * Get the URL for the user's primary dashboard
   */
  const getPrimaryDashboardUrl = (): string => {
    const primaryRole = getPrimaryRole();
    if (primaryRole && ROLE_DASHBOARD_MAP[primaryRole]) {
      return ROLE_DASHBOARD_MAP[primaryRole];
    }
    return '/dashboard/developer'; // Default fallback
  };

  /**
   * Get list of all dashboards the user can access
   * Used for the Role Switcher component
   */
  const getAvailableDashboards = (): { role: Role; url: string; label: string }[] => {
    if (!user?.roles) return [];

    const dashboards: { role: Role; url: string; label: string }[] = [];
    const roleLabels: Record<Role, string> = {
      [Role.CXO]: 'Executive',
      [Role.ADMIN]: 'Admin',
      [Role.DEVELOPER]: 'Developer',
      [Role.BA]: 'Analyst',
      [Role.PRODUCT_MANAGER]: 'Product Manager',
    };

    for (const role of ROLE_PRIORITY) {
      if (user.roles.includes(role)) {
        dashboards.push({
          role,
          url: ROLE_DASHBOARD_MAP[role],
          label: roleLabels[role],
        });
      }
    }

    return dashboards;
  };

  const value: AuthContextType = {
    user,
    tenant,
    permissions,
    isLoading,
    isAuthenticated,
    login,
    logout,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    isCXO,
    isAdmin,
    isDeveloper,
    isBA,
    hasRole,
    getPrimaryRole,
    getPrimaryDashboardUrl,
    getAvailableDashboards,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Hook to use auth context
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

/**
 * Hook to require authentication
 * Redirects to login if not authenticated
 */
export function useRequireAuth() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/');
    }
  }, [isAuthenticated, isLoading, router]);

  return { isAuthenticated, isLoading };
}
