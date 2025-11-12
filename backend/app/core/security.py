from datetime import datetime, timedelta, timezone
from typing import Any, Union

from jose import jwt
from passlib.context import CryptContext
import bcrypt

from app.core.config import settings

# CryptContext is used for hashing and verifying passwords.
# We specify the "bcrypt" scheme, which is a strong hashing algorithm.
# "deprecated="auto"" means it will automatically handle upgrading hashes if we change the scheme later.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _truncate_password(password: str) -> str:
    """
    Truncate password to 72 bytes to comply with bcrypt limits.
    
    bcrypt has a hard limit of 72 bytes for passwords. This function ensures
    that passwords are safely truncated while preserving as much of the original
    password as possible by handling UTF-8 encoding properly.
    
    :param password: The original password
    :return: The truncated password (max 72 bytes when UTF-8 encoded)
    """
    if not password:
        return password
        
    # Encode to bytes and truncate to 72 bytes
    password_bytes = password.encode('utf-8')
    if len(password_bytes) <= 72:
        return password
        
    # Truncate to 72 bytes, but be careful not to split UTF-8 characters
    truncated_bytes = password_bytes[:72]
    
    # Decode back to string, ignoring any incomplete UTF-8 sequences at the end
    return truncated_bytes.decode('utf-8', errors='ignore')


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
    
    Note: bcrypt has a 72-byte limit, so we truncate passwords to ensure compatibility.

    :param plain_password: The password to check.
    :param hashed_password: The stored hash to compare against.
    :return: True if the passwords match, False otherwise.
    """
    try:
        # Truncate password to 72 bytes to comply with bcrypt limits
        truncated_password = _truncate_password(plain_password)
        return pwd_context.verify(truncated_password, hashed_password)
    except Exception as e:
        print(f"Passlib verification failed: {str(e)}")
        # Fallback to raw bcrypt if passlib fails
        try:
            truncated_password = _truncate_password(plain_password)
            password_bytes = truncated_password.encode('utf-8')
            hash_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hash_bytes)
        except Exception as fallback_e:
            print(f"Raw bcrypt verification also failed: {str(fallback_e)}")
            return False


def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password.
    
    Note: bcrypt has a 72-byte limit, so we truncate passwords to ensure compatibility.

    :param password: The password to hash.
    :return: The hashed password as a string.
    """
    try:
        # Truncate password to 72 bytes to comply with bcrypt limits
        truncated_password = _truncate_password(password)
        return pwd_context.hash(truncated_password)
    except Exception as e:
        print(f"Passlib hashing failed: {str(e)}")
        # Fallback to raw bcrypt if passlib fails
        try:
            truncated_password = _truncate_password(password)
            password_bytes = truncated_password.encode('utf-8')
            salt = bcrypt.gensalt()
            hash_bytes = bcrypt.hashpw(password_bytes, salt)
            return hash_bytes.decode('utf-8')
        except Exception as fallback_e:
            print(f"Raw bcrypt hashing also failed: {str(fallback_e)}")
            raise

