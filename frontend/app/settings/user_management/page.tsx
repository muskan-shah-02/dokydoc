/**
 * User Management Settings Page
 * Sprint 2 Refinement - FR-05
 *
 * Location: /settings/user_management
 * Access: CXO and Admin only
 *
 * Features:
 * - List all users in the tenant
 * - Search users by email
 * - "Invite User" modal (Email + Role selection)
 * - Edit Roles / Deactivate User
 * - Constraint: Users cannot delete themselves or modify their own role
 */

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth, Permission, Role } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  Users,
  Search,
  UserPlus,
  MoreVertical,
  Check,
  X,
  Shield,
  Edit,
  Trash2,
  ChevronLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Link from "next/link";

interface User {
  id: number;
  email: string;
  roles: string[];
  is_active: boolean;
  tenant_id: number;
  created_at: string;
}

export default function UserManagementPage() {
  const router = useRouter();
  const { user: currentUser, hasPermission, isCXO, isAdmin, isLoading: authLoading } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [filteredUsers, setFilteredUsers] = useState<User[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [actionMenuOpen, setActionMenuOpen] = useState<number | null>(null);

  // Check access
  const canAccess = isCXO() || isAdmin() || hasPermission(Permission.USER_MANAGE);

  // Redirect if no access
  useEffect(() => {
    if (!authLoading && currentUser && !canAccess) {
      router.push("/settings");
    }
  }, [authLoading, currentUser, canAccess, router]);

  // Load users
  useEffect(() => {
    if (canAccess) {
      loadUsers();
    }
  }, [canAccess]);

  // Filter users on search
  useEffect(() => {
    if (searchQuery) {
      setFilteredUsers(
        users.filter((u) =>
          u.email.toLowerCase().includes(searchQuery.toLowerCase())
        )
      );
    } else {
      setFilteredUsers(users);
    }
  }, [searchQuery, users]);

  const loadUsers = async () => {
    setIsLoading(true);
    try {
      const data = await api.get<User[]>("/users/");
      setUsers(data);
      setFilteredUsers(data);
    } catch (error) {
      console.error("Failed to load users:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleInviteUser = async (email: string, password: string, roles: string[]) => {
    try {
      await api.post("/users/invite/", { email, password, roles });
      setShowInviteModal(false);
      loadUsers();
    } catch (error: any) {
      alert(error.detail || "Failed to invite user");
    }
  };

  const handleUpdateRoles = async (userId: number, roles: string[]) => {
    try {
      await api.put(`/users/${userId}/roles/`, { roles });
      setEditingUser(null);
      loadUsers();
    } catch (error: any) {
      alert(error.detail || "Failed to update roles");
    }
  };

  const handleToggleActive = async (userId: number, isActive: boolean) => {
    try {
      await api.put(`/users/${userId}/`, { is_active: isActive });
      loadUsers();
    } catch (error: any) {
      alert(error.detail || "Failed to update user status");
    }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!confirm("Are you sure you want to delete this user? This action cannot be undone.")) {
      return;
    }
    try {
      await api.delete(`/users/${userId}/`);
      loadUsers();
    } catch (error: any) {
      alert(error.detail || "Failed to delete user");
    }
  };

  if (authLoading || !canAccess) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
            <p className="text-gray-600">Loading...</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Back link */}
        <Link href="/settings" className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900">
          <ChevronLeft className="mr-1 h-4 w-4" />
          Back to Settings
        </Link>

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">User Management</h1>
            <p className="mt-2 text-gray-600">
              Manage users in your organization
            </p>
          </div>
          <Button onClick={() => setShowInviteModal(true)}>
            <UserPlus className="mr-2 h-4 w-4" />
            Invite User
          </Button>
        </div>

        {/* Search */}
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <Input
            type="text"
            placeholder="Search users by email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Users Table */}
        <div className="rounded-lg border bg-white shadow-sm overflow-visible">
          {isLoading ? (
            <div className="p-8 text-center">
              <div className="mb-4 h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
              <p className="text-gray-600">Loading users...</p>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="p-8 text-center">
              <Users className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-sm font-medium text-gray-900">No users found</h3>
              <p className="mt-2 text-sm text-gray-600">
                {searchQuery ? "Try a different search term" : "Invite users to get started"}
              </p>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    User
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Roles
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Joined
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filteredUsers.map((user) => {
                  const isSelf = user.id === currentUser?.id;

                  return (
                    <tr key={user.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="h-10 w-10 flex-shrink-0 rounded-full bg-blue-600 flex items-center justify-center text-white font-semibold">
                            {user.email.charAt(0).toUpperCase()}
                          </div>
                          <div className="ml-4">
                            <div className="text-sm font-medium text-gray-900">
                              {user.email}
                              {isSelf && (
                                <span className="ml-2 text-xs text-blue-600">(you)</span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex flex-wrap gap-1">
                          {user.roles.map((role) => (
                            <span
                              key={role}
                              className={`rounded px-2 py-0.5 text-xs font-medium ${
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
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`rounded-full px-2 py-1 text-xs font-medium ${
                            user.is_active
                              ? "bg-green-100 text-green-700"
                              : "bg-red-100 text-red-700"
                          }`}
                        >
                          {user.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(user.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                        {!isSelf && (
                          <div className="relative">
                            <button
                              onClick={() => setActionMenuOpen(actionMenuOpen === user.id ? null : user.id)}
                              className="rounded p-1 hover:bg-gray-100"
                            >
                              <MoreVertical className="h-5 w-5 text-gray-500" />
                            </button>

                            {actionMenuOpen === user.id && (
                              <>
                                <div
                                  className="fixed inset-0 z-10"
                                  onClick={() => setActionMenuOpen(null)}
                                />
                                <div className="absolute right-0 z-20 mt-1 w-48 rounded-md border bg-white shadow-lg">
                                  <button
                                    onClick={() => {
                                      setEditingUser(user);
                                      setActionMenuOpen(null);
                                    }}
                                    className="flex w-full items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                  >
                                    <Edit className="mr-2 h-4 w-4" />
                                    Edit Roles
                                  </button>
                                  <button
                                    onClick={() => {
                                      handleToggleActive(user.id, !user.is_active);
                                      setActionMenuOpen(null);
                                    }}
                                    className="flex w-full items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                  >
                                    {user.is_active ? (
                                      <>
                                        <X className="mr-2 h-4 w-4" />
                                        Deactivate
                                      </>
                                    ) : (
                                      <>
                                        <Check className="mr-2 h-4 w-4" />
                                        Activate
                                      </>
                                    )}
                                  </button>
                                  <button
                                    onClick={() => {
                                      handleDeleteUser(user.id);
                                      setActionMenuOpen(null);
                                    }}
                                    className="flex w-full items-center px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                                  >
                                    <Trash2 className="mr-2 h-4 w-4" />
                                    Delete
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Invite User Modal */}
        {showInviteModal && (
          <InviteUserModal
            onClose={() => setShowInviteModal(false)}
            onInvite={handleInviteUser}
          />
        )}

        {/* Edit Roles Modal */}
        {editingUser && (
          <EditRolesModal
            user={editingUser}
            onClose={() => setEditingUser(null)}
            onSave={handleUpdateRoles}
          />
        )}
      </div>
    </AppLayout>
  );
}

// Invite User Modal
function InviteUserModal({
  onClose,
  onInvite,
}: {
  onClose: () => void;
  onInvite: (email: string, password: string, roles: string[]) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [selectedRoles, setSelectedRoles] = useState<string[]>(["Developer"]);
  const [isLoading, setIsLoading] = useState(false);

  const availableRoles = [Role.CXO, Role.ADMIN, Role.DEVELOPER, Role.BA, Role.PRODUCT_MANAGER];

  const handleSubmit = async () => {
    if (!email || !password || selectedRoles.length === 0) {
      alert("Please fill in all fields and select at least one role");
      return;
    }
    setIsLoading(true);
    await onInvite(email, password, selectedRoles);
    setIsLoading(false);
  };

  const toggleRole = (role: string) => {
    setSelectedRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">Invite User</h2>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="email">Email Address</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              className="mt-2"
            />
          </div>

          <div>
            <Label htmlFor="password">Initial Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Set a password"
              className="mt-2"
            />
            <p className="mt-1 text-xs text-gray-500">
              User can change this after logging in
            </p>
          </div>

          <div>
            <Label>Roles</Label>
            <div className="mt-2 space-y-2">
              {availableRoles.map((role) => (
                <button
                  key={role}
                  onClick={() => toggleRole(role)}
                  className={`flex w-full items-center justify-between rounded-lg border p-3 text-left ${
                    selectedRoles.includes(role)
                      ? "border-blue-600 bg-blue-50"
                      : "border-gray-200 hover:border-blue-300"
                  }`}
                >
                  <span className="text-sm font-medium">{role}</span>
                  {selectedRoles.includes(role) && (
                    <Check className="h-4 w-4 text-blue-600" />
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="flex space-x-3 pt-4">
            <Button onClick={onClose} variant="outline" className="flex-1">
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isLoading} className="flex-1">
              {isLoading ? "Inviting..." : "Invite User"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Edit Roles Modal
function EditRolesModal({
  user,
  onClose,
  onSave,
}: {
  user: User;
  onClose: () => void;
  onSave: (userId: number, roles: string[]) => void;
}) {
  const [selectedRoles, setSelectedRoles] = useState<string[]>(user.roles);
  const [isLoading, setIsLoading] = useState(false);

  const availableRoles = [Role.CXO, Role.ADMIN, Role.DEVELOPER, Role.BA, Role.PRODUCT_MANAGER];

  const handleSubmit = async () => {
    if (selectedRoles.length === 0) {
      alert("User must have at least one role");
      return;
    }
    setIsLoading(true);
    await onSave(user.id, selectedRoles);
    setIsLoading(false);
  };

  const toggleRole = (role: string) => {
    setSelectedRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">Edit Roles</h2>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mb-4 rounded-lg bg-gray-50 p-3">
          <p className="text-sm text-gray-600">User</p>
          <p className="font-medium text-gray-900">{user.email}</p>
        </div>

        <div className="space-y-4">
          <div>
            <Label>Roles</Label>
            <div className="mt-2 space-y-2">
              {availableRoles.map((role) => (
                <button
                  key={role}
                  onClick={() => toggleRole(role)}
                  className={`flex w-full items-center justify-between rounded-lg border p-3 text-left ${
                    selectedRoles.includes(role)
                      ? "border-blue-600 bg-blue-50"
                      : "border-gray-200 hover:border-blue-300"
                  }`}
                >
                  <span className="text-sm font-medium">{role}</span>
                  {selectedRoles.includes(role) && (
                    <Check className="h-4 w-4 text-blue-600" />
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="flex space-x-3 pt-4">
            <Button onClick={onClose} variant="outline" className="flex-1">
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isLoading} className="flex-1">
              {isLoading ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
