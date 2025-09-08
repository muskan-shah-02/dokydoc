from datetime import timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from typing import Any
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps
from app.core.security import create_access_token, verify_password
from app.core.logging import LoggerMixin
from app.core.exceptions import AuthenticationException, ValidationException

class LoginEndpoints(LoggerMixin):
    """Login endpoints with enhanced logging and error handling."""
    
    def __init__(self):
        super().__init__()

# Create instance for use in endpoints
login_endpoints = LoginEndpoints()

router = APIRouter()

@router.post("/users/", response_model=schemas.user.User, status_code=201)
def create_user(
    *,
    db: Session = Depends(deps.get_db),
    user_in: schemas.user.UserCreate,
) -> Any:
    """
    Create a new user.
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
def login_for_access_token(
    db: Session = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
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
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        subject=user.email, expires_delta=access_token_expires
    )
    
    logger.info(f"Login successful for user: {user.email}")
    return {"access_token": access_token, "token_type": "bearer"}


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
