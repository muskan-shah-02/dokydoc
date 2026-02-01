from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
from enum import Enum

# Define the available roles using an Enum for consistency and validation
class Role(str, Enum):
    CXO = "CXO"  # Tenant Owner - "God Mode" access to everything
    ADMIN = "Admin"  # Operations manager - Users, Billing, Org settings (no code/docs)
    BA = "BA"  # Business Analyst - Documents, Analysis
    DEVELOPER = "Developer"  # Technical execution - Code, Tasks, Validation
    PRODUCT_MANAGER = "Product Manager"  # Product features - limited access

# --- Base Schema ---
# Shared properties that are common to other schemas
class UserBase(BaseModel):
    email: EmailStr
    is_active: bool = True
    roles: List[Role] = [] # Ensures 'roles' is part of the base model

# --- Create Schema ---
# Properties required when creating a new user.
class UserCreate(UserBase):
    password: str
    roles: List[Role]

# --- Update Schema ---
# Properties that can be updated. All are optional.
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    roles: Optional[List[Role]] = None

# --- Schema for Database Models ---
# This schema is used when reading data from the database.
class UserInDB(UserBase):
    id: int
    hashed_password: str

    class Config:
        from_attributes = True

# --- Schema for API Responses ---
# Properties to return to the client. It inherits 'roles' from UserBase.
class User(UserBase):
    id: int

    class Config:
        from_attributes = True


# SPRINT 2 Phase 5: User Management Schemas

class UserResponse(BaseModel):
    """
    Schema for user information in API responses.
    Includes tenant context and timestamps.
    """
    id: int
    email: EmailStr
    roles: List[Role]
    is_superuser: bool
    tenant_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserInvite(BaseModel):
    """
    Schema for inviting a new user to a tenant.

    Used by tenant admins (CXO) to add users.
    """
    email: EmailStr
    password: str  # TODO: Consider auto-generating and emailing
    roles: List[Role]


class UserRolesUpdate(BaseModel):
    """
    Schema for updating a user's roles.

    Used by tenant admins (CXO) to change permissions.
    """
    roles: List[Role]


class UserProfileUpdate(BaseModel):
    """
    Schema for updating user profile (email).

    Users can update their own email address.
    """
    email: EmailStr


class PasswordChange(BaseModel):
    """
    Schema for changing user password.

    Requires current password for security.
    """
    current_password: str
    new_password: str


class UserStatusUpdate(BaseModel):
    """
    Schema for updating user active status.

    Used by tenant admins to activate/deactivate users.
    """
    is_active: bool