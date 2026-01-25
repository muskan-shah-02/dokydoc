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
    DASHBOARD_PM = "dashboard:pm"


# Role-to-Permissions Mapping
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.CXO: {
        # CXO has ALL permissions (tenant admin)
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
        Permission.BILLING_VIEW,
        Permission.BILLING_MANAGE,
        Permission.USER_VIEW,
        Permission.USER_INVITE,
        Permission.USER_MANAGE,
        Permission.USER_DELETE,
        Permission.TENANT_VIEW,
        Permission.TENANT_MANAGE,
        Permission.DASHBOARD_CXO,
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
        Permission.BILLING_VIEW,  # Can view billing but not manage
        Permission.USER_VIEW,  # Can see other users
        Permission.TENANT_VIEW,  # Can view tenant info
        Permission.DASHBOARD_BA,
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
        Permission.BILLING_VIEW,
        Permission.USER_VIEW,
        Permission.TENANT_VIEW,
        Permission.DASHBOARD_DEVELOPER,
    },

    Role.PRODUCT_MANAGER: {
        # Product Manager - Read access, limited write
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_WRITE,  # Can upload PRDs
        Permission.CODE_READ,  # Can view code
        Permission.ANALYSIS_VIEW,
        Permission.ANALYSIS_RUN,
        Permission.VALIDATION_VIEW,
        Permission.BILLING_VIEW,
        Permission.USER_VIEW,
        Permission.TENANT_VIEW,
        Permission.DASHBOARD_PM,
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
