"use client";

import { useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth, Permission, Role } from "@/contexts/AuthContext";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Shield,
  CheckCircle,
  XCircle,
  User,
  Users,
  Settings,
  FileText,
  Code,
  BarChart3,
  CreditCard,
  Building2,
} from "lucide-react";

// Define permission groups for display
const permissionGroups = [
  {
    name: "Dashboards",
    icon: BarChart3,
    permissions: [
      { id: Permission.DASHBOARD_CXO, name: "CXO Dashboard", description: "Access executive dashboard with cost and health metrics" },
      { id: Permission.DASHBOARD_ADMIN, name: "Admin Dashboard", description: "Access admin dashboard with user management" },
      { id: Permission.DASHBOARD_DEVELOPER, name: "Developer Dashboard", description: "Access developer-focused dashboard" },
      { id: Permission.DASHBOARD_BA, name: "BA Dashboard", description: "Access business analyst dashboard" },
    ],
  },
  {
    name: "Documents",
    icon: FileText,
    permissions: [
      { id: Permission.DOCUMENT_WRITE, name: "Create Documents", description: "Upload new documents" },
      { id: Permission.DOCUMENT_READ, name: "View Documents", description: "View document details and analysis" },
      { id: Permission.DOCUMENT_ANALYZE, name: "Analyze Documents", description: "Run AI analysis on documents" },
      { id: Permission.DOCUMENT_DELETE, name: "Delete Documents", description: "Remove documents from the system" },
    ],
  },
  {
    name: "Code Components",
    icon: Code,
    permissions: [
      { id: Permission.CODE_WRITE, name: "Register Code", description: "Add new code components" },
      { id: Permission.CODE_READ, name: "View Code", description: "View code component details" },
      { id: Permission.CODE_DELETE, name: "Delete Code", description: "Remove code components" },
    ],
  },
  {
    name: "User Management",
    icon: Users,
    permissions: [
      { id: Permission.USER_VIEW, name: "View Users", description: "View user list and details" },
      { id: Permission.USER_MANAGE, name: "Manage Users", description: "Create, edit, and delete users" },
      { id: Permission.USER_INVITE, name: "Invite Users", description: "Send invitations to new users" },
    ],
  },
  {
    name: "Organization",
    icon: Building2,
    permissions: [
      { id: Permission.TENANT_MANAGE, name: "Organization Settings", description: "Modify organization configuration" },
      { id: Permission.BILLING_VIEW, name: "View Billing", description: "Access billing information" },
      { id: Permission.BILLING_MANAGE, name: "Manage Billing", description: "Modify billing and subscription" },
    ],
  },
];

// Role definitions with their permissions
const roleDefinitions: Record<string, { description: string; color: string }> = {
  CXO: { description: "Full access to all features (God Mode)", color: "purple" },
  Admin: { description: "Organization administration and user management", color: "blue" },
  Developer: { description: "Code-focused workflow with technical features", color: "green" },
  BA: { description: "Document and analysis focused workflow", color: "orange" },
  "Product Manager": { description: "Product planning and validation features", color: "pink" },
};

export default function PermissionsPage() {
  const { user, hasPermission } = useAuth();
  const [selectedRole, setSelectedRole] = useState<string | null>(null);

  const userRoles = user?.roles || [];

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Permissions</h1>
          <p className="mt-2 text-gray-600">
            View your current permissions based on your assigned roles
          </p>
        </div>

        {/* Your Roles */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" />
              Your Roles
            </CardTitle>
            <CardDescription>
              Roles assigned to your account determine your permissions
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              {userRoles.length > 0 ? (
                userRoles.map((role) => {
                  const roleInfo = roleDefinitions[role];
                  return (
                    <div
                      key={role}
                      className={`flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-colors ${
                        selectedRole === role
                          ? "border-blue-500 bg-blue-50"
                          : "hover:bg-gray-50"
                      }`}
                      onClick={() => setSelectedRole(selectedRole === role ? null : role)}
                    >
                      <Shield className={`h-4 w-4 text-${roleInfo?.color || "gray"}-600`} />
                      <div>
                        <p className="font-medium">{role}</p>
                        <p className="text-xs text-muted-foreground">
                          {roleInfo?.description || "Custom role"}
                        </p>
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="text-muted-foreground">No roles assigned</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Permission Matrix */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Permission Matrix
            </CardTitle>
            <CardDescription>
              Permissions you have access to based on your roles
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {permissionGroups.map((group) => {
                const GroupIcon = group.icon;
                return (
                  <div key={group.name}>
                    <h3 className="flex items-center gap-2 font-semibold mb-3">
                      <GroupIcon className="h-4 w-4 text-muted-foreground" />
                      {group.name}
                    </h3>
                    <div className="border rounded-lg overflow-hidden">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Permission</TableHead>
                            <TableHead>Description</TableHead>
                            <TableHead className="text-center">Status</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {group.permissions.map((perm) => {
                            const hasAccess = hasPermission(perm.id);
                            return (
                              <TableRow key={perm.id}>
                                <TableCell className="font-medium">
                                  {perm.name}
                                </TableCell>
                                <TableCell className="text-muted-foreground">
                                  {perm.description}
                                </TableCell>
                                <TableCell className="text-center">
                                  {hasAccess ? (
                                    <Badge className="bg-green-100 text-green-700">
                                      <CheckCircle className="h-3 w-3 mr-1" />
                                      Granted
                                    </Badge>
                                  ) : (
                                    <Badge variant="secondary" className="text-gray-500">
                                      <XCircle className="h-3 w-3 mr-1" />
                                      No Access
                                    </Badge>
                                  )}
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Role Comparison */}
        <Card>
          <CardHeader>
            <CardTitle>Role Comparison</CardTitle>
            <CardDescription>
              See how different roles compare in terms of permissions
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Role</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-center">Dashboards</TableHead>
                    <TableHead className="text-center">Documents</TableHead>
                    <TableHead className="text-center">Code</TableHead>
                    <TableHead className="text-center">User Mgmt</TableHead>
                    <TableHead className="text-center">Billing</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(roleDefinitions).map(([role, info]) => (
                    <TableRow key={role}>
                      <TableCell>
                        <Badge
                          className={`bg-${info.color}-100 text-${info.color}-700`}
                        >
                          {role}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {info.description}
                      </TableCell>
                      <TableCell className="text-center">
                        <CheckCircle className="h-4 w-4 text-green-600 mx-auto" />
                      </TableCell>
                      <TableCell className="text-center">
                        <CheckCircle className="h-4 w-4 text-green-600 mx-auto" />
                      </TableCell>
                      <TableCell className="text-center">
                        {role === "BA" ? (
                          <XCircle className="h-4 w-4 text-gray-400 mx-auto" />
                        ) : (
                          <CheckCircle className="h-4 w-4 text-green-600 mx-auto" />
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        {role === "CXO" || role === "Admin" ? (
                          <CheckCircle className="h-4 w-4 text-green-600 mx-auto" />
                        ) : (
                          <XCircle className="h-4 w-4 text-gray-400 mx-auto" />
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        {role === "CXO" || role === "Admin" ? (
                          <CheckCircle className="h-4 w-4 text-green-600 mx-auto" />
                        ) : (
                          <XCircle className="h-4 w-4 text-gray-400 mx-auto" />
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
