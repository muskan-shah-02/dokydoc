from pydantic import BaseModel
from typing import Optional
from app.schemas.user import UserResponse
from app.schemas.tenant import TenantResponse

class Token(BaseModel):
    """
    Defines the response model for a JWT token.

    BE-04/AUTH-01 FIX: Now includes refresh_token for session persistence.
    SPRINT 2: Includes user and tenant data for frontend state management.
    """
    access_token: str
    refresh_token: str  # BE-04 FIX: Added refresh token
    token_type: str
    user: UserResponse  # SPRINT 2: User information for frontend
    tenant: TenantResponse  # SPRINT 2: Tenant information for frontend


class TokenData(BaseModel):
    """
    Defines the data contained within the JWT.
    This schema is used for decoding and verifying the token's payload.
    """
    email: Optional[str] = None

