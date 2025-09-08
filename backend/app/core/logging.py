import logging
import logging.config
import sys
from pathlib import Path
from typing import Dict, Any
import json
from datetime import datetime

from app.core.config import settings

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry, ensure_ascii=False)

class ColoredFormatter(logging.Formatter):
    """Colored formatter for development environment."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        formatted = super().format(record)
        return f"{color}{formatted}{reset}"

def setup_logging():
    """Configure logging based on environment settings."""
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Base logging configuration
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JSONFormatter,
            },
            "colored": {
                "()": ColoredFormatter,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "colored" if settings.ENVIRONMENT == "development" else "simple",
                "stream": sys.stdout
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "json",
                "filename": log_dir / "app.log",
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json",
                "filename": log_dir / "error.log",
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5
            }
        },
        "loggers": {
            "": {  # Root logger
                "handlers": ["console", "file", "error_file"],
                "level": settings.LOG_LEVEL,
                "propagate": False
            },
            "app": {  # Application logger
                "handlers": ["console", "file", "error_file"],
                "level": settings.LOG_LEVEL,
                "propagate": False
            },
            "uvicorn": {  # Uvicorn logger
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False
            },
            "sqlalchemy": {  # SQLAlchemy logger
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False
            }
        }
    }
    
    # Apply configuration
    logging.config.dictConfig(log_config)
    
    # Set specific logger levels
    logging.getLogger("app").setLevel(settings.LOG_LEVEL)
    logging.getLogger("uvicorn").setLevel("INFO")
    logging.getLogger("sqlalchemy").setLevel("WARNING")
    
    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel("WARNING")
    logging.getLogger("urllib3").setLevel("WARNING")

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(f"app.{name}")

class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return get_logger(self.__class__.__name__)
    
    def log_with_context(self, level: str, message: str, **kwargs):
        """Log message with additional context."""
        extra_fields = {
            "class": self.__class__.__name__,
            "extra_fields": kwargs
        }
        getattr(self.logger, level.lower())(message, extra=extra_fields)

# Initialize logging
setup_logging()

# Export main logger
logger = get_logger("main")
