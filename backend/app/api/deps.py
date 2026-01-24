from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

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
    token: str = Depends(oauth2_scheme),
    request: Request = None
) -> User:
    """
    Dependency function to decode a JWT token and get the current user from the database.

    BE-04/AUTH-01 FIX: Now validates token type to ensure only access tokens are accepted.
    SPRINT 2 ENHANCEMENT: Validates tenant context from JWT matches user's tenant_id.
    """
    logger.debug("Validating user token")

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
