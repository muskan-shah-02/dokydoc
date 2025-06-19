from datetime import datetime, timedelta, timezone
from typing import Any, Union

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# CryptContext is used for hashing and verifying passwords.
# We specify the "bcrypt" scheme, which is a strong hashing algorithm.
# "deprecated="auto"" means it will automatically handle upgrading hashes if we change the scheme later.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """
    Creates a new JWT access token.

    :param subject: The subject of the token (e.g., user's email or ID).
    :param expires_delta: The lifespan of the token. If not provided, it defaults
                          to the value from the settings.
    :return: The encoded JWT token as a string.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a hashed password.

    :param plain_password: The password to check.
    :param hashed_password: The stored hash to compare against.
    :return: True if the passwords match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password.

    :param password: The password to hash.
    :return: The hashed password as a string.
    """
    return pwd_context.hash(password)

