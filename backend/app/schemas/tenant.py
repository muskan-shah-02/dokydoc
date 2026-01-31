"""
Tenant schemas for registration and management.
Sprint 2 Phase 3: Tenant Registration Flow
"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import re


class TenantBase(BaseModel):
    """Base tenant schema with common fields."""
    name: str = Field(..., min_length=2, max_length=100, description="Organization name")
    subdomain: str = Field(..., min_length=3, max_length=63, description="Unique subdomain (3-63 chars, alphanumeric + hyphens)")


class TenantCreate(TenantBase):
    """
    Schema for tenant registration.

    Creates a new tenant organization with the first admin user.
    """
    # Tenant info
    tier: str = Field(default="free", description="Subscription tier: free, pro, enterprise")
    billing_type: str = Field(default="prepaid", description="Billing type: prepaid or postpaid")

    # First user (tenant admin) info
    admin_email: str = Field(..., description="Email for the first admin user")
    admin_password: str = Field(..., min_length=8, description="Password for admin user (min 8 chars)")
    admin_name: Optional[str] = Field(None, description="Full name of admin user")

    @field_validator('subdomain')
    @classmethod
    def validate_subdomain(cls, v: str) -> str:
        """
        Validate subdomain format:
        - 3-63 characters
        - Lowercase alphanumeric and hyphens only
        - Cannot start or end with hyphen
        - Cannot contain consecutive hyphens
        """
        if not v:
            raise ValueError("Subdomain cannot be empty")

        # Convert to lowercase
        v = v.lower()

        # Check length
        if len(v) < 3 or len(v) > 63:
            raise ValueError("Subdomain must be 3-63 characters long")

        # Check format (alphanumeric + hyphens, no start/end hyphens)
        if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', v):
            raise ValueError(
                "Subdomain must contain only lowercase letters, numbers, and hyphens. "
                "Cannot start or end with hyphen."
            )

        # Check for consecutive hyphens
        if '--' in v:
            raise ValueError("Subdomain cannot contain consecutive hyphens")

        # Reserved subdomains
        reserved = {'www', 'api', 'app', 'admin', 'mail', 'smtp', 'ftp', 'localhost',
                   'staging', 'dev', 'test', 'demo', 'docs', 'blog', 'status'}
        if v in reserved:
            raise ValueError(f"Subdomain '{v}' is reserved and cannot be used")

        return v

    @field_validator('tier')
    @classmethod
    def validate_tier(cls, v: str) -> str:
        """Validate tier is one of the allowed values."""
        allowed = {'free', 'pro', 'enterprise'}
        if v not in allowed:
            raise ValueError(f"Tier must be one of: {', '.join(allowed)}")
        return v

    @field_validator('billing_type')
    @classmethod
    def validate_billing_type(cls, v: str) -> str:
        """Validate billing type is one of the allowed values."""
        allowed = {'prepaid', 'postpaid'}
        if v not in allowed:
            raise ValueError(f"Billing type must be one of: {', '.join(allowed)}")
        return v


class TenantUpdate(BaseModel):
    """Schema for updating tenant settings (admin only)."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    status: Optional[str] = Field(None, description="Status: active, suspended, cancelled")
    tier: Optional[str] = Field(None, description="Subscription tier: free, pro, enterprise")
    billing_type: Optional[str] = Field(None, description="Billing type: prepaid or postpaid")
    max_users: Optional[int] = Field(None, ge=1, description="Maximum users allowed")
    max_documents: Optional[int] = Field(None, ge=1, description="Maximum documents allowed")
    settings: Optional[dict] = Field(None, description="Additional tenant settings")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate status if provided."""
        if v is not None:
            allowed = {'active', 'suspended', 'cancelled'}
            if v not in allowed:
                raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        return v

    @field_validator('tier')
    @classmethod
    def validate_tier(cls, v: Optional[str]) -> Optional[str]:
        """Validate tier if provided."""
        if v is not None:
            allowed = {'free', 'pro', 'enterprise'}
            if v not in allowed:
                raise ValueError(f"Tier must be one of: {', '.join(allowed)}")
        return v

    @field_validator('billing_type')
    @classmethod
    def validate_billing_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate billing type if provided."""
        if v is not None:
            allowed = {'prepaid', 'postpaid'}
            if v not in allowed:
                raise ValueError(f"Billing type must be one of: {', '.join(allowed)}")
        return v


class TenantResponse(TenantBase):
    """
    Schema for tenant response (public info).

    Returned after successful registration and in tenant info queries.
    """
    id: int
    status: str
    tier: str
    billing_type: str
    max_users: int
    max_documents: int
    created_at: datetime
    settings: dict

    model_config = {"from_attributes": True}


class TenantDetailResponse(TenantResponse):
    """
    Detailed tenant response (admin only).

    Includes additional fields like user count, document count, etc.
    """
    user_count: Optional[int] = Field(None, description="Current number of users")
    document_count: Optional[int] = Field(None, description="Current number of documents")
    storage_used_mb: Optional[float] = Field(None, description="Storage used in MB")


class TenantRegistrationResponse(BaseModel):
    """
    Response after successful tenant registration.

    Includes tenant info and access tokens for the admin user.
    """
    tenant: TenantResponse
    admin_user: dict = Field(..., description="Admin user information")
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    message: str = Field(default="Tenant registered successfully", description="Success message")
