"""
Tenant User Management Endpoints
Sprint 2 Phase 5: RBAC with Permission Decorators

Allows tenant admins (CXO) to manage users within their tenant.
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas, models
from app.api import deps
from app.core.logging import LoggerMixin, get_logger
from app.core.permissions import Permission

logger = get_logger("api.users")


class UserManagementEndpoints(LoggerMixin):
    """User management endpoints with enhanced logging."""

    def __init__(self):
        super().__init__()


# Create instance
user_management_endpoints = UserManagementEndpoints()

router = APIRouter()


@router.get("/", response_model=List[schemas.user.UserResponse])
def list_tenant_users(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.USER_VIEW)),
    skip: int = 0,
    limit: int = 100
) -> Any:
    """
    List all users in the current tenant.

    Requires: USER_VIEW permission (CXO, BA, Developer, Product Manager)

    SPRINT 2 Phase 5: Tenant-scoped user listing with permission check.
    """
    logger_instance = user_management_endpoints.logger
    logger_instance.info(
        f"Listing users for tenant {tenant_id} by user {current_user.email} "
        f"(skip={skip}, limit={limit})"
    )

    # Get all users in tenant
    users = crud.user.get_multi_by_tenant(
        db=db,
        tenant_id=tenant_id,
        skip=skip,
        limit=limit
    )

    logger_instance.info(f"Retrieved {len(users)} users for tenant {tenant_id}")

    # Convert to response schema
    return [
        schemas.user.UserResponse(
            id=user.id,
            email=user.email,
            roles=user.roles,
            is_superuser=user.is_superuser,
            tenant_id=user.tenant_id,
            created_at=user.created_at
        )
        for user in users
    ]


@router.post("/invite", response_model=schemas.user.UserResponse, status_code=status.HTTP_201_CREATED)
def invite_user_to_tenant(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.USER_INVITE)),
    user_in: schemas.user.UserInvite
) -> Any:
    """
    Invite a new user to the tenant.

    Requires: USER_INVITE permission (CXO only)

    SPRINT 2 Phase 5: Tenant admins can invite users with specified roles.

    Note: This creates the user immediately. In production, you might want to:
    - Send an email invitation instead
    - Generate a temporary password or invite token
    - Require user to set password on first login
    """
    logger_instance = user_management_endpoints.logger
    logger_instance.info(
        f"Inviting user {user_in.email} to tenant {tenant_id} "
        f"by admin {current_user.email} with roles: {user_in.roles}"
    )

    # Check if email already exists
    existing_user = crud.user.get_user_by_email(db, email=user_in.email)
    if existing_user:
        logger_instance.warning(
            f"Invite failed - email {user_in.email} already exists (user_id={existing_user.id})"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists"
        )

    # Check tenant user limit
    from app.crud.crud_tenant import tenant as crud_tenant
    limits = crud_tenant.check_limits(db, tenant_id=tenant_id)

    if not limits["can_add_user"]:
        logger_instance.warning(
            f"Invite failed - tenant {tenant_id} has reached user limit "
            f"({limits['current_users']}/{limits['max_users']})"
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "user_limit_reached",
                "message": f"Tenant has reached maximum user limit ({limits['max_users']} users)",
                "current_users": limits['current_users'],
                "max_users": limits['max_users']
            }
        )

    # Create user in tenant
    user_create = schemas.user.UserCreate(
        email=user_in.email,
        password=user_in.password,  # TODO: Consider auto-generating and emailing
        roles=user_in.roles
    )

    new_user = crud.user.create_user(
        db=db,
        obj_in=user_create,
        tenant_id=tenant_id
    )

    logger_instance.info(
        f"User {new_user.email} (id={new_user.id}) invited successfully to tenant {tenant_id}"
    )

    return schemas.user.UserResponse(
        id=new_user.id,
        email=new_user.email,
        roles=new_user.roles,
        is_superuser=new_user.is_superuser,
        tenant_id=new_user.tenant_id,
        created_at=new_user.created_at
    )


@router.put("/{user_id}/roles", response_model=schemas.user.UserResponse)
def update_user_roles(
    *,
    user_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.USER_MANAGE)),
    roles_update: schemas.user.UserRolesUpdate
) -> Any:
    """
    Update a user's roles within the tenant.

    Requires: USER_MANAGE permission (CXO only)

    SPRINT 2 Phase 5: Tenant admins can change user roles.

    Restrictions:
    - Cannot update your own roles (prevent admin lockout)
    - User must be in the same tenant
    - Cannot make users superusers (platform-level only)
    """
    logger_instance = user_management_endpoints.logger
    logger_instance.info(
        f"Updating roles for user {user_id} in tenant {tenant_id} "
        f"by admin {current_user.email}: {roles_update.roles}"
    )

    # Get target user
    target_user = crud.user.get(db, id=user_id)
    if not target_user:
        logger_instance.warning(f"User {user_id} not found for role update")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify user is in same tenant
    if target_user.tenant_id != tenant_id:
        logger_instance.warning(
            f"Permission denied: User {user_id} (tenant={target_user.tenant_id}) "
            f"not in admin's tenant ({tenant_id})"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"  # Don't leak cross-tenant info
        )

    # Prevent self-role modification (admin lockout prevention)
    if target_user.id == current_user.id:
        logger_instance.warning(
            f"User {current_user.email} attempted to modify their own roles"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot modify your own roles. Ask another admin."
        )

    # Update roles
    target_user.roles = roles_update.roles
    db.add(target_user)
    db.commit()
    db.refresh(target_user)

    logger_instance.info(
        f"Roles updated for user {target_user.email} (id={user_id}): {target_user.roles}"
    )

    return schemas.user.UserResponse(
        id=target_user.id,
        email=target_user.email,
        roles=target_user.roles,
        is_superuser=target_user.is_superuser,
        tenant_id=target_user.tenant_id,
        created_at=target_user.created_at
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_from_tenant(
    *,
    user_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.USER_DELETE))
) -> None:
    """
    Delete a user from the tenant.

    Requires: USER_DELETE permission (CXO only)

    SPRINT 2 Phase 5: Tenant admins can remove users from their tenant.

    Restrictions:
    - Cannot delete yourself (prevent admin lockout)
    - User must be in the same tenant
    - Cannot delete platform superusers

    WARNING: This is a hard delete. Consider implementing soft delete in production.
    """
    logger_instance = user_management_endpoints.logger
    logger_instance.info(
        f"Deleting user {user_id} from tenant {tenant_id} by admin {current_user.email}"
    )

    # Get target user
    target_user = crud.user.get(db, id=user_id)
    if not target_user:
        logger_instance.warning(f"User {user_id} not found for deletion")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify user is in same tenant
    if target_user.tenant_id != tenant_id:
        logger_instance.warning(
            f"Permission denied: User {user_id} (tenant={target_user.tenant_id}) "
            f"not in admin's tenant ({tenant_id})"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"  # Don't leak cross-tenant info
        )

    # Prevent self-deletion (admin lockout prevention)
    if target_user.id == current_user.id:
        logger_instance.warning(
            f"User {current_user.email} attempted to delete themselves"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete yourself. Ask another admin."
        )

    # Prevent deletion of platform superusers
    if target_user.is_superuser:
        logger_instance.warning(
            f"Attempt to delete platform superuser {target_user.email} (id={user_id})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete platform superusers"
        )

    # Delete user
    db.delete(target_user)
    db.commit()

    logger_instance.info(
        f"User {target_user.email} (id={user_id}) deleted successfully from tenant {tenant_id}"
    )


@router.put("/me", response_model=schemas.user.UserResponse)
def update_my_profile(
    *,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    profile_update: schemas.user.UserProfileUpdate
) -> Any:
    """
    Update current user's profile (email).

    Users can update their own email address.
    Other fields like roles must be changed by admins.
    """
    logger_instance = user_management_endpoints.logger
    logger_instance.info(f"User {current_user.email} updating profile to email={profile_update.email}")

    # Check if new email is already taken
    if profile_update.email != current_user.email:
        existing_user = crud.user.get_user_by_email(db, email=profile_update.email)
        if existing_user:
            logger_instance.warning(f"Email {profile_update.email} already exists")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )

    # Update email
    current_user.email = profile_update.email
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    logger_instance.info(f"User profile updated: {current_user.email}")

    return schemas.user.UserResponse(
        id=current_user.id,
        email=current_user.email,
        roles=current_user.roles,
        is_superuser=current_user.is_superuser,
        tenant_id=current_user.tenant_id,
        created_at=current_user.created_at
    )


@router.post("/me/password", status_code=status.HTTP_200_OK)
def change_my_password(
    *,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    password_change: schemas.user.PasswordChange
) -> Any:
    """
    Change current user's password.

    Requires current password verification for security.
    """
    logger_instance = user_management_endpoints.logger
    logger_instance.info(f"User {current_user.email} requesting password change")

    # Verify current password
    from app.core.security import verify_password, get_password_hash

    if not verify_password(password_change.current_password, current_user.hashed_password):
        logger_instance.warning(f"User {current_user.email} provided incorrect current password")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Update password
    current_user.hashed_password = get_password_hash(password_change.new_password)
    db.add(current_user)
    db.commit()

    logger_instance.info(f"Password changed successfully for user {current_user.email}")

    return {"message": "Password changed successfully"}


@router.put("/{user_id}", response_model=schemas.user.UserResponse)
def update_user_status(
    *,
    user_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.USER_MANAGE)),
    user_update: schemas.user.UserStatusUpdate
) -> Any:
    """
    Update user status (activate/deactivate).

    Requires: USER_MANAGE permission (CXO only)

    Restrictions:
    - Cannot update your own status (prevent admin lockout)
    - User must be in the same tenant
    """
    logger_instance = user_management_endpoints.logger
    logger_instance.info(
        f"Updating status for user {user_id} to is_active={user_update.is_active} "
        f"by admin {current_user.email}"
    )

    # Get target user
    target_user = crud.user.get(db, id=user_id)
    if not target_user:
        logger_instance.warning(f"User {user_id} not found for status update")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify user is in same tenant
    if target_user.tenant_id != tenant_id:
        logger_instance.warning(
            f"Permission denied: User {user_id} (tenant={target_user.tenant_id}) "
            f"not in admin's tenant ({tenant_id})"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent self-status modification
    if target_user.id == current_user.id:
        logger_instance.warning(
            f"User {current_user.email} attempted to modify their own status"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot modify your own status. Ask another admin."
        )

    # Update status
    target_user.is_active = user_update.is_active
    db.add(target_user)
    db.commit()
    db.refresh(target_user)

    logger_instance.info(
        f"Status updated for user {target_user.email} (id={user_id}): is_active={target_user.is_active}"
    )

    return schemas.user.UserResponse(
        id=target_user.id,
        email=target_user.email,
        roles=target_user.roles,
        is_superuser=target_user.is_superuser,
        tenant_id=target_user.tenant_id,
        created_at=target_user.created_at
    )


@router.get("/me/permissions", response_model=List[str])
def get_my_permissions(
    *,
    current_user: models.User = Depends(deps.get_current_user)
) -> Any:
    """
    Get all permissions for the current user.

    SPRINT 2 Phase 5: Introspection endpoint for UI to check permissions.

    Returns:
        List of permission strings (e.g., ["document:read", "document:write", ...])
    """
    logger_instance = user_management_endpoints.logger
    logger_instance.info(f"Fetching permissions for user {current_user.email}")

    from app.core.permissions import permission_checker

    permissions = permission_checker.get_user_permissions(current_user.roles)

    permission_strings = [p.value for p in permissions]

    logger_instance.info(
        f"User {current_user.email} has {len(permission_strings)} permissions"
    )

    return permission_strings
