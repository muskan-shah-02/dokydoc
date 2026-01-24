from datetime import timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from typing import Any
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.core.logging import LoggerMixin
from app.core.exceptions import AuthenticationException, ValidationException
from app.middleware.rate_limiter import limiter, RateLimits
from jose import jwt, JWTError

class LoginEndpoints(LoggerMixin):
    """Login endpoints with enhanced logging and error handling."""
    
    def __init__(self):
        super().__init__()

# Create instance for use in endpoints
login_endpoints = LoginEndpoints()

router = APIRouter()

@router.post("/users/", response_model=schemas.user.User, status_code=201)
@limiter.limit(RateLimits.AUTH)  # API-01 FIX: Prevent account creation abuse (5/min, 20/hour)
def create_user(
    request: Request,  # API-01 FIX: Required for rate limiter
    *,
    db: Session = Depends(deps.get_db),
    user_in: schemas.user.UserCreate,
) -> Any:
    """
    Create a new user.

    Rate Limit: 5 registrations/minute, 20/hour per IP (prevents spam)
    """
    logger = login_endpoints.logger
    logger.info(f"Creating new user with email: {user_in.email}")
    
    user = crud.user.get_user_by_email(db, email=user_in.email)
    if user:
        logger.warning(f"User creation failed - email {user_in.email} already exists")
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists.",
        )
    
    user = crud.user.create_user(db=db, obj_in=user_in)
    logger.info(f"User {user.id} created successfully with email: {user.email}")
    return user


@router.post("/login/access-token", response_model=schemas.token.Token)
@limiter.limit(RateLimits.AUTH)  # API-01 FIX: Prevent brute force (5/min, 20/hour)
def login_for_access_token(
    request: Request,  # API-01 FIX: Required for rate limiter
    db: Session = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.

    Rate Limit: 5 login attempts/minute, 20/hour per IP (prevents brute force)
    """
    logger = login_endpoints.logger
    logger.info(f"Login attempt for user: {form_data.username}")
    
    user = crud.user.get_user_by_email(db, email=form_data.username)
    if not user:
        logger.warning(f"Login failed - user not found: {form_data.username}")
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Login failed - incorrect password for user: {form_data.username}")
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # BE-04/AUTH-01 FIX: Create both access and refresh tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email, expires_delta=access_token_expires
    )

    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_refresh_token(
        subject=user.email, expires_delta=refresh_token_expires
    )

    logger.info(f"Login successful for user: {user.email} (access token: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}min, refresh token: {settings.REFRESH_TOKEN_EXPIRE_DAYS}d)")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,  # BE-04 FIX: Return refresh token
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=schemas.token.Token)
@limiter.limit(RateLimits.AUTH)  # BE-04 FIX: Rate limit refresh endpoint
def refresh_access_token(
    request: Request,  # Required for rate limiter
    refresh_token: str,
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Use a refresh token to get a new access token.

    BE-04/AUTH-01 FIX: Prevents users from losing session during long document processing.
    Refresh tokens are long-lived (7 days) while access tokens expire quickly (30 min).

    Rate Limit: 5 refresh attempts/minute, 20/hour per IP
    """
    logger = login_endpoints.logger
    logger.info("Refresh token request received")

    try:
        # Decode and validate refresh token
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        # Validate this is actually a refresh token
        token_type = payload.get("type")
        if token_type != "refresh":
            logger.warning(f"Invalid token type for refresh: {token_type}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token type. Please use a refresh token.",
            )

        email = payload.get("sub")
        if email is None:
            logger.warning("Refresh token missing email")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid refresh token",
            )

    except JWTError as e:
        logger.warning(f"Refresh token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate refresh token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = crud.user.get_user_by_email(db, email=email)
    if not user:
        logger.warning(f"User not found for refresh token: {email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Create new access token and refresh token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        subject=user.email, expires_delta=access_token_expires
    )

    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_refresh_token = create_refresh_token(
        subject=user.email, expires_delta=refresh_token_expires
    )

    logger.info(f"Tokens refreshed for user: {user.email}")
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,  # Return new refresh token
        "token_type": "bearer"
    }


@router.get("/users/me", response_model=schemas.user.User)
def read_users_me(
    current_user: schemas.user.User = Depends(deps.get_current_user)
) -> Any:
    """
    Fetch the current logged in user.
    """
    logger = login_endpoints.logger
    logger.info(f"Fetching user profile for: {current_user.email}")
    return current_user
