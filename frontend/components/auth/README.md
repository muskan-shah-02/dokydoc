# RBAC Guards - Permission & Role-Based Access Control

Comprehensive permission and role-based components and hooks for controlling access to UI elements and routes.

## Components

### RequirePermission

Conditionally renders content based on user permissions.

```tsx
import { RequirePermission } from "@/components/auth";
import { Permission } from "@/contexts/AuthContext";

// Single permission
<RequirePermission permission={Permission.DOCUMENT_WRITE}>
  <Button>Create Document</Button>
</RequirePermission>

// Multiple permissions (any)
<RequirePermission
  permissions={[Permission.DOCUMENT_WRITE, Permission.DOCUMENT_DELETE]}
  mode="any"
>
  <Button>Edit Document</Button>
</RequirePermission>

// Multiple permissions (all required)
<RequirePermission
  permissions={[Permission.BILLING_VIEW, Permission.BILLING_MANAGE]}
  mode="all"
>
  <BillingSettings />
</RequirePermission>

// With fallback content
<RequirePermission
  permission={Permission.BILLING_VIEW}
  fallback={<p>Contact admin for billing access</p>}
>
  <BillingDashboard />
</RequirePermission>
```

**Props:**
- `permission` - Single permission to check
- `permissions` - Array of permissions to check (used with `mode`)
- `mode` - "any" (default) or "all" - how to evaluate multiple permissions
- `children` - Content to show if permission granted
- `fallback` - Content to show if permission denied (optional)

### RequireRole

Conditionally renders content based on user roles.

```tsx
import { RequireRole } from "@/components/auth";

// Single role
<RequireRole role="CXO">
  <AdminPanel />
</RequireRole>

// Multiple roles (any)
<RequireRole roles={["CXO", "PM"]} mode="any">
  <TeamManagement />
</RequireRole>

// Multiple roles (all required)
<RequireRole roles={["CXO", "BA"]} mode="all">
  <AdvancedSettings />
</RequireRole>

// With fallback
<RequireRole
  role="CXO"
  fallback={<p>Admin access required</p>}
>
  <UserManagement />
</RequireRole>
```

**Props:**
- `role` - Single role to check
- `roles` - Array of roles to check (used with `mode`)
- `mode` - "any" (default) or "all" - how to evaluate multiple roles
- `children` - Content to show if role matches
- `fallback` - Content to show if role doesn't match (optional)

### ProtectedRoute

Protects entire routes or page sections with permission/role checks. Shows forbidden message or redirects if access denied.

```tsx
import { ProtectedRoute } from "@/components/auth";
import { Permission } from "@/contexts/AuthContext";

// Protect with permission
<ProtectedRoute permission={Permission.BILLING_MANAGE}>
  <BillingSettings />
</ProtectedRoute>

// Protect with role
<ProtectedRoute role="CXO" redirectTo="/dashboard">
  <AdminDashboard />
</ProtectedRoute>

// Protect with multiple permissions
<ProtectedRoute
  permissions={[Permission.USER_VIEW, Permission.USER_MANAGE]}
  mode="all"
>
  <UserManagement />
</ProtectedRoute>

// Custom redirect without forbidden message
<ProtectedRoute
  role="CXO"
  redirectTo="/login"
  showForbidden={false}
>
  <SuperAdminPanel />
</ProtectedRoute>
```

**Props:**
- `permission` - Single permission to check
- `permissions` - Array of permissions to check
- `role` - Single role to check
- `roles` - Array of roles to check
- `mode` - "any" (default) or "all" - evaluation mode
- `redirectTo` - Where to redirect if access denied (default: "/dashboard")
- `showForbidden` - Show forbidden message instead of redirect (default: true)
- `children` - Protected content

## Hooks

### usePermissionGuard

Programmatically check multiple permissions at once.

```tsx
import { usePermissionGuard } from "@/components/auth";
import { Permission } from "@/contexts/AuthContext";

function DocumentActions() {
  const { canCreate, canDelete, canAnalyze } = usePermissionGuard({
    canCreate: Permission.DOCUMENT_WRITE,
    canDelete: Permission.DOCUMENT_DELETE,
    canAnalyze: Permission.DOCUMENT_ANALYZE,
  });

  return (
    <div>
      {canCreate && <Button>Create</Button>}
      {canDelete && <Button>Delete</Button>}
      {canAnalyze && <Button>Analyze</Button>}
    </div>
  );
}
```

**Returns:**
- Object with boolean values for each permission check

### useRoleGuard

Programmatically check multiple roles at once.

