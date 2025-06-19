from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    """
    Defines the response model for a JWT token.
    """
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """
    Defines the data contained within the JWT.
    This schema is used for decoding and verifying the token's payload.
    """
    email: Optional[str] = None

