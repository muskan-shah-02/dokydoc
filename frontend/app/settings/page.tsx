/**
 * Settings Page
 * Sprint 2 Extended - Multi-Tenancy Support
 *
 * Features:
 * - User profile settings
 * - Password change
 * - Tenant settings (CXO only)
 * - My permissions view
 */

"use client";

import { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth, Permission } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  Settings as SettingsIcon,
  User,
  Lock,
  Building2,
  Shield,
  Save,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function SettingsPage() {
  const { user, tenant, isCXO, permissions } = useAuth();
  const [activeTab, setActiveTab] = useState("profile");

  const tabs = [
    { id: "profile", label: "Profile", icon: <User className="h-4 w-4" /> },
    { id: "password", label: "Password", icon: <Lock className="h-4 w-4" /> },
    { id: "permissions", label: "My Permissions", icon: <Shield className="h-4 w-4" /> },
  ];

  // Add tenant settings tab for CXO
  if (isCXO()) {
    tabs.splice(2, 0, {
      id: "tenant",
      label: "Organization",
      icon: <Building2 className="h-4 w-4" />,
    });
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
          <p className="mt-2 text-gray-600">
            Manage your account and organization settings
          </p>
        </div>

        {/* Tabs */}
        <div className="border-b">
          <nav className="-mb-px flex space-x-8">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 border-b-2 px-1 py-4 text-sm font-medium ${
                  activeTab === tab.id
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          {activeTab === "profile" && <ProfileTab user={user} />}
          {activeTab === "password" && <PasswordTab />}
          {activeTab === "tenant" && isCXO() && <TenantTab tenant={tenant} />}
          {activeTab === "permissions" && <PermissionsTab permissions={permissions} />}
        </div>
      </div>
    </AppLayout>
  );
}

// ============================================================================
// Profile Tab
// ============================================================================

function ProfileTab({ user }: { user: any }) {
  const [email, setEmail] = useState(user?.email || "");
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSave = async () => {
    setIsLoading(true);
    setSuccess(false);

    try {
      await api.put("/users/me/", { email });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (error) {
      console.error("Failed to update profile:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Profile Information</h3>
        <p className="mt-1 text-sm text-gray-600">
          Update your account information
        </p>
      </div>

      <div className="max-w-xl space-y-4">
        <div>
          <Label htmlFor="email">Email Address</Label>
          <Input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-2"
          />
        </div>

        <div>
          <Label>Roles</Label>
          <div className="mt-2 flex flex-wrap gap-2">
            {user?.roles.map((role: string) => (
              <span
                key={role}
                className={`rounded px-3 py-1 text-sm font-medium ${
                  role === "CXO"
                    ? "bg-purple-100 text-purple-700"
                    : "bg-gray-100 text-gray-700"
                }`}
              >
                {role}
              </span>
            ))}
          </div>
          <p className="mt-1 text-sm text-gray-500">
            Contact your administrator to change roles
          </p>
        </div>

        <div>
          <Label>Account Created</Label>
          <p className="mt-2 text-sm text-gray-700">
            {new Date(user?.created_at).toLocaleDateString()}
          </p>
        </div>

        {success && (
          <div className="flex items-center space-x-2 rounded-md bg-green-50 p-3 text-green-800">
            <CheckCircle2 className="h-5 w-5" />
            <span className="text-sm font-medium">Profile updated successfully</span>
          </div>
        )}

        <Button onClick={handleSave} disabled={isLoading}>
          <Save className="mr-2 h-4 w-4" />
          {isLoading ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// Password Tab
// ============================================================================

function PasswordTab() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSave = async () => {
    setError(null);
    setSuccess(false);

    // Validation
    if (!currentPassword || !newPassword || !confirmPassword) {
      setError("All fields are required");
      return;
    }

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("New passwords do not match");
      return;
    }

    setIsLoading(true);

    try {
      await api.post("/users/me/password/", {
        current_password: currentPassword,
        new_password: newPassword,
      });

      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.detail || "Failed to change password");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Change Password</h3>
        <p className="mt-1 text-sm text-gray-600">
          Update your password to keep your account secure
        </p>
      </div>

      <div className="max-w-xl space-y-4">
        <div>
          <Label htmlFor="currentPassword">Current Password</Label>
          <Input
            id="currentPassword"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="mt-2"
          />
        </div>

        <div>
          <Label htmlFor="newPassword">New Password</Label>
          <Input
            id="newPassword"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="mt-2"
          />
          <p className="mt-1 text-sm text-gray-500">
            Must be at least 8 characters
          </p>
        </div>

        <div>
          <Label htmlFor="confirmPassword">Confirm New Password</Label>
          <Input
            id="confirmPassword"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-2"
          />
        </div>

        {error && (
          <div className="rounded-md bg-red-50 p-3">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {success && (
          <div className="flex items-center space-x-2 rounded-md bg-green-50 p-3 text-green-800">
            <CheckCircle2 className="h-5 w-5" />
            <span className="text-sm font-medium">Password changed successfully</span>
          </div>
        )}

        <Button onClick={handleSave} disabled={isLoading}>
          <Save className="mr-2 h-4 w-4" />
          {isLoading ? "Changing..." : "Change Password"}
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// Tenant Tab (CXO Only)
// ============================================================================

function TenantTab({ tenant }: { tenant: any }) {
  const [name, setName] = useState(tenant?.name || "");
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSave = async () => {
    setIsLoading(true);
    setSuccess(false);

    try {
      await api.put("/tenants/me/", { name });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (error) {
      console.error("Failed to update tenant:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Organization Settings</h3>
        <p className="mt-1 text-sm text-gray-600">
          Manage your organization details and configuration
        </p>
      </div>

      <div className="max-w-xl space-y-4">
        <div>
          <Label htmlFor="orgName">Organization Name</Label>
          <Input
            id="orgName"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-2"
          />
        </div>

        <div>
          <Label>Subdomain</Label>
          <div className="mt-2 rounded-md bg-gray-50 p-3">
            <p className="text-sm font-medium text-gray-900">
              {tenant?.subdomain}.dokydoc.com
            </p>
          </div>
          <p className="mt-1 text-sm text-gray-500">
            Subdomain cannot be changed after registration
          </p>
        </div>

        <div>
          <Label>Plan</Label>
          <div className="mt-2 flex items-center space-x-3">
            <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-medium capitalize text-blue-700">
              {tenant?.tier || "Free"}
            </span>
            <span className="rounded-full bg-gray-100 px-3 py-1 text-sm font-medium capitalize text-gray-700">
              {tenant?.billing_type || "Prepaid"}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>Max Users</Label>
            <p className="mt-2 text-sm text-gray-700">{tenant?.max_users}</p>
          </div>

          <div>
            <Label>Max Documents</Label>
            <p className="mt-2 text-sm text-gray-700">{tenant?.max_documents}</p>
          </div>
        </div>

        <div>
          <Label>Status</Label>
          <div className="mt-2">
            <span className="inline-flex items-center rounded-full bg-green-100 px-3 py-1 text-sm font-medium capitalize text-green-700">
              {tenant?.status || "Active"}
            </span>
          </div>
        </div>

        {success && (
          <div className="flex items-center space-x-2 rounded-md bg-green-50 p-3 text-green-800">
            <CheckCircle2 className="h-5 w-5" />
            <span className="text-sm font-medium">Settings updated successfully</span>
          </div>
        )}

        <Button onClick={handleSave} disabled={isLoading}>
          <Save className="mr-2 h-4 w-4" />
          {isLoading ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// Permissions Tab
// ============================================================================

function PermissionsTab({ permissions }: { permissions: string[] }) {
  // Group permissions by category
  const permissionsByCategory = permissions.reduce((acc, permission) => {
    const [category] = permission.split(":");
    if (!acc[category]) acc[category] = [];
    acc[category].push(permission);
    return acc;
  }, {} as Record<string, string[]>);

  const categoryLabels: Record<string, string> = {
    document: "Documents",
    code: "Code Components",
    analysis: "Analysis",
    validation: "Validation",
    task: "Tasks",
    billing: "Billing",
    user: "Users",
    tenant: "Organization",
  };

  const permissionLabels: Record<string, string> = {
    read: "View",
    write: "Create/Edit",
    delete: "Delete",
    analyze: "Analyze",
    view: "View",
    run: "Run",
    create: "Create",
    update: "Update",
    assign: "Assign",
    comment: "Comment",
    manage: "Manage",
    invite: "Invite",
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">My Permissions</h3>
        <p className="mt-1 text-sm text-gray-600">
          View all permissions granted to your account
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {Object.entries(permissionsByCategory).map(([category, perms]) => (
          <div key={category} className="rounded-lg border p-4">
            <h4 className="mb-3 font-medium text-gray-900">
              {categoryLabels[category] || category}
            </h4>
            <div className="space-y-2">
              {perms.map((permission) => {
                const [, action] = permission.split(":");
                return (
                  <div key={permission} className="flex items-center space-x-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    <span className="text-sm text-gray-700">
                      {permissionLabels[action] || action}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {permissions.length === 0 && (
        <div className="rounded-lg border border-dashed p-8 text-center">
          <Shield className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-sm font-medium text-gray-900">
            No permissions assigned
          </h3>
          <p className="mt-2 text-sm text-gray-600">
            Contact your administrator to request access
          </p>
        </div>
      )}
    </div>
  );
}
