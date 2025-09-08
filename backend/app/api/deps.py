from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas import token as token_schema
from app.db.session import get_db
from app import crud
from app.models.user import User
from app.schemas.user import Role
from app.core.logging import get_logger
from app.core.exceptions import AuthenticationException

# Get logger for this module
logger = get_logger("api.deps")

# This tells FastAPI which URL to use to get the token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login/access-token")


# Use the get_db function directly from session module


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    Dependency function to decode a JWT token and get the current user from the database.
    """
    logger.debug("Validating user token")
    
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = token_schema.TokenData(email=payload.get("sub"))
        if token_data.email is None:
            logger.warning("Token validation failed - no email in token")
            raise HTTPException(status_code=403, detail="Could not validate credentials")
    except (jwt.JWTError, ValidationError) as e:
        logger.warning(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = crud.user.get_user_by_email(db, email=token_data.email)
    if not user:
        logger.warning(f"User not found for email: {token_data.email}")
        raise HTTPException(status_code=404, detail="User not found")
    
    logger.debug(f"User {user.email} authenticated successfully")
    return user

def get_current_user_with_role(required_role: Role):
    """
    A dependency that checks if the current user has the required role.
    """
    def _get_user_with_role(current_user: User = Depends(get_current_user)):
        logger.debug(f"Checking role {required_role.value} for user {current_user.email}")
        
        if required_role.value not in current_user.roles:
            logger.warning(f"User {current_user.email} attempted to access resource requiring role {required_role.value}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        
        logger.debug(f"User {current_user.email} has required role {required_role.value}")
        return current_user
    return _get_user_with_role
