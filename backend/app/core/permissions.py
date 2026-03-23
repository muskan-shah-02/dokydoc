"""
RBAC Permission System
Sprint 2 Phase 5: Enhanced RBAC with Permission Decorators

Defines all permissions and role-to-permission mappings for fine-grained access control.
"""
from enum import Enum
from typing import Set, List
from app.schemas.user import Role


class Permission(str, Enum):
    """
    All available permissions in the system.

    Naming convention: RESOURCE_ACTION
    - RESOURCE: What is being accessed (USER, DOCUMENT, BILLING, etc.)
    - ACTION: What operation (READ, WRITE, DELETE, MANAGE, etc.)
    """
    # Document Permissions
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_ANALYZE = "document:analyze"

    # Code Component Permissions
    CODE_READ = "code:read"
    CODE_WRITE = "code:write"
    CODE_DELETE = "code:delete"

    # Analysis Permissions
    ANALYSIS_VIEW = "analysis:view"
    ANALYSIS_RUN = "analysis:run"

    # Validation Permissions
    VALIDATION_VIEW = "validation:view"
    VALIDATION_RUN = "validation:run"

    # Task Permissions (Sprint 2 Extended - Phase 10)
    TASK_READ = "task:read"
    TASK_CREATE = "task:create"
    TASK_UPDATE = "task:update"
    TASK_DELETE = "task:delete"
    TASK_ASSIGN = "task:assign"
    TASK_COMMENT = "task:comment"

    # Billing Permissions
    BILLING_VIEW = "billing:view"
    BILLING_MANAGE = "billing:manage"  # Update settings, add balance

    # User Management Permissions (Tenant-scoped)
    USER_VIEW = "user:view"  # View users in tenant
    USER_INVITE = "user:invite"  # Invite new users to tenant
    USER_MANAGE = "user:manage"  # Edit user roles, deactivate users
    USER_DELETE = "user:delete"  # Delete users from tenant

    # Tenant Management Permissions
    TENANT_VIEW = "tenant:view"  # View tenant info
    TENANT_MANAGE = "tenant:manage"  # Update tenant settings

    # Dashboard Permissions
    DASHBOARD_DEVELOPER = "dashboard:developer"
    DASHBOARD_BA = "dashboard:ba"
    DASHBOARD_CXO = "dashboard:cxo"
    DASHBOARD_ADMIN = "dashboard:admin"
    DASHBOARD_PM = "dashboard:pm"
    DASHBOARD_AUDITOR = "dashboard:auditor"

    # Audit & Compliance Permissions
    AUDIT_VIEW = "audit:view"  # View audit trails
    AUDIT_EXPORT = "audit:export"  # Export audit reports
    COMPLIANCE_VIEW = "compliance:view"  # View compliance status
    COMPLIANCE_REPORT = "compliance:report"  # Generate compliance reports

    # Chat/AskyDoc Permissions (Sprint 7)
    CHAT_USE = "chat:use"  # Use the AI chat assistant

    # Approval Permissions (Sprint 6)
    APPROVAL_REQUEST = "approval:request"  # Request approvals
    APPROVAL_VIEW = "approval:view"  # View approvals
    APPROVAL_RESOLVE = "approval:resolve"  # Approve/reject/request revision

    # API Key Permissions (Sprint 8)
    API_KEY_MANAGE = "api_key:manage"  # Create / revoke own API keys


