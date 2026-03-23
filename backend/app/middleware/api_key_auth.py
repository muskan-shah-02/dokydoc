"""
API Key Authentication Middleware
Sprint 8: Allows requests with X-API-Key header to authenticate without a JWT.

Flow:
  1. If Authorization: Bearer <token> header exists → normal JWT auth (no-op here)
  2. If X-API-Key: dk_live_<token> header exists → resolve to user + inject tenant context
  3. Otherwise → pass through (endpoint-level guards will reject unauthenticated requests)

The middleware stores resolved user info on request.state so that downstream
get_current_user() and get_tenant_id() deps can reuse it without re-querying.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger
from app.crud.crud_api_key import crud_api_key

logger = get_logger("middleware.api_key_auth")

# Routes that are always JWT-only (never allow API key access)
_JWT_ONLY_PREFIXES = ["/login", "/api/v1/users", "/api/v1/tenants"]


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Intercepts requests that carry X-API-Key and resolves them to a tenant+user context.
    """

    async def dispatch(self, request: Request, call_next):
        raw_key = request.headers.get("X-API-Key")

        # Only act if an API key is present AND no Bearer token is present
        bearer = request.headers.get("Authorization", "")
        if raw_key and not bearer.startswith("Bearer "):
            # Block JWT-only routes
            path = request.url.path
            if any(path.startswith(p) for p in _JWT_ONLY_PREFIXES):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "This endpoint requires user authentication, not an API key."},
                )

            # Resolve key
            from app.db.session import SessionLocal

            db = SessionLocal()
            try:
                api_key = crud_api_key.get_by_raw_key(db, raw_key)
                if api_key is None or not crud_api_key.is_valid(api_key):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or expired API key."},
                    )

                # Load user
                from app.crud.crud_user import user as crud_user

                user = crud_user.get(db, id=api_key.user_id)
                if user is None or not user.is_active:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "API key owner account is inactive."},
                    )

                # Record usage (async-safe: simple DB write)
                crud_api_key.record_usage(db, api_key)

                # Inject into request.state — picked up by get_current_user / get_tenant_id
                request.state.api_key_user = user
                request.state.tenant_id = api_key.tenant_id
                request.state.api_key_id = api_key.id

                logger.debug(
                    f"API key auth: user={user.email}, tenant={api_key.tenant_id}, key_id={api_key.id}"
                )
            except Exception as e:
                logger.error(f"API key middleware error: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"detail": "API key authentication failed."},
                )
            finally:
                db.close()

        response = await call_next(request)
        return response
