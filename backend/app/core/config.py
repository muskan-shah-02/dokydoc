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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=480, env="ACCESS_TOKEN_EXPIRE_MINUTES")  # 8 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # --- CORS Settings ---
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"], env="CORS_ORIGINS")
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True, env="CORS_ALLOW_CREDENTIALS")
    
    # --- NEW: ALLOWED_HOSTS (Fix for CONFIG-01) ---
    ALLOWED_HOSTS: List[str] = Field(default=["localhost", "127.0.0.1"], env="ALLOWED_HOSTS")

    # --- AI Service Settings: Gemini ---
    GEMINI_API_KEY: str = Field(..., env="GEMINI_API_KEY")
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash", env="GEMINI_MODEL")
    GEMINI_VISION_MODEL: str = Field(default="gemini-2.5-flash", env="GEMINI_VISION_MODEL")
    GEMINI_MAX_RETRIES: int = Field(default=3, env="GEMINI_MAX_RETRIES")
    GEMINI_TIMEOUT: int = Field(default=60, env="GEMINI_TIMEOUT")

    # --- AI Service Settings: Claude/Anthropic (ADHOC-07) ---
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL: str = Field(default="claude-sonnet-4-5-20250929", env="ANTHROPIC_MODEL")
    ANTHROPIC_MAX_TOKENS: int = Field(default=4096, env="ANTHROPIC_MAX_TOKENS")
    ANTHROPIC_TIMEOUT: int = Field(default=120, env="ANTHROPIC_TIMEOUT")

    # --- AI Provider Routing (ADHOC-08) ---
    # "gemini" = Gemini only (default), "dual" = Claude for code + Gemini for docs
    AI_PROVIDER_MODE: str = Field(default="gemini", env="AI_PROVIDER_MODE")

    # --- Git Webhook Settings (ADHOC-09) ---
    WEBHOOK_SECRET: Optional[str] = Field(default=None, env="WEBHOOK_SECRET")
    GITHUB_TOKEN: Optional[str] = Field(default=None, env="GITHUB_TOKEN")

    # --- OAuth Integration Settings (Sprint 8) ---
    FRONTEND_URL: str = Field(default="http://localhost:3000", env="FRONTEND_URL")
    BACKEND_URL: str = Field(default="http://localhost:8000", env="BACKEND_URL")

    # Jira / Atlassian OAuth 2.0
    JIRA_CLIENT_ID: Optional[str] = Field(default=None, env="JIRA_CLIENT_ID")
    JIRA_CLIENT_SECRET: Optional[str] = Field(default=None, env="JIRA_CLIENT_SECRET")

    # Slack OAuth 2.0
    SLACK_CLIENT_ID: Optional[str] = Field(default=None, env="SLACK_CLIENT_ID")
    SLACK_CLIENT_SECRET: Optional[str] = Field(default=None, env="SLACK_CLIENT_SECRET")

    # GitHub OAuth App (private repo integration)
    GITHUB_CLIENT_ID: Optional[str] = Field(default=None, env="GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET: Optional[str] = Field(default=None, env="GITHUB_CLIENT_SECRET")

    # Confluence / Atlassian OAuth 2.0
    # Tip: if you use the same Atlassian OAuth App for Jira + Confluence, set these
    # to the same values as JIRA_CLIENT_ID / JIRA_CLIENT_SECRET.
    CONFLUENCE_CLIENT_ID: Optional[str] = Field(default=None, env="CONFLUENCE_CLIENT_ID")
    CONFLUENCE_CLIENT_SECRET: Optional[str] = Field(default=None, env="CONFLUENCE_CLIENT_SECRET")
    
    # --- File Upload Settings ---
    MAX_FILE_SIZE: int = Field(default=50 * 1024 * 1024, env="MAX_FILE_SIZE")  # 50MB
    UPLOAD_DIR: str = Field(default="/app/uploads", env="UPLOAD_DIR")
    ALLOWED_EXTENSIONS: List[str] = Field(default=[".pdf", ".docx", ".doc", ".txt"], env="ALLOWED_EXTENSIONS")

    # --- Cache & Task Broker Settings ---
    REDIS_URL: str = Field(default="redis://redis:6379", env="REDIS_URL")
    CACHE_TTL: int = Field(default=3600, env="CACHE_TTL")  # 1 hour
    
    # --- Celery Settings ---
    CELERY_BROKER_URL: str = Field(default="redis://dokydoc_redis:6379/0", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://dokydoc_redis:6379/0", env="CELERY_RESULT_BACKEND")
    CELERY_RESULT_BACKEND_URL: str = Field(default="redis://redis:6379/1", env="CELERY_RESULT_BACKEND_URL")
    CELERY_TASK_TRACK_STARTED: bool = Field(default=True, env="CELERY_TASK_TRACK_STARTED")
    CELERY_TASK_TIME_LIMIT: int = Field(default=30 * 60, env="CELERY_TASK_TIME_LIMIT")  # 30 minutes
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(default=25 * 60, env="CELERY_TASK_SOFT_TIME_LIMIT")  # 25 minutes
    
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
        
    # --- NEW: Validator for ALLOWED_HOSTS ---
    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            if "," in v:
                return [host.strip() for host in v.split(",")]
            return [v.strip()]
        return v

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
        env_file = ".env"
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