# Role-to-Permissions Mapping
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.CXO: {
        # CXO has ALL permissions (tenant owner - "God Mode")
        # Work Permissions - Full access to all work modules
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_WRITE,
        Permission.DOCUMENT_DELETE,
        Permission.DOCUMENT_ANALYZE,
        Permission.CODE_READ,
        Permission.CODE_WRITE,
        Permission.CODE_DELETE,
        Permission.ANALYSIS_VIEW,
        Permission.ANALYSIS_RUN,
        Permission.VALIDATION_VIEW,
        Permission.VALIDATION_RUN,
        Permission.TASK_READ,
        Permission.TASK_CREATE,
        Permission.TASK_UPDATE,
        Permission.TASK_DELETE,
        Permission.TASK_ASSIGN,
        Permission.TASK_COMMENT,
        # Management Permissions - Full admin access
        Permission.BILLING_VIEW,
        Permission.BILLING_MANAGE,
        Permission.USER_VIEW,
        Permission.USER_INVITE,
        Permission.USER_MANAGE,
        Permission.USER_DELETE,
        Permission.TENANT_VIEW,
        Permission.TENANT_MANAGE,
        # Dashboard Permissions - ALL dashboards (God Mode)
        Permission.DASHBOARD_CXO,
        Permission.DASHBOARD_ADMIN,
        Permission.DASHBOARD_DEVELOPER,
        Permission.DASHBOARD_BA,
        Permission.DASHBOARD_PM,
        Permission.DASHBOARD_AUDITOR,
        # Audit & Compliance - Full access
        Permission.AUDIT_VIEW,
        Permission.AUDIT_EXPORT,
        Permission.COMPLIANCE_VIEW,
        Permission.COMPLIANCE_REPORT,
        # Chat/AskyDoc (Sprint 7)
        Permission.CHAT_USE,
        # Approval Permissions - Full access (Sprint 6)
        Permission.APPROVAL_REQUEST,
        Permission.APPROVAL_VIEW,
        Permission.APPROVAL_RESOLVE,
        # API Key Management (Sprint 8)
        Permission.API_KEY_MANAGE,
    },

    Role.ADMIN: {
        # ADMIN - Operations manager (Users, Billing, Org settings only)
        # NO access to Work modules (Documents, Code, Tasks, Validation)
        Permission.BILLING_VIEW,
        Permission.BILLING_MANAGE,
        Permission.USER_VIEW,
        Permission.USER_INVITE,
        Permission.USER_MANAGE,
        Permission.USER_DELETE,
        Permission.TENANT_VIEW,
        Permission.TENANT_MANAGE,
        Permission.DASHBOARD_ADMIN,
        # Approval - can view and resolve level 1-2 (Sprint 6)
        Permission.APPROVAL_VIEW,
        Permission.APPROVAL_RESOLVE,
        # API Key Management (Sprint 8)
        Permission.API_KEY_MANAGE,
    },

    Role.BA: {
        # Business Analyst - Read/Write documents, run analysis
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_WRITE,
        Permission.DOCUMENT_DELETE,
        Permission.DOCUMENT_ANALYZE,
        Permission.CODE_READ,
        Permission.ANALYSIS_VIEW,
        Permission.ANALYSIS_RUN,
        Permission.VALIDATION_VIEW,
        Permission.VALIDATION_RUN,
        Permission.TASK_READ,
        Permission.TASK_CREATE,
        Permission.TASK_UPDATE,
        Permission.TASK_ASSIGN,  # BA can assign tasks
        Permission.TASK_COMMENT,
        Permission.BILLING_VIEW,  # Can view billing but not manage
        Permission.USER_VIEW,  # Can see other users
        Permission.TENANT_VIEW,  # Can view tenant info
        Permission.DASHBOARD_BA,
        # Chat/AskyDoc (Sprint 7)
        Permission.CHAT_USE,
        # Approval - can request and view (Sprint 6)
        Permission.APPROVAL_REQUEST,
        Permission.APPROVAL_VIEW,
        Permission.APPROVAL_RESOLVE,
    },

    Role.DEVELOPER: {
        # Developer - Full access to code, documents, and analysis
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_WRITE,
        Permission.DOCUMENT_DELETE,
        Permission.DOCUMENT_ANALYZE,
        Permission.CODE_READ,
        Permission.CODE_WRITE,
        Permission.CODE_DELETE,
        Permission.ANALYSIS_VIEW,
        Permission.ANALYSIS_RUN,
        Permission.VALIDATION_VIEW,
        Permission.VALIDATION_RUN,
        Permission.TASK_READ,
        Permission.TASK_CREATE,
        Permission.TASK_UPDATE,
        Permission.TASK_COMMENT,
        Permission.BILLING_VIEW,
        Permission.USER_VIEW,
        Permission.TENANT_VIEW,
        Permission.DASHBOARD_DEVELOPER,
        # Chat/AskyDoc (Sprint 7)
        Permission.CHAT_USE,
        # Approval - can request, view, and resolve level 1 (Sprint 6)
        Permission.APPROVAL_REQUEST,
        Permission.APPROVAL_VIEW,
        Permission.APPROVAL_RESOLVE,
        # API Key Management (Sprint 8)
        Permission.API_KEY_MANAGE,
    },

    Role.PRODUCT_MANAGER: {
        # Product Manager - Read access, limited write
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_WRITE,  # Can upload PRDs
        Permission.CODE_READ,  # Can view code
        Permission.ANALYSIS_VIEW,
        Permission.ANALYSIS_RUN,
        Permission.VALIDATION_VIEW,
        Permission.TASK_READ,
        Permission.TASK_CREATE,
        Permission.TASK_UPDATE,
        Permission.TASK_COMMENT,
        Permission.BILLING_VIEW,
        Permission.USER_VIEW,
        Permission.TENANT_VIEW,
        Permission.DASHBOARD_PM,
        # Chat/AskyDoc (Sprint 7)
        Permission.CHAT_USE,
        # Approval - can request and view (Sprint 6)
        Permission.APPROVAL_REQUEST,
        Permission.APPROVAL_VIEW,
    },

    Role.AUDITOR: {
        # Auditor - Read-only access focused on compliance and audit trails
        # Document access - READ ONLY for audit purposes
        Permission.DOCUMENT_READ,
        Permission.ANALYSIS_VIEW,
        Permission.VALIDATION_VIEW,
        # Code access - READ ONLY
        Permission.CODE_READ,
        # Task access - READ ONLY
        Permission.TASK_READ,
        # Billing view (for cost audits)
        Permission.BILLING_VIEW,
        # User/Tenant view (for access audits)
        Permission.USER_VIEW,
        Permission.TENANT_VIEW,
        # Full Audit & Compliance permissions
        Permission.AUDIT_VIEW,
        Permission.AUDIT_EXPORT,
        Permission.COMPLIANCE_VIEW,
        Permission.COMPLIANCE_REPORT,
        # Auditor dashboard
        Permission.DASHBOARD_AUDITOR,
        # Approval - view only for audit purposes (Sprint 6)
        Permission.APPROVAL_VIEW,
    },
}


