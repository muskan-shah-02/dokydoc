from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session
from typing import Optional

from app.core.config import settings
from app.schemas import token as token_schema
from app.db.session import get_db
from app import crud
from app.models.user import User
from app.schemas.user import Role
from app.core.logging import get_logger
from app.core.exceptions import AuthenticationException

# Get logger for this module
logger = get_logger("api.deps")

# This tells FastAPI which URL to use to get the token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login/access-token")


# Use the get_db function directly from session module


def get_tenant_id(request: Request) -> int:
    """
    Extract tenant_id from request state (injected by TenantContextMiddleware).

    SPRINT 2: This dependency is injected into EVERY endpoint that needs tenant context.
    Fails fast if tenant_id is missing.

    :param request: FastAPI Request object
    :return: Tenant ID from request state
    :raises AuthenticationException: If tenant context is not found
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    if tenant_id is None:
        logger.error("Tenant context not found in request state")
        raise AuthenticationException(
            "Tenant context not found. This endpoint requires authentication."
        )

    logger.debug(f"Tenant ID from request: {tenant_id}")
    return tenant_id


def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
    request: Request = None
) -> User:
    """
    Dependency function to decode a JWT token and get the current user from the database.

    BE-04/AUTH-01 FIX: Now validates token type to ensure only access tokens are accepted.
    SPRINT 2 ENHANCEMENT: Validates tenant context from JWT matches user's tenant_id.
    """
    # Sprint 8: API key auth — if middleware resolved the user, skip JWT validation
    if request is not None:
        api_key_user = getattr(request.state, "api_key_user", None)
        if api_key_user is not None:
            logger.debug(f"API key auth bypass for user {api_key_user.email}")
            return api_key_user

    logger.debug("Validating user token")

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        # BE-04/AUTH-01 FIX: Validate token type
        token_type = payload.get("type")
        if token_type != "access":
            logger.warning(f"Invalid token type: {token_type} (expected 'access')")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token type. Please use an access token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # SPRINT 2: Extract tenant_id from JWT
        token_tenant_id = payload.get("tenant_id")

        token_data = token_schema.TokenData(email=payload.get("sub"))
        if token_data.email is None:
            logger.warning("Token validation failed - no email in token")
            raise HTTPException(status_code=403, detail="Could not validate credentials")

        # SPRINT 2: Validate tenant_id is present in token
        if token_tenant_id is None:
            logger.warning("Token validation failed - no tenant_id in token")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token: missing tenant context"
            )

    except (jwt.JWTError, ValidationError) as e:
        logger.warning(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = crud.user.get_user_by_email(db, email=token_data.email)
    if not user:
        logger.warning(f"User not found for email: {token_data.email}")
        raise HTTPException(status_code=404, detail="User not found")

    # SPRINT 2: Validate user's tenant_id matches token tenant_id
    # EXCEPTION: Superusers with X-Tenant-Override can access other tenants
    if request and hasattr(request.state, "is_tenant_override"):
        # Superuser override - already validated in middleware
        if request.state.is_tenant_override:
            logger.debug(
                f"Superuser {user.email} accessing tenant {request.state.tenant_id} "
                f"(override from tenant {user.tenant_id})"
            )
    else:
        # Normal flow: Validate tenant match
        if user.tenant_id != token_tenant_id:
            logger.error(
                f"Tenant mismatch: User {user.email} has tenant_id={user.tenant_id} "
                f"but token has tenant_id={token_tenant_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant mismatch in authentication"
            )

    logger.debug(f"User {user.email} authenticated successfully for tenant {user.tenant_id}")
    return user

def get_current_user_with_role(required_role: Role):
    """
    A dependency that checks if the current user has the required role.
    """
    def _get_user_with_role(current_user: User = Depends(get_current_user)):
        logger.debug(f"Checking role {required_role.value} for user {current_user.email}")

        if required_role.value not in current_user.roles:
            logger.warning(f"User {current_user.email} attempted to access resource requiring role {required_role.value}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )

        logger.debug(f"User {current_user.email} has required role {required_role.value}")
        return current_user
    return _get_user_with_role


# SPRINT 2 Phase 5: Permission-based dependencies

def require_permission(required_permission):
    """
    Dependency factory that checks if the current user has a specific permission.

    SPRINT 2 Phase 5: Fine-grained permission checking.

    Usage:
        @router.get("/protected")
        def protected_endpoint(
            current_user: User = Depends(require_permission(Permission.DOCUMENT_WRITE))
        ):
            ...

    Args:
        required_permission: Permission enum value to check

    Returns:
        Dependency function that validates permission
    """
    from app.core.permissions import permission_checker

    def _check_permission(current_user: User = Depends(get_current_user)):
        logger.debug(
            f"Checking permission {required_permission.value} for user {current_user.email}"
        )

        if not permission_checker.user_has_permission(current_user.roles, required_permission):
            logger.warning(
                f"Permission denied: User {current_user.email} (roles={current_user.roles}) "
                f"attempted to access resource requiring {required_permission.value}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have permission to {required_permission.value}",
            )

        logger.debug(f"User {current_user.email} has permission {required_permission.value}")
        return current_user

    return _check_permission


def require_any_permission(*required_permissions):
    """
    Dependency factory that checks if user has ANY of the specified permissions.

    SPRINT 2 Phase 5: Flexible permission checking (OR logic).

    Usage:
        @router.get("/flexible")
        def flexible_endpoint(
            current_user: User = Depends(
                require_any_permission(Permission.DOCUMENT_READ, Permission.CODE_READ)
            )
        ):
            ...

    Args:
        *required_permissions: Variable number of Permission enum values

    Returns:
        Dependency function that validates user has at least one permission
    """
    from app.core.permissions import permission_checker

    def _check_any_permission(current_user: User = Depends(get_current_user)):
        logger.debug(
            f"Checking if user {current_user.email} has any of: "
            f"{[p.value for p in required_permissions]}"
        )

        if not permission_checker.user_has_any_permission(
            current_user.roles, list(required_permissions)
        ):
            logger.warning(
                f"Permission denied: User {current_user.email} (roles={current_user.roles}) "
                f"attempted to access resource requiring any of: "
                f"{[p.value for p in required_permissions]}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have the required permissions to access this resource",
            )

        logger.debug(f"User {current_user.email} has required permissions")
        return current_user

    return _check_any_permission


def require_all_permissions(*required_permissions):
    """
    Dependency factory that checks if user has ALL of the specified permissions.

    SPRINT 2 Phase 5: Strict permission checking (AND logic).

    Usage:
        @router.post("/strict")
        def strict_endpoint(
            current_user: User = Depends(
                require_all_permissions(Permission.DOCUMENT_WRITE, Permission.BILLING_VIEW)
            )
        ):
            ...

    Args:
        *required_permissions: Variable number of Permission enum values

    Returns:
        Dependency function that validates user has all permissions
    """
    from app.core.permissions import permission_checker

    def _check_all_permissions(current_user: User = Depends(get_current_user)):
        logger.debug(
            f"Checking if user {current_user.email} has all of: "
            f"{[p.value for p in required_permissions]}"
        )

        if not permission_checker.user_has_all_permissions(
            current_user.roles, list(required_permissions)
        ):
            logger.warning(
                f"Permission denied: User {current_user.email} (roles={current_user.roles}) "
                f"attempted to access resource requiring all of: "
                f"{[p.value for p in required_permissions]}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have all the required permissions to access this resource",
            )

        logger.debug(f"User {current_user.email} has all required permissions")
        return current_user

    return _check_all_permissions


def require_tenant_admin(current_user: User = Depends(get_current_user)):
    """
    Dependency that requires user to be a tenant admin (CXO role).

    SPRINT 2 Phase 5: Tenant admin restriction for user management.

    Usage:
        @router.post("/admin-only")
        def admin_endpoint(
            current_user: User = Depends(require_tenant_admin)
        ):
            ...

    Args:
        current_user: Current authenticated user

    Returns:
        User if they are tenant admin

    Raises:
        HTTPException: If user is not a tenant admin
    """
    from app.core.permissions import permission_checker

    logger.debug(f"Checking if user {current_user.email} is tenant admin")

    if not permission_checker.is_tenant_admin(current_user.roles):
        logger.warning(
            f"Tenant admin access denied: User {current_user.email} (roles={current_user.roles}) "
            f"attempted to access tenant admin resource"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant administrators (CXO) can access this resource",
        )

    logger.debug(f"User {current_user.email} is tenant admin")
    return current_user


# Phase 3 (P3.9/P3.15): Premium tier gating helper.
# Used by data-flow endpoints to 403 free-tier tenants.
PREMIUM_TIERS = {"professional", "pro", "enterprise"}


def get_premium_tenant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Ensure the caller's tenant is on a paid tier."""
    from app.models.tenant import Tenant

    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    tier = (tenant.tier if tenant else "free") or "free"
    if tier.lower() not in PREMIUM_TIERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PREMIUM_REQUIRED",
                "message": "Request Data Flow diagrams require a Pro or Enterprise plan.",
                "current_tier": tier,
            },
        )
    return current_user


def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Allow superusers or CXO/Admin roles. Used by the backfill endpoint."""
    roles = [str(r) for r in (current_user.roles or [])]
    if current_user.is_superuser or any(r in ("CXO", "Admin") for r in roles):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )


def get_optional_tenant_id(request: Request) -> Optional[int]:
    """Return tenant_id from request state, or None if unauthenticated."""
    return getattr(request.state, "tenant_id", None)


def get_optional_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
    request: Request = None,
) -> Optional[User]:
    """Return the current user, or None if unauthenticated (never raises)."""
    try:
        return get_current_user(db=db, token=token, request=request)
    except (HTTPException, Exception):
        return None


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the current user, ensuring the account is active."""
    if not getattr(current_user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account.",
        )
    return current_user
