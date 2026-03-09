"""
Audit Middleware — Automatically logs user actions for mutating API requests.

Captures POST, PUT, DELETE, PATCH requests to tracked endpoints and creates
audit log entries without modifying individual endpoint code.
"""
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logging import get_logger

logger = get_logger("audit_middleware")

# Endpoints to track (prefix match)
TRACKED_PREFIXES = [
    "/api/v1/documents",
    "/api/v1/repositories",
    "/api/v1/code-components",
    "/api/v1/initiatives",
    "/api/v1/ontology",
    "/api/v1/users",
    "/api/v1/webhooks",
    "/api/v1/tasks",
    "/api/login",
]

# Methods that represent state-changing operations
TRACKED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


def _extract_resource_info(path: str) -> tuple:
    """Extract resource type and ID from URL path."""
    parts = path.strip("/").split("/")

    # Map URL segments to resource types
    resource_map = {
        "documents": "document",
        "repositories": "repository",
        "code-components": "code_component",
        "initiatives": "initiative",
        "ontology": "ontology",
        "users": "user",
        "webhooks": "system",
        "tasks": "task",
        "login": "auth",
    }

    resource_type = "unknown"
    resource_id = None

    for part in parts:
        if part in resource_map:
            resource_type = resource_map[part]
        elif part.isdigit():
            resource_id = int(part)

    return resource_type, resource_id


def _method_to_action(method: str, path: str) -> str:
    """Map HTTP method + path to an action name."""
    if "login" in path:
        return "login"
    if "analyze" in path:
        return "analyze"
    if "synthesize" in path:
        return "analyze"
    if "retry" in path:
        return "analyze"
    if "webhook" in path:
        return "webhook"

    method_map = {
        "POST": "create",
        "PUT": "update",
        "DELETE": "delete",
        "PATCH": "update",
    }
    return method_map.get(method, "unknown")


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that auto-logs mutating API requests to the audit_logs table."""

    async def dispatch(self, request: Request, call_next):
        # Only track mutating requests to tracked endpoints
        if request.method not in TRACKED_METHODS:
            return await call_next(request)

        path = request.url.path
        if not any(path.startswith(prefix) for prefix in TRACKED_PREFIXES):
            return await call_next(request)

        start_time = time.time()
        response = await call_next(request)
        elapsed = time.time() - start_time

        # Log the audit event asynchronously (best-effort, never blocks response)
        try:
            resource_type, resource_id = _extract_resource_info(path)
            action = _method_to_action(request.method, path)
            status_str = "success" if response.status_code < 400 else "failure"

            # Extract user info from request state (set by auth middleware)
            tenant_id = getattr(request.state, "tenant_id", None)
            user_id = getattr(request.state, "user_id", None)
            user_email = getattr(request.state, "user_email", None)

            if not tenant_id:
                return response

            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent", "")[:500]

            description = (
                f"{request.method} {path} "
                f"(status={response.status_code}, {elapsed:.2f}s)"
            )

            # Import here to avoid circular imports
            from app.db.session import SessionLocal
            from app.crud.crud_audit_log import audit_log

            db = SessionLocal()
            try:
                audit_log.log(
                    db=db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    user_email=user_email,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    description=description,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status=status_str,
                    details={
                        "method": request.method,
                        "path": path,
                        "status_code": response.status_code,
                        "elapsed_seconds": round(elapsed, 3),
                    },
                )
            finally:
                db.close()

        except Exception as e:
            # Never fail the response due to audit logging
            logger.debug(f"Audit middleware logging failed (non-fatal): {e}")

        return response
