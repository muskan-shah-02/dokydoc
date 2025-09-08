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
        # Disable .env file loading to avoid JSON parsing issues
        env_file = None
        env_file_encoding = 'utf-8'
        case_sensitive = True

# Load environment variables manually to avoid pydantic-settings JSON parsing
def load_env_vars():
    """Load environment variables manually to avoid JSON parsing issues."""
    env_vars = {}
    
    # Load from .env file if it exists
    env_file_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    if os.path.exists(env_file_path):
        with open(env_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    # Override with actual environment variables
    for key, value in os.environ.items():
        env_vars[key] = value
    
    return env_vars

# Load environment variables
env_vars = load_env_vars()

# Create settings instance with manual environment variable handling
settings = Settings(
    DATABASE_URL=env_vars.get("DATABASE_URL"),
    SECRET_KEY=env_vars.get("SECRET_KEY", "your-super-secret-key-here-make-it-at-least-32-characters-long"),
    GEMINI_API_KEY=env_vars.get("GEMINI_API_KEY", ""),
    CORS_ORIGINS=env_vars.get("CORS_ORIGINS", "http://localhost:3000"),
    ALLOWED_EXTENSIONS=env_vars.get("ALLOWED_EXTENSIONS", ".pdf,.docx,.doc,.txt"),
    ENVIRONMENT=env_vars.get("ENVIRONMENT", "development"),
    DEBUG=env_vars.get("DEBUG", "true").lower() == "true",
    LOG_LEVEL=env_vars.get("LOG_LEVEL", "INFO"),
    REDIS_URL=env_vars.get("REDIS_URL", "redis://redis:6379"),
)

# Validate that required environment variables are set
if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

if not settings.GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")

# Environment-specific overrides
if settings.ENVIRONMENT == "production":
    settings.DEBUG = False
    settings.LOG_LEVEL = "WARNING"
    settings.CORS_ORIGINS = ["https://yourdomain.com"]  # Update with actual domain
elif settings.ENVIRONMENT == "staging":
    settings.DEBUG = False
    settings.LOG_LEVEL = "INFO"