class PermissionChecker:
    """
    Utility class for checking permissions.
    """

    @staticmethod
    def user_has_permission(user_roles: List[str], required_permission: Permission) -> bool:
        """
        Check if user has a specific permission based on their roles.

        Args:
            user_roles: List of role names (e.g., ["CXO", "Developer"])
            required_permission: The permission to check

        Returns:
            True if user has the permission, False otherwise
        """
        if not user_roles:
            return False

        # Convert string roles to Role enum
        try:
            roles = [Role(role) for role in user_roles]
        except ValueError:
            # Invalid role
            return False

        # Check if any of the user's roles has the required permission
        for role in roles:
            if role in ROLE_PERMISSIONS:
                if required_permission in ROLE_PERMISSIONS[role]:
                    return True

        return False

    @staticmethod
    def user_has_any_permission(user_roles: List[str], required_permissions: List[Permission]) -> bool:
        """
        Check if user has ANY of the specified permissions.

        Args:
            user_roles: List of role names
            required_permissions: List of permissions to check

        Returns:
            True if user has at least one permission, False otherwise
        """
        for permission in required_permissions:
            if PermissionChecker.user_has_permission(user_roles, permission):
                return True
        return False

    @staticmethod
    def user_has_all_permissions(user_roles: List[str], required_permissions: List[Permission]) -> bool:
        """
        Check if user has ALL of the specified permissions.

        Args:
            user_roles: List of role names
            required_permissions: List of permissions to check

        Returns:
            True if user has all permissions, False otherwise
        """
        for permission in required_permissions:
            if not PermissionChecker.user_has_permission(user_roles, permission):
                return False
        return True

    @staticmethod
    def get_user_permissions(user_roles: List[str]) -> Set[Permission]:
        """
        Get all permissions for a user based on their roles.

        Args:
            user_roles: List of role names

        Returns:
            Set of all permissions the user has
        """
        all_permissions: Set[Permission] = set()

        try:
            roles = [Role(role) for role in user_roles]
        except ValueError:
            return all_permissions

        for role in roles:
            if role in ROLE_PERMISSIONS:
                all_permissions.update(ROLE_PERMISSIONS[role])

        return all_permissions

    @staticmethod
    def is_tenant_admin(user_roles: List[str]) -> bool:
        """
        Check if user is a tenant admin (has CXO role).

        Args:
            user_roles: List of role names

        Returns:
            True if user has CXO role, False otherwise
        """
        return Role.CXO.value in user_roles


# Singleton instance
permission_checker = PermissionChecker()
