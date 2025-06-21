from pydantic import BaseModel, EmailStr
from typing import List, Optional
from enum import Enum

# Define the available roles using an Enum for consistency and validation
class Role(str, Enum):
    CXO = "CXO"
    BA = "BA"
    DEVELOPER = "Developer"
    PRODUCT_MANAGER = "Product Manager"

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