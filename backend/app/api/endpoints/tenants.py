"""
Tenant registration and management endpoints.
Sprint 2 Phase 3: Tenant Registration Flow
"""
from datetime import timedelta
from typing import Any, Dict
from fastapi import Body
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
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

        # P5-10: Set initial onboarding flag in tenant settings
        from sqlalchemy import update as sql_update
        from app.models.tenant import Tenant as TenantModel
        initial_settings = dict(tenant.settings or {})
        if "onboarding_complete" not in initial_settings:
            initial_settings["onboarding_complete"] = False
            db.execute(
                sql_update(TenantModel).where(TenantModel.id == tenant.id).values(settings=initial_settings)
            )
            db.commit()
            db.refresh(tenant)

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

        # P5-10: Dispatch background industry detection if company_website provided
        if tenant_in.company_website:
            try:
                from app.tasks.tenant_tasks import detect_tenant_industry
                detect_tenant_industry.delay(tenant.id, tenant_in.company_website)
                logger.info(
                    f"[P5-10] Queued industry detection for tenant {tenant.id} from {tenant_in.company_website}"
                )
            except Exception as bg_err:
                # Non-fatal — user can set industry manually in onboarding wizard
                logger.warning(f"[P5-10] Could not queue industry detection: {bg_err}")

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


@router.get("/me/settings")
def get_tenant_settings(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Get current tenant's settings JSON blob.

    P5-10: Used by onboarding wizard to check onboarding_complete flag
    and read auto-detected industry.

    Returns:
        {"tenant_id": int, "settings": dict}
    """
    logger = tenant_endpoints.logger
    from app.models.tenant import Tenant as TenantModel
    tenant = db.query(TenantModel).filter(TenantModel.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    return {"tenant_id": tenant_id, "settings": tenant.settings or {}}


@router.patch("/me/settings")
def patch_tenant_settings(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user_with_role(schemas.user.Role.CXO)),
    payload: Dict[str, Any] = Body(...)
) -> Any:
    """
    Merge-update tenant settings JSON.

    P5-10: Used by onboarding wizard to set onboarding_complete=true, preferred
    industry, glossary entries, etc. Only top-level keys in the payload are
    merged — existing keys not in payload are preserved.

    Only CXO role can update settings.

    Returns:
        {"tenant_id": int, "settings": dict}
    """
    logger = tenant_endpoints.logger
    from sqlalchemy import update as sql_update
    from app.models.tenant import Tenant as TenantModel

    tenant = db.query(TenantModel).filter(TenantModel.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    merged = dict(tenant.settings or {})
    merged.update(payload)

    db.execute(
        sql_update(TenantModel).where(TenantModel.id == tenant_id).values(settings=merged)
    )
    db.commit()

    logger.info(f"[P5-10] Settings updated for tenant {tenant_id}: keys={list(payload.keys())}")
    return {"tenant_id": tenant_id, "settings": merged}


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


@router.get("/org-profile", response_model=schemas.tenant.OrgProfileResponse)
def get_org_profile(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Get the organization profile used by AskyDoc for context.

    Any authenticated user in the tenant can view the org profile.
    """
    tenant = db.query(crud.tenant.model).filter(crud.tenant.model.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    org_profile = (tenant.settings or {}).get("org_profile", {})

    return schemas.tenant.OrgProfileResponse(
        mission=org_profile.get("mission"),
        company_description=org_profile.get("company_description"),
        industry=org_profile.get("industry"),
        products_services=org_profile.get("products_services", []),
        key_objectives=org_profile.get("key_objectives", []),
        tech_stack=org_profile.get("tech_stack", []),
        team_size=org_profile.get("team_size"),
        founded_year=org_profile.get("founded_year"),
        is_configured=bool(org_profile),
    )


@router.put("/org-profile", response_model=schemas.tenant.OrgProfileResponse)
def update_org_profile(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user_with_role(schemas.user.Role.CXO)),
    profile_in: schemas.tenant.OrgProfileUpdate
) -> Any:
    """
    Update the organization profile for AskyDoc context.

    Only CXO/Admin can update the org profile. This data is used by AskyDoc
    to provide organization-aware answers.
    """
    tenant = db.query(crud.tenant.model).filter(crud.tenant.model.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Merge with existing settings
    current_settings = dict(tenant.settings or {})
    current_profile = current_settings.get("org_profile", {})

    # Only update provided fields
    update_data = profile_in.model_dump(exclude_unset=True)
    current_profile.update(update_data)
    current_settings["org_profile"] = current_profile

    # Update tenant settings
    from sqlalchemy import update as sql_update
    from app.models.tenant import Tenant
    db.execute(
        sql_update(Tenant).where(Tenant.id == tenant_id).values(settings=current_settings)
    )
    db.commit()
    db.refresh(tenant)

    org_profile = current_settings.get("org_profile", {})
    return schemas.tenant.OrgProfileResponse(
        mission=org_profile.get("mission"),
        company_description=org_profile.get("company_description"),
        industry=org_profile.get("industry"),
        products_services=org_profile.get("products_services", []),
        key_objectives=org_profile.get("key_objectives", []),
        tech_stack=org_profile.get("tech_stack", []),
        team_size=org_profile.get("team_size"),
        founded_year=org_profile.get("founded_year"),
        is_configured=bool(org_profile),
    )


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
        return JSONResponse(
            status_code=200,
            content={
                "subdomain": subdomain,
                "available": False,
                "message": "Invalid subdomain format. Use lowercase letters, numbers, and hyphens only."
            }
        )

    # Check availability
    available = crud.tenant.is_subdomain_available(db, subdomain=subdomain)

    if available:
        message = f"Subdomain '{subdomain}' is available!"
    else:
        message = f"Subdomain '{subdomain}' is already taken. Please try another."

    logger.info(f"Subdomain check: {subdomain} - {'available' if available else 'taken'}")

    return JSONResponse(
        status_code=200,
        content={
            "subdomain": subdomain,
            "available": available,
            "message": message
        }
    )
