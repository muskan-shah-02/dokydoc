import os
from typing import Optional, List
from pydantic import Field, validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Application settings with comprehensive configuration management.
    Supports environment-specific overrides and validation.
    """

    # --- Environment & Deployment ---
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")
    API_VERSION: str = Field(default="v1", env="API_VERSION")

    # --- Project Settings ---
    PROJECT_NAME: str = Field(default="DokyDoc", env="PROJECT_NAME")
    PROJECT_DESCRIPTION: str = Field(default="AI-Powered Document Analysis & Governance Platform")
    PROJECT_VERSION: str = Field(default="1.0.0", env="PROJECT_VERSION")

    # --- Server Settings ---
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    WORKERS: int = Field(default=1, env="WORKERS")

    # --- Database Settings ---
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = Field(default=20, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=30, env="DATABASE_MAX_OVERFLOW")
    DATABASE_POOL_TIMEOUT: int = Field(default=30, env="DATABASE_POOL_TIMEOUT")

    # --- Security Settings ---
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")

    # --- CORS Settings ---
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"], env="CORS_ORIGINS")
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True, env="CORS_ALLOW_CREDENTIALS")

    # --- AI Service Settings ---
    GEMINI_API_KEY: str = Field(..., env="GEMINI_API_KEY")
    GEMINI_MODEL: str = Field(default="gemini-1.5-pro-latest", env="GEMINI_MODEL")
    GEMINI_VISION_MODEL: str = Field(default="gemini-1.5-pro-latest", env="GEMINI_VISION_MODEL")
    GEMINI_MAX_RETRIES: int = Field(default=3, env="GEMINI_MAX_RETRIES")
    GEMINI_TIMEOUT: int = Field(default=60, env="GEMINI_TIMEOUT")

    # --- File Upload Settings ---
    MAX_FILE_SIZE: int = Field(default=50 * 1024 * 1024, env="MAX_FILE_SIZE")  # 50MB
    UPLOAD_DIR: str = Field(default="/app/uploads", env="UPLOAD_DIR")
    ALLOWED_EXTENSIONS: List[str] = Field(default=[".pdf", ".docx", ".doc", ".txt"], env="ALLOWED_EXTENSIONS")

    # --- Cache Settings ---
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    CACHE_TTL: int = Field(default=3600, env="CACHE_TTL")  # 1 hour

    # --- Logging Settings ---
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")

    # --- Rate Limiting ---
    RATE_LIMIT_PER_MINUTE: int = Field(default=100, env="RATE_LIMIT_PER_MINUTE")
    RATE_LIMIT_PER_HOUR: int = Field(default=1000, env="RATE_LIMIT_PER_HOUR")

    # --- Background Task Settings ---
    MAX_WORKERS: int = Field(default=4, env="MAX_WORKERS")
    TASK_TIMEOUT: int = Field(default=300, env="TASK_TIMEOUT")  # 5 minutes

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # Handle comma-separated string from environment variable
            if "," in v:
                return [origin.strip() for origin in v.split(",")]
            # Handle single value
            return [v.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000"]

    @validator("ALLOWED_EXTENSIONS", pre=True)
    def parse_allowed_extensions(cls, v):
        if isinstance(v, str):
            # Handle comma-separated string from environment variable
            if "," in v:
                return [ext.strip() for ext in v.split(",")]
            # Handle single value
            return [v.strip()]
        elif isinstance(v, list):
            return v
        return [".pdf", ".docx", ".doc", ".txt"]

    @validator("SECRET_KEY")
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v

    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        if not v or "YOUR_DATABASE_URL_HERE" in v:
            raise ValueError("DATABASE_URL must be properly configured")
        return v

    @validator("GEMINI_API_KEY")
    def validate_gemini_api_key(cls, v):
        if not v or "YOUR_GEMINI_API_KEY_HERE" in v:
            raise ValueError("GEMINI_API_KEY must be properly configured")
        return v

    class Config:
        # Let pydantic-settings handle environment variables automatically
        env_file = None
        env_file_encoding = 'utf-8'
        case_sensitive = True

# Create settings instance - let pydantic-settings read Docker environment variables
settings = Settings()

# Environment-specific overrides
if settings.ENVIRONMENT == "production":
    settings.DEBUG = False
    settings.LOG_LEVEL = "WARNING"
    settings.CORS_ORIGINS = ["https://yourdomain.com"]  # Update with actual domain
elif settings.ENVIRONMENT == "staging":
    settings.DEBUG = False
    settings.LOG_LEVEL = "INFO"
