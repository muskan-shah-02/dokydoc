"""
Tenant context middleware for multi-tenancy support.

This middleware extracts tenant_id from JWT tokens and injects it into request.state,
making it available to all endpoints and dependencies.

CRITICAL SECURITY FEATURE:
- Ensures every authenticated request has tenant context
- Prevents cross-tenant data access
- Supports superuser override for debugging/support
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError

from app.core.config import settings
from app.core.exceptions import AuthenticationException
from app.core.logging import get_logger

logger = get_logger("tenant_context")

# Public routes that don't require tenant context
PUBLIC_ROUTES = [
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/login/access-token",  # Login endpoint
    "/api/refresh",  # Refresh token endpoint
    "/api/v1/tenants/register",  # Tenant registration
    "/api/v1/tenants/check-subdomain",  # Subdomain availability check
]


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Extracts tenant_id from JWT and injects into request.state.

    This ensures EVERY authenticated request has tenant context.
    Unauthenticated routes (login, register) bypass this middleware.

    SUPERUSER OVERRIDE:
    Superusers can access any tenant by passing X-Tenant-Override header.
    This is logged for audit purposes.
    """

    async def dispatch(self, request: Request, call_next):
        # Skip tenant context for public routes
        if self._is_public_route(request.url.path):
            response = await call_next(request)
            return response

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None

        if not token:
            # No token = no tenant context (will be handled by auth dependency)
            response = await call_next(request)
            return response

        try:
            # Decode JWT token to extract tenant_id
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )

            default_tenant_id = payload.get("tenant_id")
            is_superuser = payload.get("is_superuser", False)
            user_email = payload.get("sub")

            # 🔑 SUPERUSER OVERRIDE LOGIC
            # Superusers can access any tenant via X-Tenant-Override header
            if is_superuser and "X-Tenant-Override" in request.headers:
                try:
                    override_tenant_id = int(request.headers["X-Tenant-Override"])

                    # Inject overridden tenant_id
                    request.state.tenant_id = override_tenant_id
                    request.state.is_tenant_override = True
                    request.state.original_tenant_id = default_tenant_id

                    # AUDIT LOG: Record superuser override for security tracking
                    logger.warning(
                        f"🔓 SUPERUSER OVERRIDE: User '{user_email}' "
                        f"accessing Tenant {override_tenant_id} "
                        f"(original: {default_tenant_id}) "
                        f"on {request.method} {request.url.path}"
                    )

                except ValueError:
                    # Invalid override value
                    raise AuthenticationException(
                        "Invalid X-Tenant-Override header: must be an integer tenant ID"
                    )
            else:
                # Normal flow: Use tenant from JWT
                request.state.tenant_id = default_tenant_id
                request.state.is_tenant_override = False
                request.state.original_tenant_id = default_tenant_id

            # Store additional context for logging and audit
            request.state.tenant_subdomain = payload.get("tenant_subdomain")

            # Validate tenant_id exists
            if not request.state.tenant_id:
                logger.error(f"Missing tenant_id in JWT for user: {user_email}")
                raise AuthenticationException("Missing tenant_id in authentication token")

        except JWTError as e:
            # JWT decode error - log and continue without setting tenant context
            # This allows unauthenticated endpoints to work, but authenticated
            # endpoints will fail at the dependency level
            logger.debug(f"JWT decode error in tenant context: {e}")
            # Set tenant_id to None explicitly so we know middleware ran
            request.state.tenant_id = None
            request.state.is_tenant_override = False

        except AuthenticationException:
            # Re-raise authentication exceptions
            raise

        except Exception as e:
            # Unexpected errors in tenant context extraction
            logger.error(f"Unexpected error in tenant context middleware: {e}")
            raise AuthenticationException("Failed to extract tenant context from request")

        # Continue with request processing
        response = await call_next(request)
        return response

    def _is_public_route(self, path: str) -> bool:
        """Check if route is public (doesn't require tenant context)."""
        # Exact match
        if path in PUBLIC_ROUTES:
            return True

        # Prefix match (e.g., /docs/*)
        for public_route in PUBLIC_ROUTES:
            if path.startswith(public_route):
                return True

        return False