```tsx
import { useRoleGuard } from "@/components/auth";

function DashboardContent() {
  const { isCXO, isPM, isDev } = useRoleGuard({
    isCXO: "CXO",
    isPM: "PM",
    isDev: "Developer",
  });

  if (isCXO) return <AdminDashboard />;
  if (isPM) return <PMDashboard />;
  if (isDev) return <DeveloperDashboard />;
  return <DefaultDashboard />;
}
```

**Returns:**
- Object with boolean values for each role check

## Common Patterns

### Button with Permission

```tsx
<RequirePermission permission={Permission.TASK_CREATE}>
  <Button onClick={handleCreateTask}>
    <Plus className="mr-2 h-4 w-4" />
    Create Task
  </Button>
</RequirePermission>
```

### Menu Item with Role

```tsx
<RequireRole role="CXO">
  <MenuItem href="/users">User Management</MenuItem>
</RequireRole>
```

### Protected Page Component

```tsx
export default function UsersPage() {
  return (
    <ProtectedRoute role="CXO">
      <AppLayout>
        <UserManagement />
      </AppLayout>
    </ProtectedRoute>
  );
}
```

### Conditional Actions with Hook

```tsx
function TaskCard({ task }) {
  const { canUpdate, canDelete, canComment } = usePermissionGuard({
    canUpdate: Permission.TASK_UPDATE,
    canDelete: Permission.TASK_DELETE,
    canComment: Permission.TASK_COMMENT,
  });

  return (
    <Card>
      <CardContent>{task.title}</CardContent>
      <CardActions>
        {canUpdate && <EditButton />}
        {canDelete && <DeleteButton />}
        {canComment && <CommentButton />}
      </CardActions>
    </Card>
  );
}
```

### Complex Permission Logic

```tsx
// Require EITHER document write OR document delete
<RequirePermission
  permissions={[Permission.DOCUMENT_WRITE, Permission.DOCUMENT_DELETE]}
  mode="any"
>
  <DocumentActions />
</RequirePermission>

// Require BOTH billing view AND billing manage
<RequirePermission
  permissions={[Permission.BILLING_VIEW, Permission.BILLING_MANAGE]}
  mode="all"
>
  <BillingSettings />
</RequirePermission>
```

### Nested Guards

```tsx
<RequireRole role="CXO">
  <AdminLayout>
    <RequirePermission permission={Permission.BILLING_MANAGE}>
      <BillingSection />
    </RequirePermission>

    <RequirePermission permission={Permission.USER_MANAGE}>
      <UserSection />
    </RequirePermission>
  </AdminLayout>
</RequireRole>
```

## Available Permissions

```typescript
enum Permission {
  // Documents
  DOCUMENT_READ = "document:read",
  DOCUMENT_WRITE = "document:write",
  DOCUMENT_DELETE = "document:delete",
  DOCUMENT_ANALYZE = "document:analyze",

  // Code
  CODE_READ = "code:read",
  CODE_WRITE = "code:write",
  CODE_DELETE = "code:delete",

  // Analysis
  ANALYSIS_VIEW = "analysis:view",
  ANALYSIS_RUN = "analysis:run",

  // Validation
  VALIDATION_VIEW = "validation:view",
  VALIDATION_RUN = "validation:run",

  // Tasks
  TASK_READ = "task:read",
  TASK_CREATE = "task:create",
  TASK_UPDATE = "task:update",
  TASK_DELETE = "task:delete",
  TASK_ASSIGN = "task:assign",
  TASK_COMMENT = "task:comment",

  // Billing
  BILLING_VIEW = "billing:view",
  BILLING_MANAGE = "billing:manage",

  // Users
  USER_VIEW = "user:view",
  USER_INVITE = "user:invite",
  USER_MANAGE = "user:manage",
  USER_DELETE = "user:delete",

  // Tenant
  TENANT_VIEW = "tenant:view",
  TENANT_MANAGE = "tenant:manage",
}
```

## Available Roles

- **CXO** - Organization administrator with full access
- **BA** - Business Analyst with document and validation access
- **Developer** - Developer with code component access
- **PM** - Project Manager with task and team management access

## Best Practices

1. **Use Permission Guards for Actions**: Protect buttons, menu items, and actions with `RequirePermission`
2. **Use Role Guards for Sections**: Protect entire sections or dashboards with `RequireRole`
3. **Use ProtectedRoute for Pages**: Protect entire pages with `ProtectedRoute`
4. **Combine Guards**: Nest guards for complex permission logic
5. **Provide Fallbacks**: Always provide meaningful fallback content when denying access
6. **Use Hooks for Logic**: Use `usePermissionGuard` when you need permission checks in component logic
7. **Keep It Simple**: Don't over-complicate - most cases need single permission/role checks

## Performance Notes

- All permission checks are O(1) lookups from the permissions array in context
- Guards do not cause re-renders unless user permissions change
- Use hooks sparingly in hot paths - prefer component guards when possible
