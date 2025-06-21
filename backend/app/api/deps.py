from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas import token as token_schema
from app.db.session import SessionLocal
from app import crud
from app.models.user import User
from fastapi import HTTPException, status
from app.schemas.user import Role 

# This tells FastAPI which URL to use to get the token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login/access-token")


def get_db():
    """
    Dependency that provides a database session for each request.
    This is the function that was missing.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    Dependency function to decode a JWT token and get the current user from the database.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = token_schema.TokenData(email=payload.get("sub"))
        if token_data.email is None:
            raise HTTPException(status_code=403, detail="Could not validate credentials")
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = crud.user.get_user_by_email(db, email=token_data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user
# Add this function to deps.py

def get_current_user_with_role(required_role: Role):
    """
    A dependency that checks if the current user has the required role.
    """
    def _get_user_with_role(current_user: User = Depends(get_current_user)):
        if required_role.value not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user
    return _get_user_with_role
