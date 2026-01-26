"""
Tenant registration and management endpoints.
Sprint 2 Phase 3: Tenant Registration Flow
"""
from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.core.logging import LoggerMixin, get_logger
from app.middleware.rate_limiter import limiter, RateLimits
from app.models.user import User

logger = get_logger("api.tenants")


class TenantEndpoints(LoggerMixin):
    """Tenant endpoints with enhanced logging and error handling."""

    def __init__(self):
        super().__init__()


# Create instance for use in endpoints
tenant_endpoints = TenantEndpoints()

router = APIRouter()


@router.post("/register", response_model=schemas.tenant.TenantRegistrationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RateLimits.AUTH)  # Rate limit to prevent spam (5/min, 20/hour)
def register_tenant(
    request: Request,  # Required for rate limiter
    response: Response,  # Required for rate limiter to inject headers
    *,
    db: Session = Depends(deps.get_db),
    tenant_in: schemas.tenant.TenantCreate
) -> Any:
    """
    Register a new tenant organization with the first admin user.

    This is the primary onboarding endpoint for self-service tenant registration.

    Flow:
    1. Validate subdomain availability
    2. Create tenant record
    3. Create first user as tenant admin (with CXO role)
    4. Initialize billing record
    5. Return access tokens for immediate login

    Rate Limit: 5 registrations/minute, 20/hour per IP

    Example:
        POST /api/v1/tenants/register
        {
            "name": "Acme Corporation",
            "subdomain": "acme",
            "tier": "free",
            "billing_type": "prepaid",
            "admin_email": "admin@acme.com",
            "admin_password": "SecurePass123!",
            "admin_name": "John Doe"
        }
    """
    logger = tenant_endpoints.logger
    logger.info(f"Tenant registration request for subdomain: {tenant_in.subdomain}")

    # 1. Check subdomain availability
    if not crud.tenant.is_subdomain_available(db, subdomain=tenant_in.subdomain):
        logger.warning(f"Registration failed - subdomain '{tenant_in.subdomain}' already taken")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subdomain '{tenant_in.subdomain}' is already taken"
        )

    # 2. Check if admin email is already registered
    existing_user = crud.user.get_user_by_email(db, email=tenant_in.admin_email)
    if existing_user:
        logger.warning(f"Registration failed - email '{tenant_in.admin_email}' already exists")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered. Please use a different email."
        )

    try:
        # 3. Create tenant
        tenant = crud.tenant.create_tenant(db=db, obj_in=tenant_in)
        logger.info(f"Tenant {tenant.id} created: {tenant.name} ({tenant.subdomain})")

        # 4. Create first admin user (CXO role with full permissions)
        from app.schemas.user import UserCreate
        admin_user_data = UserCreate(
            email=tenant_in.admin_email,
            password=tenant_in.admin_password,
            roles=["CXO"],  # CXO role has full tenant admin permissions
            is_superuser=False  # Not a platform superuser, just tenant admin
        )

        admin_user = crud.user.create_user(
            db=db,
            obj_in=admin_user_data,
            tenant_id=tenant.id
        )
        logger.info(f"Admin user {admin_user.id} created for tenant {tenant.id}: {admin_user.email}")

        # 5. Initialize billing record for tenant
        billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant.id)
        logger.info(f"Billing record initialized for tenant {tenant.id}: {billing.billing_type}")

        # 6. Generate access tokens for immediate login
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=admin_user.email,
            tenant_id=tenant.id,
            tenant_subdomain=tenant.subdomain,
            roles=admin_user.roles,
            is_superuser=False,
            expires_delta=access_token_expires
        )

        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token = create_refresh_token(
            subject=admin_user.email,
            tenant_id=tenant.id,
            expires_delta=refresh_token_expires
        )

        logger.info(
            f"Tenant registration complete: {tenant.name} (ID={tenant.id}, subdomain={tenant.subdomain}), "
            f"Admin: {admin_user.email}"
        )

        # 7. Return tenant info and tokens
        return {
            "tenant": tenant,
            "admin_user": {
                "id": admin_user.id,
                "email": admin_user.email,
                "roles": admin_user.roles
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "message": f"Welcome to DokyDoc! Your tenant '{tenant.name}' has been created successfully."
        }

    except ValueError as e:
        logger.error(f"Tenant registration failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during tenant registration: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during registration. Please try again."
        )


@router.get("/me", response_model=schemas.tenant.TenantResponse)
def get_current_tenant(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Get information about the current user's tenant.

    Returns tenant configuration, limits, and current status.
    """
    logger = tenant_endpoints.logger
    logger.info(f"Fetching tenant info for tenant_id={tenant_id}, user={current_user.email}")

    tenant = db.query(crud.tenant.model).filter(crud.tenant.model.id == tenant_id).first()
    if not tenant:
        logger.error(f"Tenant {tenant_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    logger.info(f"Retrieved tenant info: {tenant.name} (ID={tenant.id})")
    return tenant


@router.get("/me/stats", response_model=schemas.tenant.TenantDetailResponse)
def get_tenant_statistics(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Get detailed tenant statistics.

    Returns tenant info plus usage statistics (user count, document count, storage).
    """
    logger = tenant_endpoints.logger
    logger.info(f"Fetching tenant stats for tenant_id={tenant_id}, user={current_user.email}")

    tenant = db.query(crud.tenant.model).filter(crud.tenant.model.id == tenant_id).first()
    if not tenant:
        logger.error(f"Tenant {tenant_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    # Get usage statistics
    stats = crud.tenant.get_tenant_statistics(db, tenant_id=tenant_id)

    logger.info(
        f"Retrieved tenant stats: {tenant.name} - "
        f"{stats['user_count']} users, {stats['document_count']} documents, "
        f"{stats['storage_used_mb']} MB storage"
    )

    # Combine tenant data with stats
    tenant_data = schemas.tenant.TenantResponse.model_validate(tenant).model_dump()
    tenant_data.update(stats)

    return tenant_data


@router.get("/me/limits")
def check_tenant_limits(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Check current tenant usage against limits.

    Useful for UI to show warnings before hitting limits.

    Returns:
        {
            "can_add_user": bool,
            "can_add_document": bool,
            "users_remaining": int,
            "documents_remaining": int,
            "current_users": int,
            "current_documents": int,
            "max_users": int,
            "max_documents": int
        }
    """
    logger = tenant_endpoints.logger
    logger.info(f"Checking limits for tenant_id={tenant_id}")

    try:
        limits = crud.tenant.check_limits(db, tenant_id=tenant_id)
        logger.info(f"Limits checked: {limits['users_remaining']} users remaining, {limits['documents_remaining']} documents remaining")
        return limits
    except ValueError as e:
        logger.error(f"Error checking limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/me", response_model=schemas.tenant.TenantResponse)
def update_tenant_settings(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user_with_role(schemas.user.Role.CXO)),  # Only CXO can update
    tenant_update: schemas.tenant.TenantUpdate
) -> Any:
    """
    Update tenant settings.

    Only accessible by users with CXO role (tenant admins).

    Updatable fields:
    - name: Organization name
    - status: active, suspended, cancelled (use with caution)
    - tier: free, pro, enterprise
    - max_users: Maximum users allowed
    - max_documents: Maximum documents allowed
    - settings: Additional JSON settings
    """
    logger = tenant_endpoints.logger
    logger.info(f"Updating tenant {tenant_id} settings by user {current_user.get('email')}")

    updated_tenant = crud.tenant.update_tenant(
        db=db,
        tenant_id=tenant_id,
        obj_in=tenant_update
    )

    if not updated_tenant:
        logger.error(f"Tenant {tenant_id} not found for update")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    logger.info(f"Tenant {tenant_id} updated successfully: {updated_tenant.name}")
    return updated_tenant


@router.get("/check-subdomain/{subdomain}")
@limiter.limit("30/minute")  # Allow frequent checks during registration form
def check_subdomain_availability(
    subdomain: str,
    request: Request,  # Required for rate limiter
    response: Response,  # Required for rate limiter to inject headers
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Check if a subdomain is available for registration.

    Public endpoint (no auth required) for real-time validation during registration.

    Rate Limit: 30 checks/minute per IP

    Returns:
        {
            "subdomain": str,
            "available": bool,
            "message": str
        }
    """
    logger = tenant_endpoints.logger

    # Validate subdomain format (same validation as in schema)
    import re
    if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', subdomain.lower()):
        return {
            "subdomain": subdomain,
            "available": False,
            "message": "Invalid subdomain format. Use lowercase letters, numbers, and hyphens only."
        }

    # Check availability
    available = crud.tenant.is_subdomain_available(db, subdomain=subdomain)

    if available:
        message = f"Subdomain '{subdomain}' is available!"
    else:
        message = f"Subdomain '{subdomain}' is already taken. Please try another."

    logger.info(f"Subdomain check: {subdomain} - {'available' if available else 'taken'}")

    return {
        "subdomain": subdomain,
        "available": available,
        "message": message
    }
