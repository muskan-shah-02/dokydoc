/**
 * User Management Page
 * Sprint 2 Extended - Multi-Tenancy & RBAC Support
 *
 * CXO-only page for managing users:
 * - View all users in the tenant
 * - Invite new users
 * - Edit user roles
 * - Activate/deactivate users
 * - Admin lockout prevention
 */

"use client";

import { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth, Permission } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import {
  Users as UsersIcon,
  UserPlus,
  Search,
  MoreVertical,
  Mail,
  Shield,
  Ban,
  CheckCircle2,
  X,
  Calendar,
  Crown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface User {
  id: number;
  email: string;
  roles: string[];
  is_active: boolean;
  created_at: string;
}

export default function UsersPage() {
  const router = useRouter();
  const { user: currentUser, hasPermission, isCXO } = useAuth();

  // Redirect if not CXO
  useEffect(() => {
    if (!isCXO()) {
      router.push("/dashboard");
    }
  }, [isCXO, router]);

  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [userMenuOpen, setUserMenuOpen] = useState<number | null>(null);

  // Invite form state
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRoles, setInviteRoles] = useState<string[]>(["Developer"]);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);

  // Load users
  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setIsLoading(true);
    try {
      const response = await api.get<User[]>("/users/");
      setUsers(response);
    } catch (error) {
      console.error("Failed to load users:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // Filter users based on search
  const filteredUsers = users.filter((user) =>
    user.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Invite user
  const handleInviteUser = async () => {
    if (!inviteEmail || inviteRoles.length === 0) {
      setInviteError("Email and at least one role are required");
      return;
    }

    setInviteLoading(true);
    setInviteError(null);

    try {
      await api.post("/users/invite", {
        email: inviteEmail,
        roles: inviteRoles,
      });

      // Close dialog and refresh
      setInviteDialogOpen(false);
      setInviteEmail("");
      setInviteRoles(["Developer"]);
      loadUsers();
    } catch (error: any) {
      setInviteError(error.detail || "Failed to invite user");
    } finally {
      setInviteLoading(false);
    }
  };

  // Toggle user active status
  const handleToggleUserStatus = async (userId: number, currentStatus: boolean) => {
    // Prevent deactivating yourself
    if (userId === currentUser?.id) {
      alert("You cannot deactivate your own account");
      return;
    }

    try {
      await api.put(`/users/${userId}`, {
        is_active: !currentStatus,
      });
      loadUsers();
    } catch (error) {
      console.error("Failed to update user status:", error);
    }
  };

  // Update user roles
  const handleUpdateRoles = async (userId: number, newRoles: string[]) => {
    // Prevent removing all roles from yourself
    if (userId === currentUser?.id && newRoles.length === 0) {
      alert("You cannot remove all roles from your own account");
      return;
    }

    try {
      await api.put(`/users/${userId}/`, {
        roles: newRoles,
      });
      loadUsers();
      setEditingUser(null);
    } catch (error) {
      console.error("Failed to update user roles:", error);
    }
  };

  if (!isCXO()) {
    return null;
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">User Management</h1>
            <p className="mt-2 text-gray-600">
              Manage your team members and their access levels
            </p>
          </div>

          <Button onClick={() => setInviteDialogOpen(true)}>
            <UserPlus className="mr-2 h-4 w-4" />
            Invite User
          </Button>
        </div>

        {/* Search and Filters */}
        <div className="flex items-center space-x-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
            <Input
              type="text"
              placeholder="Search users by email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-11 pl-10"
            />
          </div>
        </div>

        {/* Stats */}
        <div className="grid gap-6 sm:grid-cols-3">
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Users</p>
                <p className="mt-2 text-3xl font-bold text-gray-900">{users.length}</p>
              </div>
              <div className="rounded-lg bg-blue-100 p-3">
                <UsersIcon className="h-5 w-5 text-blue-600" />
              </div>
            </div>
          </div>

          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Active Users</p>
                <p className="mt-2 text-3xl font-bold text-gray-900">
                  {users.filter((u) => u.is_active).length}
                </p>
              </div>
              <div className="rounded-lg bg-green-100 p-3">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              </div>
            </div>
          </div>

          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Administrators</p>
                <p className="mt-2 text-3xl font-bold text-gray-900">
                  {users.filter((u) => u.roles.includes("CXO")).length}
                </p>
              </div>
              <div className="rounded-lg bg-purple-100 p-3">
                <Crown className="h-5 w-5 text-purple-600" />
              </div>
            </div>
          </div>
        </div>

        {/* Users List */}
        <div className="rounded-lg border bg-white shadow-sm">
          {isLoading ? (
            <div className="flex items-center justify-center p-12">
              <div className="text-center">
                <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
                <p className="text-gray-600">Loading users...</p>
              </div>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12">
              <UsersIcon className="h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-medium text-gray-900">
                {searchQuery ? "No users found" : "No users yet"}
              </h3>
              <p className="mt-2 text-sm text-gray-600">
                {searchQuery
                  ? "Try adjusting your search"
                  : "Invite users to get started"}
              </p>
              {!searchQuery && (
                <Button
                  onClick={() => setInviteDialogOpen(true)}
                  className="mt-4"
                >
                  <UserPlus className="mr-2 h-4 w-4" />
                  Invite User
                </Button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      User
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Roles
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Joined
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {filteredUsers.map((user) => (
                    <tr key={user.id} className="hover:bg-gray-50">
                      <td className="whitespace-nowrap px-6 py-4">
                        <div className="flex items-center">
                          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 text-sm font-semibold text-white">
                            {user.email.charAt(0).toUpperCase()}
                          </div>
                          <div className="ml-4">
                            <div className="flex items-center space-x-2">
                              <div className="font-medium text-gray-900">
                                {user.email}
                              </div>
                              {user.id === currentUser?.id && (
                                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                                  You
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4">
                        <div className="flex flex-wrap gap-1">
                          {user.roles.map((role) => (
                            <span
                              key={role}
                              className={`rounded px-2 py-1 text-xs font-medium ${
                                role === "CXO"
                                  ? "bg-purple-100 text-purple-700"
                                  : "bg-gray-100 text-gray-700"
                              }`}
                            >
                              {role}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4">
                        {user.is_active ? (
                          <span className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
                            <CheckCircle2 className="mr-1 h-3 w-3" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-800">
                            <Ban className="mr-1 h-3 w-3" />
                            Inactive
                          </span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                        {new Date(user.created_at).toLocaleDateString()}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-right">
                        <div className="relative inline-block">
                          <button
                            onClick={() =>
                              setUserMenuOpen(
                                userMenuOpen === user.id ? null : user.id
                              )
                            }
                            className="rounded-md p-1 hover:bg-gray-100"
                          >
                            <MoreVertical className="h-5 w-5 text-gray-500" />
                          </button>

                          {userMenuOpen === user.id && (
                            <>
                              <div
                                className="fixed inset-0 z-10"
                                onClick={() => setUserMenuOpen(null)}
                              />
                              <div className="absolute right-0 z-20 mt-2 w-48 rounded-lg border bg-white shadow-lg">
                                <button
                                  onClick={() => {
                                    setEditingUser(user);
                                    setUserMenuOpen(null);
                                  }}
                                  className="flex w-full items-center space-x-2 px-4 py-2 text-left text-sm hover:bg-gray-100"
                                >
                                  <Shield className="h-4 w-4" />
                                  <span>Edit Roles</span>
                                </button>

                                <button
                                  onClick={() => {
                                    handleToggleUserStatus(user.id, user.is_active);
                                    setUserMenuOpen(null);
                                  }}
                                  disabled={user.id === currentUser?.id}
                                  className="flex w-full items-center space-x-2 px-4 py-2 text-left text-sm hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  {user.is_active ? (
                                    <>
                                      <Ban className="h-4 w-4" />
                                      <span>Deactivate</span>
                                    </>
                                  ) : (
                                    <>
                                      <CheckCircle2 className="h-4 w-4" />
                                      <span>Activate</span>
                                    </>
                                  )}
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Invite User Dialog */}
      {inviteDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-900">Invite User</h2>
              <button
                onClick={() => {
                  setInviteDialogOpen(false);
                  setInviteError(null);
                }}
                className="rounded-md p-1 hover:bg-gray-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <Label htmlFor="inviteEmail">Email Address</Label>
                <div className="relative mt-2">
                  <Mail className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
                  <Input
                    id="inviteEmail"
                    type="email"
                    placeholder="user@example.com"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    className="h-11 pl-10"
                  />
                </div>
              </div>

              <div>
                <Label>Roles</Label>
                <div className="mt-2 space-y-2">
                  {["CXO", "BA", "Developer", "PM"].map((role) => (
                    <label key={role} className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={inviteRoles.includes(role)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setInviteRoles([...inviteRoles, role]);
                          } else {
                            setInviteRoles(inviteRoles.filter((r) => r !== role));
                          }
                        }}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600"
                      />
                      <span className="text-sm text-gray-700">{role}</span>
                    </label>
                  ))}
                </div>
              </div>

              {inviteError && (
                <div className="rounded-md bg-red-50 p-3">
                  <p className="text-sm text-red-800">{inviteError}</p>
                </div>
              )}

              <div className="flex space-x-3">
                <Button
                  onClick={() => {
                    setInviteDialogOpen(false);
                    setInviteError(null);
                  }}
                  variant="outline"
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleInviteUser}
                  disabled={inviteLoading}
                  className="flex-1"
                >
                  {inviteLoading ? "Inviting..." : "Send Invite"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Roles Dialog */}
      {editingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-900">Edit Roles</h2>
              <button
                onClick={() => setEditingUser(null)}
                className="rounded-md p-1 hover:bg-gray-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mb-4">
              <p className="text-sm text-gray-600">User: {editingUser.email}</p>
            </div>

            <div className="space-y-4">
              <div>
                <Label>Roles</Label>
                <div className="mt-2 space-y-2">
                  {["CXO", "BA", "Developer", "PM"].map((role) => (
                    <label key={role} className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={editingUser.roles.includes(role)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setEditingUser({
                              ...editingUser,
                              roles: [...editingUser.roles, role],
                            });
                          } else {
                            setEditingUser({
                              ...editingUser,
                              roles: editingUser.roles.filter((r) => r !== role),
                            });
                          }
                        }}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600"
                      />
                      <span className="text-sm text-gray-700">{role}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex space-x-3">
                <Button
                  onClick={() => setEditingUser(null)}
                  variant="outline"
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => handleUpdateRoles(editingUser.id, editingUser.roles)}
                  className="flex-1"
                >
                  Save Changes
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
