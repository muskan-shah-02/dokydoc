"""
Rate limiting middleware for API endpoints.
Protects against abuse and ensures fair resource allocation.

Fix for API-01: Rate Limiting Fix
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from typing import Callable

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("rate_limiter")


def get_identifier(request: Request) -> str:
    """
    Get unique identifier for rate limiting.

    Strategy:
        1. Use user_id if authenticated (from JWT token)
        2. Fall back to IP address for unauthenticated requests

    This prevents:
        - Authenticated users abusing the system with multiple IPs
        - IP-based limits for public endpoints
    """
    # Check if user is authenticated
    if hasattr(request.state, "user_id") and request.state.user_id:
        identifier = f"user:{request.state.user_id}"
        logger.debug(f"Rate limit identifier: {identifier}")
        return identifier

    # Fall back to IP address
    ip = get_remote_address(request)
    logger.debug(f"Rate limit identifier: ip:{ip}")
    return ip


# Initialize rate limiter with Redis backend
limiter = Limiter(
    key_func=get_identifier,
    storage_uri=settings.REDIS_URL,
    default_limits=[
        f"{settings.RATE_LIMIT_PER_MINUTE}/minute",
        f"{settings.RATE_LIMIT_PER_HOUR}/hour"
    ],
    strategy="fixed-window",  # Could use "moving-window" for better accuracy
    headers_enabled=True  # Include rate limit info in response headers
)


def get_rate_limiter() -> Limiter:
    """
    Get the rate limiter instance.

    Returns:
        Limiter instance
    """
    return limiter


# Custom rate limit exceeded handler
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded errors.

    Returns user-friendly error message with retry-after information.
    """
    logger.warning(
        f"⚠️ Rate limit exceeded for {get_identifier(request)} on {request.url.path}"
    )

    return {
        "error": "RateLimitExceeded",
        "message": "Too many requests. Please slow down and try again later.",
        "detail": str(exc.detail) if hasattr(exc, "detail") else None,
        "retry_after": exc.detail if isinstance(exc.detail, int) else None
    }


# Predefined rate limits for different endpoint types
class RateLimits:
    """Common rate limit configurations for different endpoint types."""

    # Public endpoints (higher limits)
    PUBLIC = "200/minute"

    # Authentication endpoints (prevent brute force)
    AUTH = "5/minute;20/hour"

    # Document upload (heavy operation)
    UPLOAD = "10/minute;50/hour"

    # AI analysis (expensive operation)
    ANALYSIS = "20/minute;100/hour"

    # Billing endpoints (sensitive)
    BILLING = "30/minute;200/hour"

    # Admin endpoints (restricted)
    ADMIN = "100/minute"

    # No limit (for internal/health check endpoints)
    UNLIMITED = "10000/minute"
