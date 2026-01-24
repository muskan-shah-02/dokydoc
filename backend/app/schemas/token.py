from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    """
    Defines the response model for a JWT token.

    BE-04/AUTH-01 FIX: Now includes refresh_token for session persistence.
    """
    access_token: str
    refresh_token: str  # BE-04 FIX: Added refresh token
    token_type: str


class TokenData(BaseModel):
    """
    Defines the data contained within the JWT.
    This schema is used for decoding and verifying the token's payload.
    """
    email: Optional[str] = None

